"""User-related Pydantic schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class NotificationPreferences(BaseModel):
    """User notification preferences."""

    email: bool = True
    telegram: bool = True
    intervals: List[int] = Field(default=[180, 90, 30])


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: Optional[str] = None
    preferred_language: str = "ru"


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(min_length=8)
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "viewer"):
            raise ValueError("Role must be 'admin' or 'viewer'")
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    full_name: Optional[str] = None
    preferred_language: Optional[str] = None
    notification_preferences: Optional[NotificationPreferences] = None
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None


class UserPasswordChange(BaseModel):
    """Schema for changing password."""

    current_password: str
    new_password: str = Field(min_length=8)


class UserResponse(UserBase):
    """Schema for user response."""

    id: UUID
    role: str
    is_active: bool
    notification_preferences: NotificationPreferences
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Token refresh request schema."""

    refresh_token: str
