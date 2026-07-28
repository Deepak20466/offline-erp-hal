"""User model for authentication, roles, and account recovery."""
from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
VALID_ROLES = (ROLE_ADMIN, ROLE_STAFF)


class User(Base, TimestampMixin, SoftDeleteMixin):
    """An HAL ERP user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_STAFF, server_default=ROLE_STAFF)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    security_question: Mapped[str] = mapped_column(String(255), nullable=False)
    security_answer_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    remember_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remember_token_expires: Mapped[datetime | None] = mapped_column(nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
