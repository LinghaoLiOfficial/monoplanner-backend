from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["user", "vip-plus", "vip-pro", "vip-pro-max", "admin"]
ManageableUserRole = Literal["user", "vip-plus", "vip-pro", "vip-pro-max"]


class SendEmailVerificationRequest(BaseModel):
    email: EmailStr


class SendEmailVerificationResponse(BaseModel):
    message: str
    expires_in_minutes: int
    resend_after_seconds: int


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    verification_code: str = Field(min_length=6, max_length=6)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    username: str
    display_name: str | None
    role: UserRole
    is_active: bool
    is_email_verified: bool
    avatar_seed: str
    avatar_bg_color: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthUserResponse(BaseModel):
    user: UserRead


class LoginResponse(AuthUserResponse):
    pass


class UpdateMeRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    display_name: str | None = Field(default=None, max_length=100)


class AdminUserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    display_name: str | None = Field(default=None, max_length=100)
    role: ManageableUserRole | None = None
    is_active: bool | None = None


class TokenPlaceholder(BaseModel):
    access_token: str
    token_type: str = "bearer"
