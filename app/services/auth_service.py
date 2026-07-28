"""Authentication service: credential checks, session tokens, and remember-me cookies."""
import time
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.utils.security import generate_remember_token, hash_secret, verify_secret

_session_serializer = URLSafeSerializer(settings.secret_key, salt="hal-session")

SESSION_COOKIE = settings.session_cookie_name
REMEMBER_COOKIE = "hal_erp_remember"

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AccountLockedError(Exception):
    """Raised when a login is attempted against a temporarily locked account."""


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower(), User.is_deleted.is_(False)))


def _is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > datetime.now(timezone.utc)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if the email/password pair is valid, else None.

    Tracks failed attempts and temporarily locks the account after too many, to
    slow down offline/online password-guessing without a full IP-rate-limiter.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None

    if not user.is_active:
        return None

    if _is_locked(user):
        raise AccountLockedError(f"Account locked due to too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.")

    if not verify_secret(password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        db.flush()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def create_session_token(user_id: int, session_version: int, hours: int | None = None) -> tuple[str, int]:
    """Build a signed session token embedding its own expiry. Returns (token, max_age_seconds)."""
    duration_seconds = (hours or settings.session_hours) * 3600
    expires_at = int(time.time()) + duration_seconds
    token = _session_serializer.dumps({"uid": user_id, "exp": expires_at, "sv": session_version})
    return token, duration_seconds


def read_session_token(token: str) -> tuple[int, int] | None:
    """Decode a session token, returning (user id, session version) if valid and unexpired."""
    try:
        data = _session_serializer.loads(token)
    except BadSignature:
        return None
    if data.get("exp", 0) < time.time():
        return None
    uid = data.get("uid")
    if uid is None:
        return None
    return uid, data.get("sv", 0)


def bump_session_version(db: Session, user: User) -> None:
    """Invalidate every existing session/remember-me token for this user (e.g. on password change)."""
    user.session_version = (user.session_version or 0) + 1
    clear_remember_token(db, user)


def issue_remember_token(db: Session, user: User) -> tuple[str, int]:
    """Persist a hashed remember-me token for the user. Returns (cookie_value, max_age_seconds)."""
    raw_token = generate_remember_token()
    duration_seconds = settings.remember_me_days * 86400
    user.remember_token = hash_secret(raw_token)
    user.remember_token_expires = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    db.flush()
    cookie_value = f"{user.id}:{raw_token}"
    return cookie_value, duration_seconds


def resolve_remember_cookie(db: Session, cookie_value: str) -> User | None:
    """Validate a remember-me cookie value of the form '<user_id>:<raw_token>'."""
    try:
        user_id_str, raw_token = cookie_value.split(":", 1)
        user_id = int(user_id_str)
    except ValueError:
        return None

    user = db.scalar(select(User).where(User.id == user_id, User.is_deleted.is_(False)))
    if user is None or not user.remember_token or not user.remember_token_expires:
        return None

    expires_at = user.remember_token_expires
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    if not verify_secret(raw_token, user.remember_token):
        return None

    return user


def clear_remember_token(db: Session, user: User) -> None:
    user.remember_token = None
    user.remember_token_expires = None
    db.flush()
