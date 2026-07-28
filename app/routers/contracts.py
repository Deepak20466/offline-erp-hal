"""Contract CRUD with exact column spec, dynamic fields, search, sort, export."""
from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_login
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractUpdate
from app.services import client_service, contract_service, custom_field_service
from app.templating import render
from app.utils.exporters import export_csv, export_excel, export_pdf, export_word

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
