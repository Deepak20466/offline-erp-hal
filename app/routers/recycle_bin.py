"""Recycle bin: view, restore, permanently delete, and empty soft-deleted records.

Invoices and payments are intentionally NOT here — as posted financial records they
use the Void & Reissue workflow instead (see app/routers/invoices.py and payments.py)
so they stay immutable and auditable rather than passing through a generic delete/purge.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_admin, require_login
from app.models.user import User
from app.services import client_service, contract_service, user_service
from app.templating import render
from app.utils.soft_delete import deleted_query

router = APIRouter(prefix="/recycle-bin", tags=["recycle-bin"])

MODULES = ("clients", "contracts", "users")
ADMIN_ONLY_MODULES = ("users",)

_LIST_FN = {
    "clients": client_service.list_deleted_clients,
    "contracts": contract_service.list_deleted_contracts,
    "users": user_service.list_deleted_users,
}


def _require_module_access(module: str, user: User) -> None:
    if module in ADMIN_ONLY_MODULES and not user.is_admin:
        raise HTTPException(status_code=403, detail="This section requires administrator access.")


def _get_deleted(db: Session, module: str, record_id: int):
    from app.models.client import Client
    from app.models.contract import Contract
    from app.models.user import User as UserModel

    model_map = {"clients": Client, "contracts": Contract, "users": UserModel}
    model = model_map.get(module)
    if model is None:
        return None
    instance = db.get(model, record_id)
    return instance if instance and instance.is_deleted else None


@router.get("")
def view_recycle_bin(
    request: Request,
    module: str = "clients",
    q: str | None = None,
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    if module not in MODULES or module in ADMIN_ONLY_MODULES and not user.is_admin:
        module = "clients"
    result = _LIST_FN[module](db, q, page, settings.page_size)
    visible_modules = [m for m in MODULES if m not in ADMIN_ONLY_MODULES or user.is_admin]
    return render(
        request,
        "recycle_bin.html",
        {"page_result": result, "module": module, "modules": visible_modules, "q": q or ""},
        user=user,
        active_nav="recycle_bin",
    )


@router.post("/{module}/{record_id}/restore")
def restore_record(
    module: str,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    _require_module_access(module, user)
    instance = _get_deleted(db, module, record_id)
    if instance is not None:
        try:
            if module == "clients":
                client_service.restore_client(db, instance)
            elif module == "contracts":
                contract_service.restore_contract(db, instance)
            elif module == "users":
                user_service.restore_user(db, instance)
            db.commit()
        except user_service.UserError as exc:
            db.rollback()
            return RedirectResponse(f"/recycle-bin?module={module}&error={exc}", status_code=303)
    return RedirectResponse(f"/recycle-bin?module={module}&success=Restored+successfully", status_code=303)


@router.post("/{module}/{record_id}/purge")
def purge_record(
    module: str,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    instance = _get_deleted(db, module, record_id)
    if instance is not None:
        if module == "clients":
            client_service.purge_client(db, instance)
        elif module == "contracts":
            contract_service.purge_contract(db, instance)
        elif module == "users":
            user_service.purge_user(db, instance)
        db.commit()
    return RedirectResponse(f"/recycle-bin?module={module}&success=Permanently+deleted", status_code=303)


@router.post("/{module}/empty")
def empty_recycle_bin(
    module: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    from app.models.client import Client
    from app.models.contract import Contract
    from app.models.user import User as UserModel

    model_map = {"clients": Client, "contracts": Contract, "users": UserModel}
    model = model_map.get(module)
    if model is not None:
        for instance in db.scalars(deleted_query(db, model)):
            db.delete(instance)
        db.commit()
    return RedirectResponse(f"/recycle-bin?module={module}&success=Recycle+bin+emptied", status_code=303)
