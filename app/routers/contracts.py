"""Contract CRUD with exact column spec, dynamic fields, search, sort, export."""
import io

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import FileResponse, RedirectResponse, StreamingResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_login
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractUpdate
from app.services import client_service, contract_service, custom_field_service, document_service, line_item_service
from app.templating import render
from app.utils.exporters import build_excel_bytes, build_word_bytes, export_csv, export_excel, export_pdf, export_word

DOCUMENT_MEDIA_TYPES = {
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

router = APIRouter(prefix="/contracts", tags=["contracts"])


CONTRACT_STATUSES = ("active", "completed", "on_hold", "cancelled")


@router.get("")
def list_contracts(
    request: Request,
    q: str | None = None,
    sort: str | None = None,
    dir: str = "asc",
    status: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    result = contract_service.list_contracts(db, q, sort, dir, page, settings.page_size, status=status or None)
    clients = client_service.list_all_active_clients(db)
    custom_fields = custom_field_service.list_fields(db, "contracts", only_visible=True)
    values_by_contract = custom_field_service.get_values_for_records(
        db, "contracts", [c.id for c in result.items]
    )
    return render(
        request,
        "contracts/list.html",
        {
            "page_result": result,
            "q": q or "",
            "sort": sort or "",
            "dir": dir,
            "status": status or "",
            "statuses": CONTRACT_STATUSES,
            "clients": clients,
            "custom_fields": custom_fields,
            "values_by_contract": values_by_contract,
        },
        user=user,
        active_nav="contracts",
    )


@router.get("/export/{fmt}")
def export_contracts(
    fmt: str,
    q: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    contracts = contract_service.list_all_active_contracts(db, q, status=status or None)
    custom_fields = custom_field_service.list_fields(db, "contracts", only_visible=True)
    values_by_contract = custom_field_service.get_values_for_records(db, "contracts", [c.id for c in contracts])

    headers = [
        "S.No", "Client Name", "Contract Number", "Description", "Contract Date",
        "Qty Ordered", "Qty Supplied", "Qty Pending", "Escalation Notes",
    ] + [f.field_label for f in custom_fields]

    rows = []
    for idx, c in enumerate(contracts):
        row = [
            idx + 1, c.client.name, c.contract_number, c.description or "",
            c.contract_date.isoformat(), c.qty_ordered, c.qty_supplied, c.qty_pending,
            c.escalation_notes or "",
        ]
        for f in custom_fields:
            row.append(values_by_contract.get(c.id, {}).get(f.id, ""))
        rows.append(row)

    if fmt == "csv":
        return export_csv("contracts.csv", headers, rows)
    if fmt == "excel":
        return export_excel("contracts.xlsx", headers, rows, sheet_name="Contracts")
    if fmt == "word":
        return export_word("contracts.docx", "Contract Register", headers, rows)
    if fmt == "pdf":
        return export_pdf("contracts.pdf", "Contract Register", headers, rows)
    return RedirectResponse("/contracts?error=Unsupported+export+format", status_code=303)


@router.get("/{contract_id}/documents/{fmt}")
def export_contract_document(
    contract_id: int,
    fmt: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Generate an Excel/Word snapshot of one contract from current data, save it as a new
    permanent version, and return it as a download — same download behaviour as any other
    export, plus permanent storage on the side.

    This is a one-way, point-in-time copy: it never re-opens or re-parses the saved file,
    so edits made inside it afterwards can never reach the database, and later ERP changes
    never touch a file already saved here. If nothing changed since the last export for
    this contract+format, the existing version is reused instead of writing a duplicate.
    """
    if fmt not in DOCUMENT_MEDIA_TYPES:
        return RedirectResponse(f"/contracts/{contract_id}?error=Unsupported+document+format", status_code=303)

    contract = contract_service.get_active_contract(db, contract_id)
    if contract is None:
        return RedirectResponse("/contracts?error=Contract+not+found", status_code=303)

    items = line_item_service.list_line_items(db, contract_id)
    headers = ["Description", "Quantity", "Unit Rate", "Amount", "Status"]
    rows = [
        [item.description, float(item.quantity), float(item.unit_rate), float(item.amount), item.status]
        for item in items
    ]

    if fmt == "excel":
        content = build_excel_bytes(headers, rows, sheet_name="Line Items")
    else:
        content = build_word_bytes(f"Contract {contract.contract_number}", headers, rows)

    document = document_service.save_document_version(
        db, contract.id, contract.contract_number, fmt, content, created_by_id=user.id
    )
    db.commit()

    return StreamingResponse(
        io.BytesIO(content),
        media_type=DOCUMENT_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{document.original_filename}"'},
    )


@router.get("/{contract_id}/view/{fmt}")
def open_contract_document(
    contract_id: int,
    fmt: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Download this contract's single permanent Excel/Word document ("View" -> Excel/Word).

    Completely separate from Export above: there is exactly one Excel file and one Word
    file per contract, created the first time it's downloaded and never touched again
    after that — not regenerated, not overwritten, regardless of later contract edits or
    how many times this is downloaded again. Edits made inside the file (in Excel/Word
    itself) stay in the file only; this route never reads its content back into the
    database. Plain browser download (Content-Disposition: attachment) every time — no
    protocol handlers, no automatic desktop app launch from here.
    """
    if fmt not in DOCUMENT_MEDIA_TYPES:
        return RedirectResponse(f"/contracts/{contract_id}?error=Unsupported+document+format", status_code=303)

    contract = contract_service.get_active_contract(db, contract_id)
    if contract is None:
        return RedirectResponse("/contracts?error=Contract+not+found", status_code=303)

    file_path = document_service.ensure_canonical_document(db, contract, fmt)

    label = "Excel" if fmt == "excel" else "MS_Word"
    extension = document_service.EXTENSION_BY_TYPE[fmt]
    return FileResponse(
        file_path,
        media_type=DOCUMENT_MEDIA_TYPES[fmt],
        filename=f"{contract.contract_number}_{label}.{extension}",
        content_disposition_type="attachment",
    )


@router.get("/document/{document_id}")
def view_contract_document(
    document_id: int,
    mode: str = "view",
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Open a previously saved Excel/Word file exactly as it was generated — no regeneration.

    ``mode=view`` streams it inline (View Excel/Word); ``mode=download`` forces a
    save-as download (Download Excel/Word). Blocked while the owning contract is in the
    recycle bin — access resumes automatically once the contract is restored, since this
    re-checks ``get_active_contract`` on every request rather than caching anything.
    """
    document = document_service.get_document(db, document_id)
    if document is None:
        return RedirectResponse("/contracts?error=Document+not+found", status_code=303)

    contract = contract_service.get_active_contract(db, document.contract_id)
    if contract is None:
        return RedirectResponse(
            "/contracts?error=This+document%27s+contract+is+in+the+recycle+bin", status_code=303
        )

    file_path = document_service.resolve_path(document)
    if not file_path.exists():
        return RedirectResponse(
            f"/contracts/{document.contract_id}?error=Saved+file+is+missing+on+disk", status_code=303
        )

    disposition = "inline" if mode == "view" else "attachment"
    return FileResponse(
        file_path,
        media_type=DOCUMENT_MEDIA_TYPES[document.doc_type],
        filename=document.original_filename,
        content_disposition_type=disposition,
    )


@router.post("")
async def create_contract(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    try:
        data = ContractCreate(
            client_id=int(form.get("client_id")),
            contract_number=form.get("contract_number", ""),
            description=form.get("description") or None,
            contract_date=form.get("contract_date"),
            qty_ordered=float(form.get("qty_ordered") or 0),
            qty_supplied=float(form.get("qty_supplied") or 0),
            escalation_notes=form.get("escalation_notes") or None,
            status=form.get("status") or "active",
        )
        contract = contract_service.create_contract(db, data)
        submission = custom_field_service.collect_submission(db, "contracts", form)
        custom_field_service.save_values_for_record(db, "contracts", contract.id, submission)
        db.commit()
        return RedirectResponse("/contracts?success=Contract+created+successfully", status_code=303)
    except (ValidationError, ValueError, TypeError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/contracts?error={message}", status_code=303)


@router.post("/{contract_id}/edit")
async def edit_contract(
    request: Request,
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    contract = contract_service.get_active_contract(db, contract_id)
    if contract is None:
        return RedirectResponse("/contracts?error=Contract+not+found", status_code=303)
    try:
        data = ContractUpdate(
            client_id=int(form.get("client_id")),
            contract_number=form.get("contract_number", ""),
            description=form.get("description") or None,
            contract_date=form.get("contract_date"),
            qty_ordered=float(form.get("qty_ordered") or 0),
            qty_supplied=float(form.get("qty_supplied") or 0),
            escalation_notes=form.get("escalation_notes") or None,
            status=form.get("status") or "active",
        )
        contract_service.update_contract(db, contract, data)
        submission = custom_field_service.collect_submission(db, "contracts", form)
        custom_field_service.save_values_for_record(db, "contracts", contract.id, submission)
        db.commit()
        return RedirectResponse("/contracts?success=Contract+updated+successfully", status_code=303)
    except (ValidationError, ValueError, TypeError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/contracts?error={message}", status_code=303)


@router.post("/{contract_id}/delete")
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    contract = contract_service.get_active_contract(db, contract_id)
    if contract is not None:
        contract_service.delete_contract(db, contract)
        db.commit()
    return RedirectResponse("/contracts?success=Contract+moved+to+recycle+bin", status_code=303)


@router.post("/bulk-delete")
async def bulk_delete_contracts(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    ids = [int(v) for v in form.get("ids", "").split(",") if v.strip().isdigit()]
    count = contract_service.bulk_delete_contracts(db, ids)
    db.commit()
    return RedirectResponse(f"/contracts?success={count}+contract(s)+moved+to+recycle+bin", status_code=303)
