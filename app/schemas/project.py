from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    target_frontend_stack: str | None = None
    target_backend_stack: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    target_frontend_stack: str | None = None
    target_backend_stack: str | None = None


class ProjectRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    description: str | None
    target_frontend_stack: str = DEFAULT_FRONTEND_STACK
    target_backend_stack: str = DEFAULT_BACKEND_STACK
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("target_frontend_stack", mode="before")
    @classmethod
    def default_frontend_stack(cls, value: str | None) -> str:
        return normalize_stack(value, DEFAULT_FRONTEND_STACK)

    @field_validator("target_backend_stack", mode="before")
    @classmethod
    def default_backend_stack(cls, value: str | None) -> str:
        return normalize_stack(value, DEFAULT_BACKEND_STACK)
