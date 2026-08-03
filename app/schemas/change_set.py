from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChangeSetStatus = Literal["draft", "ready", "applied", "discarded", "failed"]
ImplementationScope = Literal["frontend_only", "backend_only", "fullstack", "non_code"]


class ChangeSetRead(BaseModel):
    id: UUID
    project_id: UUID
    version: int
    title: str
    status: ChangeSetStatus
    implementation_scope: ImplementationScope
    affected_layers: list[str] = Field(default_factory=list)
    impact_summary: str | None = None
    module_changes: dict[str, Any] = Field(default_factory=dict)
    risks: list[Any] = Field(default_factory=list)
    open_questions: list[Any] = Field(default_factory=list)
    recommended_prompt_strategy: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    diff_from_previous: dict[str, Any] = Field(default_factory=dict)
    source_requirement_id: UUID | None = None
    source_story_id: UUID | None = None
    generation_run_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeSetUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: ChangeSetStatus | None = None
    implementation_scope: ImplementationScope | None = None
    affected_layers: list[str] | None = None
    impact_summary: str | None = None
    module_changes: dict[str, Any] | None = None
    risks: list[Any] | None = None
    open_questions: list[Any] | None = None
    recommended_prompt_strategy: dict[str, Any] | None = None
    summary: str | None = None
    content: dict[str, Any] | None = None
    diff_from_previous: dict[str, Any] | None = None
