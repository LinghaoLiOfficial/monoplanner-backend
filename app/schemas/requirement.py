from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.generation_run import BusinessStoryGenerationStatus

RequirementProgressStatus = Literal["in_progress", "success", "failed"]
RequirementStatus = Literal["pending", "applied", "superseded"]


class RequirementCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    language: str = Field(default="zh-CN", min_length=1, max_length=20)
    source_type: str = Field(default="manual", min_length=1, max_length=50)


class RequirementRead(BaseModel):
    id: UUID
    project_id: UUID
    raw_text: str
    language: str
    source_type: str
    status: RequirementStatus = "pending"
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    progress_status: RequirementProgressStatus = "success"
    progress_label: str = "成功"
    progress_text: str = "更新成功"
    business_story_generation: BusinessStoryGenerationStatus | None = None

    model_config = ConfigDict(from_attributes=True)
