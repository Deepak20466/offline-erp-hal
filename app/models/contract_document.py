"""Saved Excel/Word snapshot generated from a contract, stored on disk.

Each row is a permanent, standalone copy: the file is written once at generation
time and this app never reads it back in, so edits made inside the Excel/Word file
can never flow back into the database.
"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

DOC_TYPE_EXCEL = "excel"
DOC_TYPE_WORD = "word"


class ContractDocument(Base, TimestampMixin):
    """Reference to a saved Excel or Word file linked to a contract."""

    __tablename__ = "contract_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doc_type: Mapped[str] = mapped_column(String(10), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    contract: Mapped["Contract"] = relationship()  # noqa: F821
    created_by: Mapped["User | None"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContractDocument id={self.id} contract_id={self.contract_id} type={self.doc_type!r}>"
