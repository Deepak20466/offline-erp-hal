"""Contract model representing a client purchase order / work contract."""
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Contract(Base, TimestampMixin, SoftDeleteMixin):
    """A contract issued by a client, tracked by quantity ordered vs supplied."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_date: Mapped[date] = mapped_column(Date, nullable=False)
    qty_ordered: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    qty_supplied: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    escalation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    client: Mapped["Client"] = relationship(back_populates="contracts")  # noqa: F821
    line_items: Mapped[list["LineItem"]] = relationship(  # noqa: F821
        back_populates="contract", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(  # noqa: F821
        back_populates="contract", cascade="all, delete-orphan"
    )

    @property
    def qty_pending(self) -> float:
        """Outstanding quantity yet to be supplied."""
        return (self.qty_ordered or 0) - (self.qty_supplied or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contract id={self.id} number={self.contract_number!r}>"
