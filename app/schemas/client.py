"""Pydantic schemas for client master data."""
from pydantic import BaseModel, Field, field_validator


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = None
    gstin: str | None = Field(default=None, max_length=20)
    pan: str | None = Field(default=None, max_length=15)

    @field_validator("email")
    @classmethod
    def empty_email_to_none(cls, value: str | None) -> str | None:
        return value or None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    pass
