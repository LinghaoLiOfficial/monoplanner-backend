from typing import Any, Literal

from pydantic import BaseModel, Field


class PromptPackSection(BaseModel):
    needed: bool = True
    title: str
    prompt: str
    affected_files: list[str] = Field(default_factory=list)
    do_not_modify: list[str] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)


class PromptPackOutput(BaseModel):
    batch_summary: str
    implementation_scope: Literal["frontend_only", "backend_only", "fullstack", "non_code"]
    frontend_prompt: PromptPackSection
    backend_prompt: PromptPackSection
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    execution_order: list[Any] = Field(default_factory=list)
    acceptance_checklist: list[Any] = Field(default_factory=list)
    rollback_notes: list[Any] = Field(default_factory=list)

