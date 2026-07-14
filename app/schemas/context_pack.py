from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design_asset import DesignAssetUpdate


class ContextPackResponse(BaseModel):
    id: UUID
    project_id: UUID
    blueprint_id: UUID | None
    api_contract_id: UUID | None
    db_model_id: UUID | None
    version: int = 1
    source_requirement_id: UUID | None = None
    source_story_id: UUID | None = None
    change_set_id: UUID | None = None
    generation_run_id: UUID | None = None
    role: str
    title: str
    summary: str
    content: dict[str, Any]
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)
    prompt_text: str
    format: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContextPackExportResponse(BaseModel):
    filename: str
    content_type: str
    content: str


class ContextPackUpdate(DesignAssetUpdate):
    role: str | None = None
    prompt_text: str | None = None
    format: str | None = None
