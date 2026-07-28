"""Pydantic schemas for contract line items."""
from pydantic import BaseModel, Field


class LineItemBase(BaseModel):
    description: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit_rate: float = Field(ge=0)
    status: str = Field(default="ordered", max_length=20)


class LineItemCreate(LineItemBase):
    pass


class LineItemUpdate(LineItemBase):
    pass
