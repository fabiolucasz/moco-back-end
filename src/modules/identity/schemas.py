import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="Minimum 8 characters password"
    )
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")


class UserResponse(BaseModel):
    """Schema for returning user profile data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class LoginRequest(BaseModel):
    """Schema for local login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Schema for requesting a new token pair using a refresh token."""

    refresh_token: str


class GoogleLoginRequest(BaseModel):
    """Schema for Google OAuth id_token login."""

    id_token: str
