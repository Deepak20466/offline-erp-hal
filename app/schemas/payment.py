"""Pydantic schemas for payment logging."""
from datetime import date

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    invoice_id: int
    amount_received: float = Field(ge=0)
    payment_date: date
    tds_deducted: float = Field(ge=0, default=0)
    ld_applied: float = Field(ge=0, default=0)
    remarks: str | None = None
