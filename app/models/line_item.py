"""Contract line item model — the unit of selective invoicing."""
from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class LineItem(Base, TimestampMixin, SoftDeleteMixin):
    """A single billable line under a contract (description/qty/rate/amount)."""

    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    unit_rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ordered", nullable=False)
    # Nullable link set once a line item is picked for selective invoicing.
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    contract: Mapped["Contract"] = relationship(back_populates="line_items")  # noqa: F821
    invoice: Mapped["Invoice | None"] = relationship(back_populates="invoiced_line_items")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LineItem id={self.id} contract_id={self.contract_id}>"
