"""Invoice model generated from selected contract line items."""
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin

STATUS_POSTED = "posted"
STATUS_VOID = "void"


class Invoice(Base, TimestampMixin, SoftDeleteMixin):
    """A tax invoice raised against one or more of a contract's line items.

    Posted invoices are immutable — there is no edit route. Correcting a mistake
    means voiding the invoice (preserving it and its sales-journal trail for audit)
    and then reissuing a fresh invoice against the now-unlocked line items.
    """

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(15), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    unit_rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gst_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=18)
    line_total: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    gst_amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    amount_in_words: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_POSTED, server_default=STATUS_POSTED)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    voided_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reissued_from_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    @property
    def is_void(self) -> bool:
        return self.status == STATUS_VOID

    contract: Mapped["Contract"] = relationship(back_populates="invoices")  # noqa: F821
    invoiced_line_items: Mapped[list["LineItem"]] = relationship(  # noqa: F821
        back_populates="invoice"
    )
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        back_populates="invoice", cascade="all, delete-orphan"
    )
    sales_journal_entries: Mapped[list["SalesJournal"]] = relationship(  # noqa: F821
        back_populates="invoice", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice id={self.id} number={self.invoice_number!r}>"
