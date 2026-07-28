"""Pydantic schemas for invoice generation."""
from datetime import date

from pydantic import BaseModel, Field, field_validator


class InvoiceCreate(BaseModel):
    contract_id: int
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: date
    gst_percentage: float = Field(ge=0, le=100)
    line_item_ids: list[int] = Field(min_length=1)
    quantities: dict[int, float] = Field(default_factory=dict)
    unit_rates: dict[int, float] = Field(default_factory=dict)
    reissued_from_id: int | None = None

    @field_validator("line_item_ids")
    @classmethod
    def at_least_one_item(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("Select at least one line item to invoice")
        return value
