"""Pydantic schemas for contract CRUD."""
from datetime import date

from pydantic import BaseModel, Field


class ContractBase(BaseModel):
    client_id: int
    contract_number: str = Field(min_length=1, max_length=100)
    description: str | None = None
    contract_date: date
    qty_ordered: float = Field(ge=0)
    qty_supplied: float = Field(ge=0)
    escalation_notes: str | None = None
    status: str = Field(default="active", max_length=30)


class ContractCreate(ContractBase):
    pass


class ContractUpdate(ContractBase):
    pass
