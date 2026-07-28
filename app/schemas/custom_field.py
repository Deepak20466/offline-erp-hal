"""Pydantic schemas for the dynamic custom field manager."""
import json

from pydantic import BaseModel, Field, field_validator

from app.models.custom_field import VALID_FIELD_TYPES, VALID_MODULES


class CustomFieldCreate(BaseModel):
    module: str
    field_name: str = Field(min_length=1, max_length=100)
    field_label: str = Field(min_length=1, max_length=150)
    field_type: str
    is_required: bool = False
    is_visible: bool = True
    field_order: int = 0
    options: str | None = None

    @field_validator("module")
    @classmethod
    def module_valid(cls, value: str) -> str:
        if value not in VALID_MODULES:
            raise ValueError(f"module must be one of {VALID_MODULES}")
        return value

    @field_validator("field_type")
    @classmethod
    def field_type_valid(cls, value: str) -> str:
        if value not in VALID_FIELD_TYPES:
            raise ValueError(f"field_type must be one of {VALID_FIELD_TYPES}")
        return value

    @field_validator("field_name")
    @classmethod
    def field_name_slug(cls, value: str) -> str:
        slug = value.strip().lower().replace(" ", "_")
        if not slug.replace("_", "").isalnum():
            raise ValueError("field_name may only contain letters, numbers, and underscores")
        return slug

    @field_validator("options")
    @classmethod
    def options_valid_json(cls, value: str | None, info) -> str | None:
        if info.data.get("field_type") != "dropdown":
            return None
        if not value:
            raise ValueError("Dropdown fields require at least one option")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Options must be valid JSON, e.g. [\"Option 1\", \"Option 2\"]") from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("Options must be a JSON list of strings")
        return json.dumps(parsed)


class CustomFieldUpdate(CustomFieldCreate):
    pass
