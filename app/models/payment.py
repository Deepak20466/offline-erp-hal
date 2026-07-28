"""Payment model tracking receipts against invoices."""
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Payment(Base, TimestampMixin, SoftDeleteMixin):
    """A single payment received against an invoice.

    Posted payments are immutable — there is no edit route. Correcting a mistake
    means voiding the payment (keeping it, with a reason, for audit) and recording
    a fresh, correct payment in its place; ``is_deleted`` doubles as the void flag.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_received: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    tds_deducted: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    ld_applied: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment id={self.id} invoice_id={self.invoice_id}>"
