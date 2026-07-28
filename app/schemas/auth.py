"""Pydantic schemas for authentication and account-recovery flows."""
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.security import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    remember_me: bool = False


class ForgotPasswordEmailRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResetRequest(BaseModel):
    email: EmailStr
    security_answer: str | None = None
    admin_pin: str | None = None
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


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    security_question: str = Field(min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
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

    @field_validator("new_password")
    @classmethod
    def new_password_differs(cls, value: str, info) -> str:
        current_password = info.data.get("current_password")
        if current_password and value == current_password:
            raise ValueError("New password must be different from the current password")
        return value
