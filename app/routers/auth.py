"""Login, logout, and forgot-password routes."""
import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.dependencies import check_csrf, get_current_user, require_login
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, ForgotPasswordResetRequest, LoginRequest, ProfileUpdateRequest
from app.services.auth_service import (
    REMEMBER_COOKIE,
    SESSION_COOKIE,
    AccountLockedError,
    authenticate_user,
    bump_session_version,
    clear_remember_token,
    create_session_token,
    get_user_by_email,
    issue_remember_token,
)
from app.templating import render
from app.utils.security import hash_secret, verify_secret

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


@router.get("/login")
def login_form(request: Request, user: User | None = Depends(get_current_user)):
    if user is not None:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/login.html", {})


@router.post("/login")
def login_submit(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    remember_me: str | None = Form(None),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    try:
        data = LoginRequest(email=email, password=password, remember_me=bool(remember_me))
    except ValidationError:
        return render(request, "auth/login.html", {"error": "Please enter a valid email and password.", "email": email}, status_code=400)

    try:
        user = authenticate_user(db, data.email, data.password)
    except AccountLockedError as exc:
        db.commit()
        return render(request, "auth/login.html", {"error": str(exc), "email": email}, status_code=423)

    if user is None:
        db.commit()  # persist the incremented failed_login_attempts counter either way
        return render(request, "auth/login.html", {"error": "Invalid email or password.", "email": email}, status_code=401)

    token, max_age = create_session_token(user.id, user.session_version)
    redirect = RedirectResponse("/dashboard", status_code=303)
    redirect.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, samesite="lax")

    if data.remember_me:
        cookie_value, remember_max_age = issue_remember_token(db, user)
        redirect.set_cookie(
            REMEMBER_COOKIE, cookie_value, max_age=remember_max_age, httponly=True, samesite="lax"
        )
        db.commit()

    logger.info("User %s logged in", user.email)
    return redirect


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    redirect = RedirectResponse("/login", status_code=303)
    redirect.delete_cookie(SESSION_COOKIE)
    redirect.delete_cookie(REMEMBER_COOKIE)
    if user is not None:
        clear_remember_token(db, user)
        db.commit()
    return redirect


@router.get("/forgot-password")
def forgot_password_form(request: Request):
    return render(request, "auth/forgot_password.html", {})


@router.post("/forgot-password")
def forgot_password_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    user = get_user_by_email(db, email)
    if user is None:
        return render(
            request,
            "auth/forgot_password.html",
            {"error": "No account was found with that email address."},
            status_code=404,
        )
    return render(
        request,
        "auth/forgot_password_reset.html",
        {"email": user.email, "security_question": user.security_question},
    )


@router.post("/forgot-password/reset")
def forgot_password_reset(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    security_answer: str = Form(""),
    admin_pin: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    user = get_user_by_email(db, email)
    if user is None:
        return RedirectResponse("/forgot-password?error=Account+not+found", status_code=303)

    try:
        ForgotPasswordResetRequest(
            email=email,
            security_answer=security_answer or None,
            admin_pin=admin_pin or None,
            new_password=new_password,
            confirm_password=confirm_password,
        )
    except ValidationError as exc:
        return render(
            request,
            "auth/forgot_password_reset.html",
            {
                "email": email,
                "security_question": user.security_question,
                "error": exc.errors()[0]["msg"],
            },
            status_code=400,
        )

    answer_ok = bool(security_answer) and verify_secret(security_answer.strip().lower(), user.security_answer_hash)
    pin_ok = bool(admin_pin) and verify_secret(admin_pin.strip(), user.admin_pin_hash)

    if not (answer_ok or pin_ok):
        return render(
            request,
            "auth/forgot_password_reset.html",
            {
                "email": email,
                "security_question": user.security_question,
                "error": "Security answer or admin PIN is incorrect.",
            },
            status_code=401,
        )

    user.password_hash = hash_secret(new_password)
    bump_session_version(db, user)
    db.commit()

    return RedirectResponse("/login?success=Password+reset+successfully.+Please+sign+in.", status_code=303)


@router.get("/profile")
def profile_form(request: Request, user: User = Depends(require_login)):
    return render(request, "auth/profile.html", {}, user=user, active_nav="profile")


@router.post("/profile")
def profile_update(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    name: str = Form(...),
    email: str = Form(...),
    security_question: str = Form(...),
    security_answer: str = Form(""),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    try:
        data = ProfileUpdateRequest(name=name, email=email, security_question=security_question)
    except ValidationError as exc:
        return render(
            request, "auth/profile.html", {"error": exc.errors()[0]["msg"]}, user=user, active_nav="profile", status_code=400
        )

    existing = get_user_by_email(db, data.email)
    if existing is not None and existing.id != user.id:
        return render(
            request,
            "auth/profile.html",
            {"error": "That email address is already in use by another account."},
            user=user,
            active_nav="profile",
            status_code=400,
        )

    user.name = data.name
    user.email = data.email.lower()
    user.security_question = data.security_question
    if security_answer.strip():
        user.security_answer_hash = hash_secret(security_answer.strip().lower())
    db.commit()
    return RedirectResponse("/profile?success=Profile+updated+successfully", status_code=303)


@router.get("/change-password")
def change_password_form(request: Request, user: User = Depends(require_login)):
    return render(request, "auth/change_password.html", {}, user=user, active_nav="profile")


@router.post("/change-password")
def change_password_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(csrf_token)
    if not verify_secret(current_password, user.password_hash):
        return render(
            request, "auth/change_password.html", {"error": "Your current password is incorrect."},
            user=user, active_nav="profile", status_code=401,
        )
    try:
        ChangePasswordRequest(
            current_password=current_password, new_password=new_password, confirm_password=confirm_password
        )
    except ValidationError as exc:
        return render(
            request, "auth/change_password.html", {"error": exc.errors()[0]["msg"]},
            user=user, active_nav="profile", status_code=400,
        )

    user.password_hash = hash_secret(new_password)
    bump_session_version(db, user)
    db.commit()

    # Re-establish a fresh session for the current browser under the new session_version
    # so the user isn't immediately logged out of the tab they just changed the password in.
    token, max_age = create_session_token(user.id, user.session_version)
    redirect = RedirectResponse("/profile?success=Password+changed+successfully", status_code=303)
    redirect.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, samesite="lax")
    redirect.delete_cookie(REMEMBER_COOKIE)
    return redirect
