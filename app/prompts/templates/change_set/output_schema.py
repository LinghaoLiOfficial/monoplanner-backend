from typing import Any, Literal

from pydantic import BaseModel, Field

ORDERED_AFFECTED_LAYERS = [
    "ux_design",
    "ui_design",
    "frontend_pages",
    "api_contract",
    "backend_services",
    "database_models",
]


class ModuleChangeBucket(BaseModel):
    added: list[Any] = Field(default_factory=list)
    modified: list[Any] = Field(default_factory=list)
    removed: list[Any] = Field(default_factory=list)
    unchanged: list[Any] = Field(default_factory=list)


class ChangeSetOutput(BaseModel):
    title: str
    implementation_scope: Literal["frontend_only", "backend_only", "fullstack", "non_code"]
    affected_layers: list[str] = Field(default_factory=list)
    impact_summary: str
    module_changes: dict[str, ModuleChangeBucket]
    risks: list[Any] = Field(default_factory=list)
    open_questions: list[Any] = Field(default_factory=list)
    recommended_prompt_strategy: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
