"""Password hashing, session tokens, and CSRF helpers."""
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_csrf_serializer = URLSafeTimedSerializer(settings.secret_key, salt="csrf-token")
_document_open_serializer = URLSafeTimedSerializer(settings.secret_key, salt="document-open-token")


def hash_secret(plain: str) -> str:
    """Hash a password, security answer, or PIN for storage."""
    return _pwd_context.hash(plain)


def verify_secret(plain: str, hashed: str) -> bool:
    """Verify a plaintext value against its stored hash."""
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def generate_remember_token() -> str:
    """Generate a cryptographically random token for the 'remember me' cookie."""
    return secrets.token_urlsafe(48)


def validate_password_strength(value: str) -> str:
    """Shared password policy: at least 8 characters with a mix of letters and digits.

    Used from every password-setting entry point (change password, forgot-password
    reset, admin create-user, admin set-password) so the rule lives in one place.
    """
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(ch.isalpha() for ch in value):
        raise ValueError("Password must contain at least one letter")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("Password must contain at least one digit")
    return value


def generate_csrf_token() -> str:
    """Generate a signed, timestamped CSRF token tied to the app secret."""
    return _csrf_serializer.dumps(secrets.token_urlsafe(16))


def validate_csrf_token(token: str | None, max_age_seconds: int = 60 * 60 * 6) -> bool:
    """Validate a CSRF token previously issued by generate_csrf_token."""
    if not token:
        return False
    try:
        _csrf_serializer.loads(token, max_age=max_age_seconds)
        return True
    except (BadSignature, SignatureExpired):
        return False


def generate_document_open_token(contract_id: int, doc_type: str) -> str:
    """Short-lived signed token scoped to one contract's document.

    Needed only for the ms-excel:/ms-word: "Open in Desktop App" links: when a user
    clicks one, Windows launches Excel/Word directly and that process fetches the URL
    itself — outside the browser, so it carries none of the browser's session cookies.
    This lets that one request past auth without exposing the document to anyone else,
    since the token is single-purpose (only this contract_id+doc_type) and expires in
    minutes.
    """
    return _document_open_serializer.dumps(f"{contract_id}:{doc_type}")


def verify_document_open_token(
    token: str | None, contract_id: int, doc_type: str, max_age_seconds: int = 300
) -> bool:
    """Validate a token previously issued by generate_document_open_token."""
    if not token:
        return False
    try:
        payload = _document_open_serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return payload == f"{contract_id}:{doc_type}"
