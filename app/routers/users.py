"""Admin-only User Management: create, view, update, roles, soft delete/restore/purge."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.dependencies import check_csrf, require_admin
from app.models.user import User
from app.schemas.user import AdminSetPasswordRequest, UserCreate, UserUpdate
from app.services import user_service
from app.templating import render
from app.utils.exporters import export_csv, export_excel, export_pdf, export_word

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users(
    request: Request,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    dir: str = "asc",
    page: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = user_service.list_users(
        db, q, role or None, status or None, page, settings.page_size, sort=sort, direction=dir
    )
    return render(
        request,
        "users/list.html",
        {
            "page_result": result,
            "q": q or "",
            "role": role or "",
            "status": status or "",
            "sort": sort or "",
            "dir": dir,
        },
        user=user,
        active_nav="users",
    )


@router.get("/export/{fmt}")
def export_users(
    fmt: str,
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    users = user_service.list_all_users(db, q, role or None, status or None)
    headers = ["S.No", "Name", "Email", "Role", "Status", "Last Login"]
    rows = [
        [
            idx + 1, u.name, u.email, u.role.capitalize(), "Active" if u.is_active else "Inactive",
            u.last_login_at.strftime("%d-%b-%Y %H:%M") if u.last_login_at else "",
        ]
        for idx, u in enumerate(users)
    ]
    if fmt == "csv":
        return export_csv("users.csv", headers, rows)
    if fmt == "excel":
        return export_excel("users.xlsx", headers, rows, sheet_name="Users")
    if fmt == "word":
        return export_word("users.docx", "User Directory", headers, rows)
    if fmt == "pdf":
        return export_pdf("users.pdf", "User Directory", headers, rows)
    return RedirectResponse("/users?error=Unsupported+export+format", status_code=303)


@router.post("")
def create_user(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("staff"),
    security_question: str = Form(...),
    security_answer: str = Form(...),
    admin_pin: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    try:
        data = UserCreate(
            name=name, email=email, password=password, role=role,
            security_question=security_question, security_answer=security_answer, admin_pin=admin_pin,
        )
        user_service.create_user(db, data)
        db.commit()
        return RedirectResponse("/users?success=User+created+successfully", status_code=303)
    except (ValidationError, user_service.UserError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/users?error={message}", status_code=303)


@router.post("/{user_id}/edit")
def edit_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    is_active: str | None = Form(None),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    target = user_service.get_active_user(db, user_id)
    if target is None:
        return RedirectResponse("/users?error=User+not+found", status_code=303)
    try:
        data = UserUpdate(name=name, email=email, role=role, is_active=bool(is_active))
        user_service.update_user(db, target, data, acting_user=user)
        db.commit()
        return RedirectResponse("/users?success=User+updated+successfully", status_code=303)
    except (ValidationError, user_service.UserError) as exc:
        db.rollback()
        message = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(f"/users?error={message}", status_code=303)


@router.post("/{user_id}/set-password")
def set_password(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    target = user_service.get_active_user(db, user_id)
    if target is None:
        return RedirectResponse("/users?error=User+not+found", status_code=303)
    try:
        AdminSetPasswordRequest(new_password=new_password, confirm_password=confirm_password)
        user_service.set_password(db, target, new_password)
        db.commit()
        return RedirectResponse(
            f"/users?success=Password+reset+for+{quote(target.name)}."
            "+They+have+been+signed+out+of+all+devices.",
            status_code=303,
        )
    except ValidationError as exc:
        db.rollback()
        return RedirectResponse(f"/users?error={exc.errors()[0]['msg']}", status_code=303)


@router.post("/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    target = user_service.get_active_user(db, user_id)
    if target is None:
        return RedirectResponse("/users?error=User+not+found", status_code=303)
    try:
        user_service.delete_user(db, target, acting_user=user)
        db.commit()
        return RedirectResponse("/users?success=User+moved+to+recycle+bin", status_code=303)
    except user_service.UserError as exc:
        db.rollback()
        return RedirectResponse(f"/users?error={exc}", status_code=303)


@router.post("/bulk-delete")
async def bulk_delete_users(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    form = await request.form()
    check_csrf(form.get("csrf_token"))
    ids = [int(v) for v in form.get("ids", "").split(",") if v.strip().isdigit()]
    skipped = 0
    for user_id in ids:
        target = user_service.get_active_user(db, user_id)
        if target is None:
            continue
        try:
            user_service.delete_user(db, target, acting_user=user)
        except user_service.UserError:
            skipped += 1
    db.commit()
    message = f"{len(ids) - skipped}+user(s)+moved+to+recycle+bin"
    if skipped:
        message += f"+({skipped}+skipped)"
    return RedirectResponse(f"/users?success={message}", status_code=303)
