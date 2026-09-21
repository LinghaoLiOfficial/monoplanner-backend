from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UXWireframeRegion(StrictModel):
    region_name: str
    region_purpose: str
    content_elements: list[str] = Field(default_factory=list)


class UXScreen(StrictModel):
    screen_name: str
    screen_purpose: str
    information_priority: list[str] = Field(default_factory=list)
    interaction_regions: list[UXWireframeRegion] = Field(default_factory=list)


class UXFlowBranch(StrictModel):
    branch_status: Literal["success", "error", "blocked", "empty", "next_action"]
    branch_description: str
    system_feedback: str


class UXElementReference(StrictModel):
    screen: str
    region: str
    element: str


class UXFlowStep(StrictModel):
    step_order: int
    involved_elements: list[UXElementReference] = Field(default_factory=list)
    system_feedback: str
    step_results: list[UXFlowBranch] = Field(default_factory=list)


class UXBusinessFlow(StrictModel):
    flow_name: str
    flow_goal: str
    primary_actor: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[UXFlowStep] = Field(default_factory=list)


class UXDesignContent(StrictModel):
    version_summary: str
    low_fidelity_screen_structure: list[UXScreen] = Field(default_factory=list)
    business_flows: list[UXBusinessFlow] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class UXDesignOutput(StrictModel):
    title: str
    summary: str
    content: UXDesignContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
