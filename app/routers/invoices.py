"""Invoice generation engine: selective invoicing from contract line items."""
from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_admin, require_login
from app.models.user import User
from app.schemas.invoice import InvoiceCreate
from app.services import contract_service, custom_field_service, invoice_service, line_item_service
from app.templating import render
from app.utils.exporters import export_csv, export_excel, export_pdf, export_word
from app.utils.invoice_pdf import invoice_pdf_response

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("")
def list_invoices(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    result = invoice_service.list_invoices(db, q, page, settings.page_size, status=status or None)
    totals_by_id = {inv.id: invoice_service.compute_invoice_totals(inv) for inv in result.items}
    return render(
        request,
        "invoices/list.html",
        {"page_result": result, "q": q or "", "status": status or "", "totals_by_id": totals_by_id},
        user=user,
        active_nav="invoices",
    )


@router.get("/export/{fmt}")
def export_invoices(
    fmt: str,
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoices = invoice_service.list_all_active_invoices(db, q, status=status or None)
    headers = ["S.No", "Invoice #", "Customer", "Invoice Date", "Line Total", "GST Amount", "Grand Total", "Status"]
    rows = [
        [idx + 1, inv.invoice_number, inv.customer_name, inv.invoice_date.isoformat(),
         float(inv.line_total), float(inv.gst_amount), float(inv.grand_total), "Void" if inv.is_void else "Posted"]
        for idx, inv in enumerate(invoices)
    ]
    if fmt == "csv":
        return export_csv("invoices.csv", headers, rows)
    if fmt == "excel":
        return export_excel("invoices.xlsx", headers, rows, sheet_name="Invoices")
    if fmt == "word":
        return export_word("invoices.docx", "Invoice Register", headers, rows)
    if fmt == "pdf":
        return export_pdf("invoices.pdf", "Invoice Register", headers, rows)
    return RedirectResponse("/invoices?error=Unsupported+export+format", status_code=303)


@router.get("/new")
def new_invoice_form(
    request: Request,
    contract_id: int | None = None,
    q: str | None = None,
    reissue_of: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    contracts = contract_service.list_all_active_contracts(db, q)
    selected_contract = None
    invoiceable_items = []
    if contract_id:
        selected_contract = contract_service.get_active_contract(db, contract_id)
        if selected_contract:
            invoiceable_items = line_item_service.list_invoiceable_line_items(db, contract_id)
    custom_fields = custom_field_service.list_fields(db, "invoices", only_visible=True)

    voided_invoice = None
    if reissue_of:
        voided_invoice = invoice_service.get_active_invoice(db, reissue_of)
        if voided_invoice is None or not voided_invoice.is_void:
            voided_invoice = None
            reissue_of = None

    return render(
        request,
        "invoices/new.html",
        {
            "contracts": contracts,
            "q": q or "",
            "selected_contract": selected_contract,
            "invoiceable_items": invoiceable_items,
            "gst_default": settings.gst_default_percentage,
            "custom_fields": custom_fields,
            "reissue_of": reissue_of,
            "voided_invoice": voided_invoice,
        },
        user=user,
        active_nav="invoices",
    )


@router.post("")
async def create_invoice(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    contract_id = int(form.get("contract_id"))
    selected_ids = [int(v) for v in form.getlist("line_item_ids")]

    quantities = {}
    unit_rates = {}
    for line_item_id in selected_ids:
        qty_raw = form.get(f"qty_{line_item_id}")
        rate_raw = form.get(f"rate_{line_item_id}")
        if qty_raw:
            quantities[line_item_id] = float(qty_raw)
        if rate_raw:
            unit_rates[line_item_id] = float(rate_raw)

    reissued_from_raw = form.get("reissued_from_id")
    try:
        data = InvoiceCreate(
            contract_id=contract_id,
            invoice_number=form.get("invoice_number", ""),
            invoice_date=form.get("invoice_date"),
            gst_percentage=float(form.get("gst_percentage") or settings.gst_default_percentage),
            line_item_ids=selected_ids,
            quantities=quantities,
            unit_rates=unit_rates,
            reissued_from_id=int(reissued_from_raw) if reissued_from_raw else None,
        )
        invoice = invoice_service.generate_invoice(db, data)

        submission = custom_field_service.collect_submission(db, "invoices", form)
        custom_field_service.save_values_for_record(db, "invoices", invoice.id, submission)

        db.commit()
        return RedirectResponse(f"/invoices/{invoice.id}?success=Invoice+generated+successfully", status_code=303)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a flash message
        db.rollback()
        return RedirectResponse(
            f"/invoices/new?contract_id={contract_id}&error={str(exc)}", status_code=303
        )


@router.get("/{invoice_id}")
def view_invoice(
    request: Request,
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None:
        return RedirectResponse("/invoices?error=Invoice+not+found", status_code=303)
    totals = invoice_service.compute_invoice_totals(invoice)
    custom_fields = custom_field_service.list_fields(db, "invoices", only_visible=True)
    custom_values = custom_field_service.get_values_for_record(db, "invoices", invoice_id)
    reissued_from = (
        invoice_service.get_active_invoice(db, invoice.reissued_from_id) if invoice.reissued_from_id else None
    )
    reissued_to = invoice_service.get_reissued_to(db, invoice.id)
    return render(
        request,
        "invoices/view.html",
        {
            "invoice": invoice,
            "totals": totals,
            "custom_fields": custom_fields,
            "custom_values": custom_values,
            "reissued_from": reissued_from,
            "reissued_to": reissued_to,
        },
        user=user,
        active_nav="invoices",
    )


@router.get("/{invoice_id}/export/pdf")
def export_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None:
        return RedirectResponse("/invoices?error=Invoice+not+found", status_code=303)
    return invoice_pdf_response(invoice)


@router.get("/{invoice_id}/export/{fmt}")
def export_invoice_table(
    invoice_id: int,
    fmt: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None:
        return RedirectResponse("/invoices?error=Invoice+not+found", status_code=303)

    headers = ["#", "Description", "Quantity", "Unit Rate", "Amount"]
    rows = [
        [idx + 1, item.description, float(item.quantity), float(item.unit_rate), float(item.amount)]
        for idx, item in enumerate(invoice.invoiced_line_items)
    ]
    rows.append(["", "Line Total", "", "", float(invoice.line_total)])
    rows.append(["", f"GST @ {invoice.gst_percentage}%", "", "", float(invoice.gst_amount)])
    rows.append(["", "Grand Total", "", "", float(invoice.grand_total)])

    filename_base = f"invoice_{invoice.invoice_number}"
    if fmt == "csv":
        return export_csv(f"{filename_base}.csv", headers, rows)
    if fmt == "excel":
        return export_excel(f"{filename_base}.xlsx", headers, rows, sheet_name="Invoice")
    if fmt == "word":
        return export_word(f"{filename_base}.docx", f"Invoice {invoice.invoice_number}", headers, rows)
    return RedirectResponse(f"/invoices/{invoice_id}?error=Unsupported+export+format", status_code=303)


@router.post("/{invoice_id}/void")
def void_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    reason: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None:
        return RedirectResponse("/invoices?error=Invoice+not+found", status_code=303)
    if not reason.strip():
        return RedirectResponse(f"/invoices/{invoice_id}?error=A+void+reason+is+required", status_code=303)
    try:
        invoice_service.void_invoice(db, invoice, reason.strip(), voided_by=user)
        db.commit()
        return RedirectResponse(f"/invoices/{invoice_id}?success=Invoice+voided", status_code=303)
    except invoice_service.InvoiceError as exc:
        db.rollback()
        return RedirectResponse(f"/invoices/{invoice_id}?error={exc}", status_code=303)


@router.get("/{invoice_id}/reissue")
def reissue_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    invoice = invoice_service.get_active_invoice(db, invoice_id)
    if invoice is None or not invoice.is_void:
        return RedirectResponse("/invoices?error=Only+voided+invoices+can+be+reissued", status_code=303)
    return RedirectResponse(f"/invoices/new?contract_id={invoice.contract_id}&reissue_of={invoice.id}", status_code=303)
