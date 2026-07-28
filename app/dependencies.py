"""Shared FastAPI dependencies: DB session, current user, and CSRF checks."""
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import ROLE_ADMIN, User
from app.services.auth_service import (
    REMEMBER_COOKIE,
    SESSION_COOKIE,
    create_session_token,
    read_session_token,
    resolve_remember_cookie,
)
from app.utils.security import validate_csrf_token


def _valid_active_user(db: Session, user_id: int, session_version: int | None = None) -> User | None:
    user = db.get(User, user_id)
    if user is None or user.is_deleted or not user.is_active:
        return None
    if session_version is not None and session_version != (user.session_version or 0):
        return None  # token was issued before a password change / forced logout
    return user


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User | None:
    """Resolve the logged-in user from the session cookie, falling back to remember-me."""
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        decoded = read_session_token(session_token)
        if decoded is not None:
            user_id, session_version = decoded
            user = _valid_active_user(db, user_id, session_version)
            if user is not None:
                return user

    remember_cookie = request.cookies.get(REMEMBER_COOKIE)
    if remember_cookie:
        user = resolve_remember_cookie(db, remember_cookie)
        if user is not None:
            token, max_age = create_session_token(user.id, user.session_version)
            response.set_cookie(
                SESSION_COOKIE, token, max_age=max_age, httponly=True, samesite="lax"
            )
            return user

    return None


def require_login(user: User | None = Depends(get_current_user)) -> User:
    """Dependency for protected routes: redirects to /login when unauthenticated."""
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_admin(user: User = Depends(require_login)) -> User:
    """Dependency for admin-only routes: 403s out staff accounts."""
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="This action requires administrator access.")
    return user


def check_csrf(csrf_token: str | None) -> None:
    """Raise a 400 if the given CSRF token is missing, tampered, or expired."""
    if not validate_csrf_token(csrf_token):
        raise HTTPException(status_code=400, detail="Your session expired. Please try again.")
