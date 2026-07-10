from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ContextPackResponse(BaseModel):
    id: UUID
    project_id: UUID
    blueprint_id: UUID | None
    api_contract_id: UUID | None
    db_model_id: UUID | None
    role: str
    title: str
    summary: str
    content: dict[str, Any]
    prompt_text: str
    format: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContextPackExportResponse(BaseModel):
    filename: str
    content_type: str
    content: str
