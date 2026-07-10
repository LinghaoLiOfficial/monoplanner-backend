from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiContractDraftResponse(BaseModel):
    id: UUID
    project_id: UUID
    blueprint_id: UUID
    version: int
    title: str
    summary: str
    base_path: str
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
