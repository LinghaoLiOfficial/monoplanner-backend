from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.generation_run import BusinessStoryGenerationStatus


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
    created_at: datetime
    updated_at: datetime
    business_story_generation: BusinessStoryGenerationStatus | None = None

    model_config = ConfigDict(from_attributes=True)
