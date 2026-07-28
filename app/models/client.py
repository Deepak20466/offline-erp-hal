"""Client (customer) master data model."""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Client(Base, TimestampMixin, SoftDeleteMixin):
    """A client / customer that contracts and invoices are issued against."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(15), nullable=True)

    contracts: Mapped[list["Contract"]] = relationship(  # noqa: F821
        back_populates="client", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Client id={self.id} name={self.name!r}>"
