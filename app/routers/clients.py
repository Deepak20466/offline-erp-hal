"""Client CRUD, search, pagination, soft delete, and multi-format export."""
from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_login
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate
from app.services import client_service, custom_field_service
from app.templating import render
from app.utils.exporters import export_csv, export_excel, export_pdf, export_word

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def list_clients(
    request: Request,
    q: str | None = None,
    sort: str | None = None,
    dir: str = "asc",
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    result = client_service.list_clients(db, q, page, settings.page_size, sort=sort, direction=dir)
    custom_fields = custom_field_service.list_fields(db, "clients", only_visible=True)
    values_by_client = custom_field_service.get_values_for_records(
        db, "clients", [c.id for c in result.items]
    )
    return render(
        request,
        "clients/list.html",
        {
            "page_result": result,
            "q": q or "",
            "sort": sort or "",
            "dir": dir,
            "custom_fields": custom_fields,
            "values_by_client": values_by_client,
        },
        user=user,
        active_nav="clients",
    )


@router.get("/export/{fmt}")
def export_clients(
    fmt: str,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    clients = client_service.list_all_active_clients(db)
    if q:
        needle = q.lower()
        clients = [c for c in clients if needle in c.name.lower() or needle in (c.email or "").lower()]

    headers = ["S.No", "Name", "Email", "Phone", "Address", "GSTIN", "PAN"]
    rows = [
        [idx + 1, c.name, c.email or "", c.phone or "", c.address or "", c.gstin or "", c.pan or ""]
        for idx, c in enumerate(clients)
    ]

    if fmt == "csv":
        return export_csv("clients.csv", headers, rows)
    if fmt == "excel":
        return export_excel("clients.xlsx", headers, rows, sheet_name="Clients")
    if fmt == "word":
        return export_word("clients.docx", "Client Master List", headers, rows)
    if fmt == "pdf":
        return export_pdf("clients.pdf", "Client Master List", headers, rows)
    return RedirectResponse("/clients?error=Unsupported+export+format", status_code=303)


@router.post("")
async def create_client(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    try:
        data = ClientCreate(
            name=form.get("name", ""),
            email=form.get("email") or None,
            phone=form.get("phone") or None,
            address=form.get("address") or None,
            gstin=form.get("gstin") or None,
            pan=form.get("pan") or None,
        )
        client = client_service.create_client(db, data)
        submission = custom_field_service.collect_submission(db, "clients", form)
        custom_field_service.save_values_for_record(db, "clients", client.id, submission)
        db.commit()
        return RedirectResponse("/clients?success=Client+created+successfully", status_code=303)
    except ValidationError as exc:
        db.rollback()
        return RedirectResponse(f"/clients?error={exc.errors()[0]['msg']}", status_code=303)


@router.post("/{client_id}/edit")
async def edit_client(
    request: Request,
    client_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    client = client_service.get_active_client(db, client_id)
    if client is None:
        return RedirectResponse("/clients?error=Client+not+found", status_code=303)
    try:
        data = ClientUpdate(
            name=form.get("name", ""),
            email=form.get("email") or None,
            phone=form.get("phone") or None,
            address=form.get("address") or None,
            gstin=form.get("gstin") or None,
            pan=form.get("pan") or None,
        )
        client_service.update_client(db, client, data)
        submission = custom_field_service.collect_submission(db, "clients", form)
        custom_field_service.save_values_for_record(db, "clients", client.id, submission)
        db.commit()
        return RedirectResponse("/clients?success=Client+updated+successfully", status_code=303)
    except ValidationError as exc:
        db.rollback()
        return RedirectResponse(f"/clients?error={exc.errors()[0]['msg']}", status_code=303)


@router.post("/{client_id}/delete")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    client = client_service.get_active_client(db, client_id)
    if client is not None:
        client_service.delete_client(db, client)
        db.commit()
    return RedirectResponse("/clients?success=Client+moved+to+recycle+bin", status_code=303)


@router.post("/bulk-delete")
async def bulk_delete_clients(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    ids = [int(v) for v in form.get("ids", "").split(",") if v.strip().isdigit()]
    count = client_service.bulk_delete_clients(db, ids)
    db.commit()
    return RedirectResponse(f"/clients?success={count}+client(s)+moved+to+recycle+bin", status_code=303)
