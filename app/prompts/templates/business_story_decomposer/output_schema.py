from typing import Any, Literal

from pydantic import BaseModel, Field

BusinessStoryPriority = Literal["p1_must", "p2_should", "p3_could", "p4_wont"]
ImplementationScope = Literal["frontend_only", "backend_only", "fullstack", "non_code"]


class BusinessStoryItem(BaseModel):
    title: str
    priority: BusinessStoryPriority
    implementation_scope: ImplementationScope = "fullstack"
    affected_layers: list[str] = Field(default_factory=list)
    user_story: str
    business_scope: dict[str, list[str]]
    data_rules: list[dict[str, Any]]
    acceptance_criteria: list[str]
    vertical_slice_note: str | None = None
    depends_on: list[Any] = Field(default_factory=list)
    source_requirement_ids: list[str] = Field(default_factory=list)
    execution_notes: str | None = None


class BusinessStoryDecompositionOutput(BaseModel):
    stories: list[BusinessStoryItem]

