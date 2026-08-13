from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design_asset import DesignAssetUpdate


class DbModelDraftResponse(BaseModel):
    id: UUID
    project_id: UUID
    blueprint_id: UUID | None = None
    version: int
    source_requirement_id: UUID | None = None
    source_story_id: UUID | None = None
    change_set_id: UUID | None = None
    generation_run_id: UUID | None = None
    title: str
    summary: str
    content: dict[str, Any]
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DbModelDraftUpdate(DesignAssetUpdate):
    pass
