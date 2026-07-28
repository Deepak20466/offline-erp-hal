"""Pydantic schemas for the admin-only User Management module."""
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import VALID_ROLES
from app.utils.security import validate_password_strength


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=1)
    role: str = "staff"
    security_question: str = Field(min_length=1, max_length=255)
    security_answer: str = Field(min_length=1)
    admin_pin: str = Field(min_length=4, max_length=12)

    @field_validator("role")
    @classmethod
    def role_is_valid(cls, value: str) -> str:
        if value not in VALID_ROLES:
            raise ValueError(f"Role must be one of {', '.join(VALID_ROLES)}")
        return value

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password_strength(value)


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    role: str
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def role_is_valid(cls, value: str) -> str:
        if value not in VALID_ROLES:
            raise ValueError(f"Role must be one of {', '.join(VALID_ROLES)}")
        return value


class AdminSetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)
    confirm_password: str = Field(min_length=1)

    @field_validator("new_password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        new_password = info.data.get("new_password")
        if new_password and value != new_password:
            raise ValueError("Passwords do not match")
        return value
