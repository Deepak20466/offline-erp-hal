"""Sales journal model — auto-generated double-entry rows per invoice."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SalesJournal(Base):
    """A single debit or credit row auto-posted when an invoice is created."""

    __tablename__ = "sales_journal"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    debit_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    credit_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="sales_journal_entries")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SalesJournal id={self.id} invoice_id={self.invoice_id} account={self.account_name!r}>"
