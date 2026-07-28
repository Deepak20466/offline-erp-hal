"""Payment logging and the invoice register / ledger view."""
from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_admin, require_login
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.services import invoice_service, payment_service
from app.templating import render
from app.utils.exporters import export_csv, export_excel, export_pdf, export_word

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("")
def invoice_register(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    invoice_id: int | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    result = payment_service.list_invoice_register(db, q, page, settings.page_size, status=status or None)
    totals_by_id = {inv.id: invoice_service.compute_invoice_totals(inv) for inv in result.items}
    payments_by_invoice = {
        inv.id: payment_service.list_payments_for_invoice(db, inv.id) for inv in result.items
    }
    return render(
        request,
        "payments/list.html",
        {
            "page_result": result,
            "q": q or "",
            "status": status or "",
            "totals_by_id": totals_by_id,
            "payments_by_invoice": payments_by_invoice,
            "open_invoice_id": invoice_id,
        },
        user=user,
        active_nav="payments",
    )


@router.get("/export/{fmt}")
def export_register(
    fmt: str,
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoices = payment_service.list_all_invoices_for_register(db, q, status=status or None)
    headers = ["S.No", "Invoice #", "Client Name", "Invoice Amount", "Amount Paid", "Outstanding", "Payment Status"]
    rows = []
    for idx, inv in enumerate(invoices):
        totals = invoice_service.compute_invoice_totals(inv)
        rows.append(
            [
                idx + 1, inv.invoice_number, inv.customer_name,
                float(totals.invoice_amount), float(totals.amount_paid), float(totals.outstanding),
                totals.payment_status.replace("_", " ").title(),
            ]
        )
    if fmt == "csv":
        return export_csv("invoice_register.csv", headers, rows)
    if fmt == "excel":
        return export_excel("invoice_register.xlsx", headers, rows, sheet_name="Invoice Register")
    if fmt == "word":
        return export_word("invoice_register.docx", "Invoice Register", headers, rows)
    if fmt == "pdf":
        return export_pdf("invoice_register.pdf", "Invoice Register", headers, rows)
    return RedirectResponse("/payments?error=Unsupported+export+format", status_code=303)


@router.post("")
async def create_payment(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    invoice_id = int(form.get("invoice_id"))
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None:
        return RedirectResponse("/payments?error=Invoice+not+found", status_code=303)
    try:
        data = PaymentCreate(
            invoice_id=invoice_id,
            amount_received=float(form.get("amount_received") or 0),
            payment_date=form.get("payment_date"),
            tds_deducted=float(form.get("tds_deducted") or 0),
            ld_applied=float(form.get("ld_applied") or 0),
            remarks=form.get("remarks") or None,
        )
        payment_service.record_payment(db, invoice, data)
        db.commit()
        return RedirectResponse("/payments?success=Payment+recorded+successfully", status_code=303)
    except (ValidationError, ValueError, payment_service.PaymentError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/payments?error={message}", status_code=303)


@router.post("/{payment_id}/void")
def void_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    reason: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    payment = payment_service.get_payment(db, payment_id)
    if payment is None:
        return RedirectResponse("/payments?error=Payment+not+found", status_code=303)
    if not reason.strip():
        return RedirectResponse("/payments?error=A+void+reason+is+required", status_code=303)
    try:
        payment_service.void_payment(db, payment, reason.strip(), voided_by=user)
        db.commit()
        return RedirectResponse("/payments?success=Payment+voided", status_code=303)
    except payment_service.PaymentError as exc:
        db.rollback()
        return RedirectResponse(f"/payments?error={exc}", status_code=303)
