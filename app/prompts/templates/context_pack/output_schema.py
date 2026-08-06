from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextPackContent(BaseModel):
    role: str
    goal: str
    included_context: dict[str, Any]
    task_boundaries: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    expected_output: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    do_not_do: list[str] = Field(default_factory=list)


class ContextPackItem(BaseModel):
    role: Literal["frontend_engineer", "backend_engineer"]
    title: str
    summary: str
    content: ContextPackContent
    prompt_text: str


class ContextPackOutput(BaseModel):
    packs: list[ContextPackItem]

