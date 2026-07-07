from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TemplateItemCreate(BaseModel):
    key: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TemplateItemRead(BaseModel):
    id: int
    key: str
    title: str
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
