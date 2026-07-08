from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectBlueprintRead(BaseModel):
    id: UUID
    project_id: UUID
    version: int
    title: str
    summary: str
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
