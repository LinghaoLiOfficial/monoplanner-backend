from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerationRunRead(BaseModel):
    id: UUID
    project_id: UUID
    requirement_id: UUID | None = None
    run_type: str
    status: str
    progress: int
    message: str | None = None
    queue_payload: dict[str, Any] | None = None
    input_snapshot: dict[str, Any] | None
    output_snapshot: dict[str, Any] | None
    error_message: str | None
    locked_by: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    queued_at: datetime | None = None
    started_at: datetime | None = None
    locked_at: datetime | None = None
    next_attempt_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class BusinessStoryGenerationStatus(BaseModel):
    run_id: UUID | None = None
    status: str
    progress: int
    message: str | None = None
    error_message: str | None = None
    updated_at: datetime | None = None
