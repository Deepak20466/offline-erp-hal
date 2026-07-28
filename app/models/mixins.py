"""Reusable SQLAlchemy mixins for timestamps and soft deletes."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds created_at / updated_at columns, maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Adds an is_deleted flag so records are hidden instead of removed."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
