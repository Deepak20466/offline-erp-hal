"""Dynamic custom field definitions and their per-record values."""
import json

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin

VALID_MODULES = ("contracts", "clients", "invoices")
VALID_FIELD_TYPES = (
    "text",
    "textarea",
    "number",
    "currency",
    "date",
    "dropdown",
    "email",
    "phone",
    "checkbox",
)


class CustomField(Base, TimestampMixin, SoftDeleteMixin):
    """Admin-defined field that extends a module's table/form without code changes."""

    __tablename__ = "custom_fields"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    module: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_label: Mapped[str] = mapped_column(String(150), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    field_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    options: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list for dropdowns

    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="custom_field", cascade="all, delete-orphan"
    )

    @property
    def options_list(self) -> list[str]:
        """Parsed dropdown options, or an empty list for non-dropdown fields."""
        if not self.options:
            return []
        try:
            return json.loads(self.options)
        except json.JSONDecodeError:
            return []

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CustomField id={self.id} module={self.module} name={self.field_name!r}>"


class CustomFieldValue(Base, TimestampMixin):
    """The stored value of a custom field for one specific record."""

    __tablename__ = "custom_field_values"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    custom_field_id: Mapped[int] = mapped_column(
        ForeignKey("custom_fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    client_id: Mapped[int | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True
    )
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True, index=True
    )
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    custom_field: Mapped["CustomField"] = relationship(back_populates="values")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CustomFieldValue id={self.id} field_id={self.custom_field_id}>"
