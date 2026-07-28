"""Admin panel for the Dynamic Field Manager (add/edit/delete/reorder/hide)."""
from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.dependencies import check_csrf, require_admin
from app.models.custom_field import VALID_FIELD_TYPES, VALID_MODULES
from app.models.user import User
from app.schemas.custom_field import CustomFieldCreate, CustomFieldUpdate
from app.services import custom_field_service
from app.templating import render

router = APIRouter(prefix="/admin/custom-fields", tags=["custom-fields"])


@router.get("")
def list_fields(
    request: Request,
    module: str = "contracts",
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if module not in VALID_MODULES:
        module = "contracts"
    fields = custom_field_service.list_fields(db, module)
    return render(
        request,
        "admin/custom_fields.html",
        {
            "fields": fields,
            "module": module,
            "modules": VALID_MODULES,
            "field_types": VALID_FIELD_TYPES,
        },
        user=user,
        active_nav="custom_fields",
    )


@router.post("")
def create_field(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    module: str = Form(...),
    field_name: str = Form(...),
    field_label: str = Form(...),
    field_type: str = Form(...),
    is_required: str | None = Form(None),
    is_visible: str | None = Form(None),
    field_order: int = Form(0),
    options: str | None = Form(None),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    try:
        data = CustomFieldCreate(
            module=module,
            field_name=field_name,
            field_label=field_label,
            field_type=field_type,
            is_required=bool(is_required),
            is_visible=bool(is_visible),
            field_order=field_order,
            options=options,
        )
        custom_field_service.create_field(db, data)
        db.commit()
        return RedirectResponse(
            f"/admin/custom-fields?module={module}&success=Field+added+successfully", status_code=303
        )
    except ValidationError as exc:
        db.rollback()
        return RedirectResponse(
            f"/admin/custom-fields?module={module}&error={exc.errors()[0]['msg']}", status_code=303
        )


@router.post("/{field_id}/edit")
def edit_field(
    request: Request,
    field_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    module: str = Form(...),
    field_name: str = Form(...),
    field_label: str = Form(...),
    field_type: str = Form(...),
    is_required: str | None = Form(None),
    is_visible: str | None = Form(None),
    field_order: int = Form(0),
    options: str | None = Form(None),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    field = custom_field_service.get_field(db, field_id)
    if field is None:
        return RedirectResponse(f"/admin/custom-fields?module={module}&error=Field+not+found", status_code=303)
    try:
        data = CustomFieldUpdate(
            module=module,
            field_name=field_name,
            field_label=field_label,
            field_type=field_type,
            is_required=bool(is_required),
            is_visible=bool(is_visible),
            field_order=field_order,
            options=options,
        )
        custom_field_service.update_field(db, field, data)
        db.commit()
        return RedirectResponse(
            f"/admin/custom-fields?module={module}&success=Field+updated+successfully", status_code=303
        )
    except ValidationError as exc:
        db.rollback()
        return RedirectResponse(
            f"/admin/custom-fields?module={module}&error={exc.errors()[0]['msg']}", status_code=303
        )


@router.post("/{field_id}/delete")
def delete_field(
    field_id: int,
    module: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    field = custom_field_service.get_field(db, field_id)
    if field is not None:
        custom_field_service.delete_field(db, field)
        db.commit()
    return RedirectResponse(f"/admin/custom-fields?module={module}&success=Field+removed", status_code=303)


@router.post("/{field_id}/move")
def move_field(
    field_id: int,
    module: str = Form(...),
    direction: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    fields = custom_field_service.list_fields(db, module)
    ids = [f.id for f in fields]
    if field_id in ids:
        idx = ids.index(field_id)
        swap_idx = idx - 1 if direction == "up" else idx + 1
        if 0 <= swap_idx < len(ids):
            ids[idx], ids[swap_idx] = ids[swap_idx], ids[idx]
            custom_field_service.reorder_fields(db, module, ids)
            db.commit()
    return RedirectResponse(f"/admin/custom-fields?module={module}", status_code=303)
