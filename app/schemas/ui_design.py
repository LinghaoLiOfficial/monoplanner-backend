from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UIDesignRead(BaseModel):
    id: UUID
    project_id: UUID
    version: int
    title: str
    summary: str | None = None
    content: dict[str, Any]
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)
    source_requirement_id: UUID | None = None
    source_story_id: UUID | None = None
    change_set_id: UUID | None = None
    generation_run_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UIDesignUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    content: dict[str, Any] | None = None
