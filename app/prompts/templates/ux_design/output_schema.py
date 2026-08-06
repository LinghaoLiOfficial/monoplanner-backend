from typing import Any, Literal

from pydantic import BaseModel, Field


class UXWireframeRegion(BaseModel):
    region_name: str
    region_purpose: str
    content_elements: list[str] = Field(default_factory=list)


class UXScreen(BaseModel):
    screen_name: str
    screen_purpose: str
    information_priority: list[str] = Field(default_factory=list)
    interaction_regions: list[UXWireframeRegion] = Field(default_factory=list)


class UXFlowBranch(BaseModel):
    branch_status: Literal["success", "error", "blocked", "empty", "next_action"]
    branch_description: str
    system_feedback: str


class UXFlowStep(BaseModel):
    step_order: int
    involved_elements: list[str] = Field(default_factory=list)
    user_action: str
    system_feedback: str
    branches: list[UXFlowBranch] = Field(default_factory=list)


class UXBusinessFlow(BaseModel):
    flow_name: str
    flow_goal: str
    primary_actor: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[UXFlowStep] = Field(default_factory=list)
    ux_notes: list[str] = Field(default_factory=list)


class UXDesignContent(BaseModel):
    version_summary: str
    low_fidelity_screen_structure: list[UXScreen] = Field(default_factory=list)
    business_flows: list[UXBusinessFlow] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class UXDesignOutput(BaseModel):
    title: str
    summary: str
    content: UXDesignContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
