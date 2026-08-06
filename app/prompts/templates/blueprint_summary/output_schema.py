from typing import Any

from pydantic import BaseModel, Field


class BlueprintSummarySection(BaseModel):
    pass


class BlueprintSummaryOutput(BaseModel):
    project: dict[str, Any]
    current_product_scope: dict[str, Any]
    business_capabilities: list[Any] = Field(default_factory=list)
    ux_summary: dict[str, Any]
    ui_summary: dict[str, Any]
    frontend_summary: dict[str, Any]
    backend_summary: dict[str, Any]
    architecture_notes: list[Any] = Field(default_factory=list)
    risks: list[Any] = Field(default_factory=list)
    open_questions: list[Any] = Field(default_factory=list)
    version_summary: str

