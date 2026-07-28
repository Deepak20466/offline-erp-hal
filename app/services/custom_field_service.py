"""Business logic for the dynamic Custom Field Manager and its stored values."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.custom_field import CustomField, CustomFieldValue
from app.schemas.custom_field import CustomFieldCreate, CustomFieldUpdate
from app.utils.soft_delete import soft_delete

RECORD_FK_BY_MODULE = {
    "contracts": "contract_id",
    "clients": "client_id",
    "invoices": "invoice_id",
}


def list_fields(db: Session, module: str, only_visible: bool = False) -> list[CustomField]:
    stmt = select(CustomField).where(CustomField.module == module, CustomField.is_deleted.is_(False))
    if only_visible:
        stmt = stmt.where(CustomField.is_visible.is_(True))
    stmt = stmt.order_by(CustomField.field_order.asc(), CustomField.id.asc())
    return list(db.scalars(stmt))


def get_field(db: Session, field_id: int) -> CustomField | None:
    field = db.get(CustomField, field_id)
    return field if field and not field.is_deleted else None


def create_field(db: Session, data: CustomFieldCreate) -> CustomField:
    field = CustomField(**data.model_dump())
    db.add(field)
    db.flush()
    return field


def update_field(db: Session, field: CustomField, data: CustomFieldUpdate) -> CustomField:
    for attr, value in data.model_dump().items():
        setattr(field, attr, value)
    db.flush()
    return field


def delete_field(db: Session, field: CustomField) -> None:
    """Soft delete the field definition only — stored values are left untouched."""
    soft_delete(db, field)


def reorder_fields(db: Session, module: str, ordered_field_ids: list[int]) -> None:
    for order, field_id in enumerate(ordered_field_ids):
        field = get_field(db, field_id)
        if field and field.module == module:
            field.field_order = order
    db.flush()


def parse_options(field: CustomField) -> list[str]:
    if not field.options:
        return []
    try:
        return json.loads(field.options)
    except json.JSONDecodeError:
        return []


def get_values_for_record(db: Session, module: str, record_id: int) -> dict[int, str]:
    """Return {custom_field_id: field_value} for a given record in a module."""
    fk_attr = RECORD_FK_BY_MODULE[module]
    stmt = select(CustomFieldValue).where(getattr(CustomFieldValue, fk_attr) == record_id)
    return {row.custom_field_id: row.field_value for row in db.scalars(stmt)}


def get_values_for_records(db: Session, module: str, record_ids: list[int]) -> dict[int, dict[int, str]]:
    """Batch version: {record_id: {custom_field_id: field_value}} for table rendering."""
    if not record_ids:
        return {}
    fk_attr = RECORD_FK_BY_MODULE[module]
    stmt = select(CustomFieldValue).where(getattr(CustomFieldValue, fk_attr).in_(record_ids))
    result: dict[int, dict[int, str]] = {rid: {} for rid in record_ids}
    for row in db.scalars(stmt):
        record_id = getattr(row, fk_attr)
        result.setdefault(record_id, {})[row.custom_field_id] = row.field_value
    return result


def collect_submission(db: Session, module: str, form) -> dict[int, str | None]:
    """Build the {field_id: raw_value} dict for a module's visible fields from a submitted form.

    Shared by every router that saves a record with dynamic fields (clients, contracts,
    invoices) so the "read each field, special-case checkboxes" logic lives in one place.
    """
    submission: dict[int, str | None] = {}
    for field in list_fields(db, module):
        key = f"custom_field_{field.id}"
        if field.field_type == "checkbox":
            submission[field.id] = "true" if form.get(key) else "false"
        else:
            submission[field.id] = form.get(key)
    return submission


def save_values_for_record(
    db: Session, module: str, record_id: int, submitted: dict[int, str | None]
) -> None:
    """Upsert custom field values for one record. ``submitted`` maps field_id -> raw value."""
    fk_attr = RECORD_FK_BY_MODULE[module]
    existing = {
        row.custom_field_id: row
        for row in db.scalars(
            select(CustomFieldValue).where(getattr(CustomFieldValue, fk_attr) == record_id)
        )
    }
    for field_id, value in submitted.items():
        if field_id in existing:
            existing[field_id].field_value = value
        else:
            new_value = CustomFieldValue(custom_field_id=field_id, field_value=value)
            setattr(new_value, fk_attr, record_id)
            db.add(new_value)
    db.flush()
