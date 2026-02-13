"""Pydantic schemas for user authentication and profile."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.constants import VALID_TAGS


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    preferred_tags: list[str] = []

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("preferred_tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        invalid = [t for t in v if t not in VALID_TAGS]
        if invalid:
            raise ValueError(f"Invalid tags: {invalid}. Must be from: {VALID_TAGS}")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    preferred_tags: list[str] = []
    role: str | None = None
    custom_interests: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    name: str | None = None
    preferred_tags: list[str] | None = None
    role: str | None = None
    custom_interests: str | None = None

    @field_validator("preferred_tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = [t for t in v if t not in VALID_TAGS]
            if invalid:
                raise ValueError(f"Invalid tags: {invalid}. Must be from: {VALID_TAGS}")
        return v


class PreferencesResponse(BaseModel):
    preferred_tags: list[str] = []
    available_tags: list[str] = VALID_TAGS

    model_config = ConfigDict(from_attributes=True)
