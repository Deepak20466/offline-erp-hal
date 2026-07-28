"""Helpers implementing the soft-delete pattern uniformly across repositories."""
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


def active_query(db: Session, model: type[ModelT]):
    """Return a SELECT statement scoped to non-deleted rows of ``model``."""
    return select(model).where(model.is_deleted.is_(False))


def deleted_query(db: Session, model: type[ModelT]):
    """Return a SELECT statement scoped to soft-deleted rows of ``model`` (recycle bin)."""
    return select(model).where(model.is_deleted.is_(True))


def soft_delete(db: Session, instance: ModelT) -> ModelT:
    """Flag a row as deleted instead of removing it from the table."""
    instance.is_deleted = True
    if hasattr(instance, "updated_at"):
        instance.updated_at = datetime.now(timezone.utc)
    db.flush()
    return instance


def restore(db: Session, instance: ModelT) -> ModelT:
    """Clear the deleted flag, returning a row from the recycle bin to active use."""
    instance.is_deleted = False
    if hasattr(instance, "updated_at"):
        instance.updated_at = datetime.now(timezone.utc)
    db.flush()
    return instance


def hard_delete(db: Session, instance: ModelT) -> None:
    """Permanently remove a row. Only ever called from the recycle bin's purge action."""
    db.delete(instance)
    db.flush()
