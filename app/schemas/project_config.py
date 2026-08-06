from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack


class ProjectConfigRead(BaseModel):
    id: UUID
    owner_user_id: UUID
    name: str
    description: str | None
    target_frontend_stack: str = DEFAULT_FRONTEND_STACK
    target_backend_stack: str = DEFAULT_BACKEND_STACK
    target_stacks_configured: bool = False
    global_constraints: list[Any] = Field(default_factory=list)
    coding_preferences: list[Any] = Field(default_factory=list)
    prompt_preferences: list[Any] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def project_name(self) -> str:
        return self.name

    @computed_field
    @property
    def project_description(self) -> str | None:
        return self.description

    @computed_field
    @property
    def frontend_tech_stack(self) -> str:
        return self.target_frontend_stack

    @computed_field
    @property
    def backend_tech_stack(self) -> str:
        return self.target_backend_stack

    @computed_field
    @property
    def code_preferences(self) -> list[Any]:
        return self.coding_preferences

    @field_validator("target_frontend_stack", mode="before")
    @classmethod
    def default_frontend_stack(cls, value: str | None) -> str:
        return normalize_stack(value, DEFAULT_FRONTEND_STACK)

    @field_validator("target_backend_stack", mode="before")
    @classmethod
    def default_backend_stack(cls, value: str | None) -> str:
        return normalize_stack(value, DEFAULT_BACKEND_STACK)


class ProjectConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    target_frontend_stack: str | None = None
    target_backend_stack: str | None = None
    global_constraints: list[Any] | None = None
    coding_preferences: list[Any] | None = None
    prompt_preferences: list[Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if "name" not in payload and payload.get("project_name") is not None:
            payload["name"] = payload["project_name"]
        if "description" not in payload and payload.get("project_description") is not None:
            payload["description"] = payload["project_description"]
        if (
            "target_frontend_stack" not in payload
            and payload.get("frontend_tech_stack") is not None
        ):
            payload["target_frontend_stack"] = payload["frontend_tech_stack"]
        if "target_backend_stack" not in payload and payload.get("backend_tech_stack") is not None:
            payload["target_backend_stack"] = payload["backend_tech_stack"]
        if "coding_preferences" not in payload and payload.get("code_preferences") is not None:
            payload["coding_preferences"] = payload["code_preferences"]
        return payload
