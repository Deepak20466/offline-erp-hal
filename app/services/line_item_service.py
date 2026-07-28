"""Business logic for contract line items — stored in the database, not Excel."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.line_item import LineItem
from app.schemas.line_item import LineItemCreate, LineItemUpdate
from app.utils.soft_delete import soft_delete


def list_line_items(db: Session, contract_id: int) -> list[LineItem]:
    stmt = (
        select(LineItem)
        .where(LineItem.contract_id == contract_id, LineItem.is_deleted.is_(False))
        .order_by(LineItem.id.asc())
    )
    return list(db.scalars(stmt))


def list_invoiceable_line_items(db: Session, contract_id: int) -> list[LineItem]:
    """Line items on a contract that have not yet been attached to an invoice."""
    stmt = (
        select(LineItem)
        .where(
            LineItem.contract_id == contract_id,
            LineItem.is_deleted.is_(False),
            LineItem.invoice_id.is_(None),
        )
        .order_by(LineItem.id.asc())
    )
    return list(db.scalars(stmt))


def get_line_item(db: Session, line_item_id: int) -> LineItem | None:
    item = db.get(LineItem, line_item_id)
    return item if item and not item.is_deleted else None


def create_line_item(db: Session, contract_id: int, data: LineItemCreate) -> LineItem:
    amount = Decimal(str(data.quantity)) * Decimal(str(data.unit_rate))
    item = LineItem(contract_id=contract_id, amount=amount, **data.model_dump())
    db.add(item)
    db.flush()
    return item


def update_line_item(db: Session, item: LineItem, data: LineItemUpdate) -> LineItem:
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    item.amount = Decimal(str(data.quantity)) * Decimal(str(data.unit_rate))
    db.flush()
    return item


def delete_line_item(db: Session, item: LineItem) -> None:
    soft_delete(db, item)
