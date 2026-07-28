"""The selective invoicing engine: contract line items -> invoice + sales journal.

Invoices are immutable once posted (no edit route). Fixing a mistake goes through
Void & Reissue: ``void_invoice`` marks the invoice void, posts reversing sales-journal
entries (never deletes the originals), and unlocks its line items; the user then raises
a brand-new invoice against those line items via the normal ``generate_invoice`` flow,
optionally tagging it with ``reissued_from_id`` so the two stay linked for audit.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.client import Client
from app.models.contract import Contract
from app.models.invoice import STATUS_POSTED, STATUS_VOID, Invoice
from app.models.line_item import LineItem
from app.models.payment import Payment
from app.models.sales_journal import SalesJournal
from app.models.user import User
from app.schemas.invoice import InvoiceCreate
from app.utils.number_to_words import number_to_indian_words
from app.utils.pagination import Page, paginate


class InvoiceError(Exception):
    """Raised for invoicing business-rule violations (bad selection, dup number, etc.)."""


def is_invoice_number_taken(db: Session, invoice_number: str, exclude_id: int | None = None) -> bool:
    stmt = select(Invoice.id).where(Invoice.invoice_number == invoice_number, Invoice.is_deleted.is_(False))
    if exclude_id:
        stmt = stmt.where(Invoice.id != exclude_id)
    return db.scalar(stmt) is not None


def generate_invoice(db: Session, data: InvoiceCreate) -> Invoice:
    """Create an invoice from selected contract line items, auto-populating and
    auto-calculating everything, then posting the matching sales journal entries.
    """
    contract = db.get(Contract, data.contract_id)
    if contract is None or contract.is_deleted:
        raise InvoiceError("Contract not found.")

    client = db.get(Client, contract.client_id)
    if client is None or client.is_deleted:
        raise InvoiceError("Client for this contract was not found.")

    if is_invoice_number_taken(db, data.invoice_number):
        raise InvoiceError(f"Invoice number '{data.invoice_number}' already exists.")

    if data.reissued_from_id is not None:
        voided_invoice = db.get(Invoice, data.reissued_from_id)
        if voided_invoice is None or voided_invoice.status != STATUS_VOID:
            raise InvoiceError("The invoice being reissued must exist and be void.")

    items = list(
        db.scalars(
            select(LineItem).where(
                LineItem.id.in_(data.line_item_ids),
                LineItem.contract_id == data.contract_id,
                LineItem.is_deleted.is_(False),
                LineItem.invoice_id.is_(None),
            )
        )
    )
    if len(items) != len(set(data.line_item_ids)):
        raise InvoiceError("One or more selected line items are unavailable (already invoiced or removed).")

    total_quantity = Decimal("0")
    line_total = Decimal("0")
    for item in items:
        qty = Decimal(str(data.quantities.get(item.id, item.quantity)))
        rate = Decimal(str(data.unit_rates.get(item.id, item.unit_rate)))
        if qty <= 0:
            raise InvoiceError(f"Quantity for '{item.description}' must be greater than zero.")
        total_quantity += qty
        line_total += qty * rate

    weighted_unit_rate = (line_total / total_quantity) if total_quantity else Decimal("0")
    gst_percentage = Decimal(str(data.gst_percentage))
    gst_amount = (line_total * gst_percentage / Decimal("100")).quantize(Decimal("0.01"))
    grand_total = (line_total + gst_amount).quantize(Decimal("0.01"))

    invoice = Invoice(
        contract_id=contract.id,
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date,
        customer_name=client.name,
        gstin=client.gstin,
        pan=client.pan,
        quantity=total_quantity,
        unit_rate=weighted_unit_rate.quantize(Decimal("0.01")),
        gst_percentage=gst_percentage,
        line_total=line_total.quantize(Decimal("0.01")),
        gst_amount=gst_amount,
        grand_total=grand_total,
        amount_in_words=number_to_indian_words(grand_total),
        status=STATUS_POSTED,
        reissued_from_id=data.reissued_from_id,
    )
    db.add(invoice)
    db.flush()

    for item in items:
        item.invoice_id = invoice.id
        item.status = "invoiced"
        if item.id in data.quantities:
            item.quantity = Decimal(str(data.quantities[item.id]))
        if item.id in data.unit_rates:
            item.unit_rate = Decimal(str(data.unit_rates[item.id]))
        item.amount = Decimal(str(item.quantity)) * Decimal(str(item.unit_rate))

    _post_sales_journal(db, invoice)

    db.flush()
    return invoice


def _post_sales_journal(db: Session, invoice: Invoice) -> None:
    """Auto-generate the double-entry sales journal rows for a new invoice."""
    entries = [
        SalesJournal(
            invoice_id=invoice.id,
            journal_date=invoice.invoice_date,
            account_name="Accounts Receivable",
            debit_amount=invoice.grand_total,
            credit_amount=Decimal("0"),
            description=f"Being invoice {invoice.invoice_number} raised on {invoice.customer_name}",
        ),
        SalesJournal(
            invoice_id=invoice.id,
            journal_date=invoice.invoice_date,
            account_name="Sales Revenue",
            debit_amount=Decimal("0"),
            credit_amount=invoice.line_total,
            description=f"Being sales value of invoice {invoice.invoice_number}",
        ),
    ]
    if invoice.gst_amount and invoice.gst_amount > 0:
        entries.append(
            SalesJournal(
                invoice_id=invoice.id,
                journal_date=invoice.invoice_date,
                account_name="GST Payable",
                debit_amount=Decimal("0"),
                credit_amount=invoice.gst_amount,
                description=f"Being GST on invoice {invoice.invoice_number}",
            )
        )
    db.add_all(entries)


@dataclass
class InvoiceTotals:
    invoice_amount: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    payment_status: str


def compute_invoice_totals(invoice: Invoice) -> InvoiceTotals:
    """Derive paid/outstanding amounts and a status tag from an invoice's payments."""
    grand_total = Decimal(str(invoice.grand_total))

    if invoice.status == STATUS_VOID:
        return InvoiceTotals(
            invoice_amount=grand_total, amount_paid=Decimal("0"), outstanding=Decimal("0"), payment_status="void"
        )

    active_payments = [p for p in invoice.payments if not p.is_deleted]
    amount_paid = sum((Decimal(str(p.amount_received)) for p in active_payments), Decimal("0"))
    tds = sum((Decimal(str(p.tds_deducted)) for p in active_payments), Decimal("0"))
    ld = sum((Decimal(str(p.ld_applied)) for p in active_payments), Decimal("0"))
    settled = amount_paid + tds + ld
    outstanding = grand_total - settled

    if ld > 0 and outstanding <= 0:
        status = "ld_applied"
    elif outstanding <= 0 and settled > 0:
        status = "fully_paid"
    elif settled > 0:
        status = "partially_paid"
    else:
        status = "pending"

    return InvoiceTotals(
        invoice_amount=grand_total, amount_paid=amount_paid, outstanding=outstanding, payment_status=status
    )


def list_invoices(db: Session, search: str | None, page: int, page_size: int, status: str | None = None) -> Page:
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.contract), selectinload(Invoice.payments))
        .where(Invoice.is_deleted.is_(False))
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Invoice.invoice_number.ilike(like), Invoice.customer_name.ilike(like)))
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.invoice_date.desc())
    return paginate(db, stmt, page, page_size)


def list_all_active_invoices(db: Session, search: str | None = None, status: str | None = None) -> list[Invoice]:
    stmt = select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Invoice.invoice_number.ilike(like), Invoice.customer_name.ilike(like)))
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.invoice_date.desc())
    return list(db.scalars(stmt).unique())


def get_active_invoice(db: Session, invoice_id: int) -> Invoice | None:
    invoice = db.get(Invoice, invoice_id)
    return invoice if invoice and not invoice.is_deleted else None


def get_reissued_to(db: Session, invoice_id: int) -> Invoice | None:
    """The invoice (if any) that was raised to reissue a voided invoice."""
    return db.scalar(select(Invoice).where(Invoice.reissued_from_id == invoice_id))


def void_invoice(db: Session, invoice: Invoice, reason: str, voided_by: User) -> None:
    """Void a posted invoice: keep it (and its journal trail) permanently, but unlock
    its line items for reissue and post reversing sales-journal entries rather than
    deleting the originals — this preserves an immutable, auditable accounting trail.
    """
    if invoice.status == STATUS_VOID:
        raise InvoiceError("This invoice has already been voided.")

    for item in invoice.invoiced_line_items:
        item.invoice_id = None
        item.status = "pending"

    for entry in invoice.sales_journal_entries:
        db.add(
            SalesJournal(
                invoice_id=invoice.id,
                journal_date=date.today(),
                account_name=entry.account_name,
                debit_amount=entry.credit_amount,
                credit_amount=entry.debit_amount,
                description=f"Reversal — voiding invoice {invoice.invoice_number}: {reason}",
            )
        )

    invoice.status = STATUS_VOID
    invoice.void_reason = reason
    invoice.voided_at = datetime.now(timezone.utc)
    invoice.voided_by_id = voided_by.id
    db.flush()
