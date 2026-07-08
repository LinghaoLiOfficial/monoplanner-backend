from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerationRunRead(BaseModel):
    id: UUID
    project_id: UUID
    run_type: str
    status: str
    input_snapshot: dict[str, Any] | None
    output_snapshot: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
