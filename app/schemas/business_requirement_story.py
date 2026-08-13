from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

BusinessStoryPriority = Literal["p1_must", "p2_should", "p3_could", "p4_wont"]
BusinessStoryStatus = Literal[
    "draft",
    "ready",
    "selected",
    "applied",
    "implemented",
    "verified",
    "deferred",
    "in_progress",
    "done",
]
ImplementationScope = Literal["frontend_only", "backend_only", "fullstack", "non_code"]


class BusinessRequirementStoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    requirement_id: UUID | None
    generation_run_id: UUID | None
    title: str
    priority: BusinessStoryPriority
    status: BusinessStoryStatus
    implementation_scope: ImplementationScope = "fullstack"
    affected_layers: list[str] = Field(default_factory=list)
    user_story: str
    business_scope: dict[str, Any]
    data_rules: list[dict[str, Any]]
    acceptance_criteria: list[str]
    vertical_slice_note: str | None
    depends_on: list[Any] = Field(default_factory=list)
    source_requirement_ids: list[str] = Field(default_factory=list)
    execution_notes: str | None = None
    source_requirement_excerpt: str | None
    sort_order: int
    is_current: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def requirement_name(self) -> str:
        return self.title

    @computed_field
    @property
    def impact_scope(self) -> dict[str, Any]:
        return {
            "implementation_scope": self.implementation_scope,
            "affected_layers": self.affected_layers,
        }

    @computed_field
    @property
    def included_scope(self) -> list[Any]:
        included = (
            self.business_scope.get("included") if isinstance(self.business_scope, dict) else []
        )
        return included if isinstance(included, list) else []

    @computed_field
    @property
    def excluded_scope(self) -> list[Any]:
        excluded = (
            self.business_scope.get("excluded") if isinstance(self.business_scope, dict) else []
        )
        return excluded if isinstance(excluded, list) else []

    @computed_field
    @property
    def execution_note(self) -> str | None:
        return self.execution_notes


class BusinessRequirementStoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    priority: BusinessStoryPriority | None = None
    status: BusinessStoryStatus | None = None
    implementation_scope: ImplementationScope | None = None
    affected_layers: list[str] | None = None
    user_story: str | None = Field(default=None, min_length=1)
    business_scope: dict[str, Any] | None = None
    data_rules: list[dict[str, Any]] | None = None
    acceptance_criteria: list[str] | None = None
    vertical_slice_note: str | None = None
    depends_on: list[Any] | None = None
    source_requirement_ids: list[str] | None = None
    execution_notes: str | None = None
    source_requirement_excerpt: str | None = None
    sort_order: int | None = None


class GenerateBusinessRequirementStoriesRequest(BaseModel):
    requirement_id: UUID | None = None
    overwrite: bool = False


class GenerateBusinessRequirementStoriesResponse(BaseModel):
    items: list[BusinessRequirementStoryResponse]
