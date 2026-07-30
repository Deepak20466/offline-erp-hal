"""Contract detail page and line item CRUD (managed in the database, not Excel)."""
from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.dependencies import check_csrf, require_login
from app.models.user import User
from app.schemas.line_item import LineItemCreate, LineItemUpdate
from app.services import contract_service, custom_field_service, document_service, line_item_service
from app.templating import render

router = APIRouter(tags=["line-items"])


@router.get("/contracts/{contract_id}")
def contract_detail(
    request: Request,
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    contract = contract_service.get_active_contract(db, contract_id)
    if contract is None:
        return RedirectResponse("/contracts?error=Contract+not+found", status_code=303)
    items = line_item_service.list_line_items(db, contract_id)
    custom_fields = custom_field_service.list_fields(db, "contracts", only_visible=True)
    custom_values = custom_field_service.get_values_for_record(db, "contracts", contract_id)
    documents = document_service.list_documents(db, contract_id)
    return render(
        request,
        "contracts/detail.html",
        {
            "contract": contract,
            "items": items,
            "custom_fields": custom_fields,
            "custom_values": custom_values,
            "documents": documents,
        },
        user=user,
        active_nav="contracts",
    )


@router.post("/contracts/{contract_id}/line-items")
async def create_line_item(
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
        data = LineItemCreate(
            description=form.get("description", ""),
            quantity=float(form.get("quantity") or 0),
            unit_rate=float(form.get("unit_rate") or 0),
            status=form.get("status") or "ordered",
        )
        line_item_service.create_line_item(db, contract_id, data)
        db.commit()
        return RedirectResponse(f"/contracts/{contract_id}?success=Line+item+added", status_code=303)
    except (ValidationError, ValueError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/contracts/{contract_id}?error={message}", status_code=303)


@router.post("/line-items/{item_id}/edit")
async def edit_line_item(
    request: Request,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    item = line_item_service.get_line_item(db, item_id)
    if item is None:
        return RedirectResponse("/contracts?error=Line+item+not+found", status_code=303)
    if item.invoice_id is not None:
        return RedirectResponse(
            f"/contracts/{item.contract_id}?error=Cannot+edit+a+line+item+already+invoiced", status_code=303
        )
    try:
        data = LineItemUpdate(
            description=form.get("description", ""),
            quantity=float(form.get("quantity") or 0),
            unit_rate=float(form.get("unit_rate") or 0),
            status=form.get("status") or "ordered",
        )
        line_item_service.update_line_item(db, item, data)
        db.commit()
        return RedirectResponse(f"/contracts/{item.contract_id}?success=Line+item+updated", status_code=303)
    except (ValidationError, ValueError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/contracts/{item.contract_id}?error={message}", status_code=303)


@router.post("/line-items/{item_id}/delete")
def delete_line_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    item = line_item_service.get_line_item(db, item_id)
    if item is None:
        return RedirectResponse("/contracts?error=Line+item+not+found", status_code=303)
    contract_id = item.contract_id
    if item.invoice_id is not None:
        return RedirectResponse(
            f"/contracts/{contract_id}?error=Cannot+delete+a+line+item+already+invoiced", status_code=303
        )
    line_item_service.delete_line_item(db, item)
    db.commit()
    return RedirectResponse(f"/contracts/{contract_id}?success=Line+item+removed", status_code=303)
