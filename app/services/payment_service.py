"""Business logic for logging payments and maintaining the invoice register.

Payments are immutable once posted (no edit route). Correcting a mistake means
voiding the payment — keeping the record and a reason for audit — and recording a
fresh, correct payment; there is no hard-delete path for a posted payment.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.services.invoice_service import compute_invoice_totals
from app.utils.pagination import Page, paginate


class PaymentError(Exception):
    """Raised for payment business-rule violations."""


def list_invoice_register(
    db: Session, search: str | None, page: int, page_size: int, status: str | None = None
) -> Page:
    stmt = select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Invoice.invoice_number.ilike(like), Invoice.customer_name.ilike(like)))
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.invoice_date.desc())
    return paginate(db, stmt, page, page_size)


def list_all_invoices_for_register(
    db: Session, search: str | None = None, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Invoice.invoice_number.ilike(like), Invoice.customer_name.ilike(like)))
    if status:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.invoice_date.desc())
    return list(db.scalars(stmt).unique())


def list_payments_for_invoice(db: Session, invoice_id: int) -> list[Payment]:
    """All payments for an invoice, including voided ones — voided payments stay
    visible (with their reason) for audit rather than disappearing from history.
    """
    stmt = select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.payment_date.desc())
    return list(db.scalars(stmt))


def record_payment(db: Session, invoice: Invoice, data: PaymentCreate) -> Payment:
    """Log a payment and derive its status from the invoice's running balance."""
    if invoice.is_void:
        raise PaymentError("Cannot record a payment against a voided invoice.")

    existing_paid = sum(
        (Decimal(str(p.amount_received)) + Decimal(str(p.tds_deducted)) + Decimal(str(p.ld_applied)))
        for p in invoice.payments
        if not p.is_deleted
    )
    settled_after = (
        existing_paid
        + Decimal(str(data.amount_received))
        + Decimal(str(data.tds_deducted))
        + Decimal(str(data.ld_applied))
    )
    grand_total = Decimal(str(invoice.grand_total))

    if data.ld_applied and settled_after >= grand_total:
        status = "ld_applied"
    elif settled_after >= grand_total:
        status = "fully_paid"
    elif settled_after > 0:
        status = "partially_paid"
    else:
        status = "pending"

    payment = Payment(
        invoice_id=invoice.id,
        amount_received=data.amount_received,
        payment_date=data.payment_date,
        tds_deducted=data.tds_deducted,
        ld_applied=data.ld_applied,
        remarks=data.remarks,
        payment_status=status,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment(db: Session, payment_id: int) -> Payment | None:
    payment = db.get(Payment, payment_id)
    return payment if payment and not payment.is_deleted else None


def void_payment(db: Session, payment: Payment, reason: str, voided_by: User) -> None:
    """Void a posted payment, preserving it (with a reason) for audit instead of deleting it."""
    if payment.is_deleted:
        raise PaymentError("This payment has already been voided.")
    payment.is_deleted = True
    payment.void_reason = reason
    payment.voided_at = datetime.now(timezone.utc)
    payment.voided_by_id = voided_by.id
    db.flush()
