from typing import Any

from pydantic import BaseModel, Field


class FrontendPageItem(BaseModel):
    path: str
    name: str
    purpose: str


class FrontendComponentItem(BaseModel):
    component_id: str
    name: str
    purpose: str
    used_by_pages: list[str] = Field(default_factory=list)
    ux_refs: list[str] = Field(default_factory=list)
    ui_refs: list[str] = Field(default_factory=list)


class FrontendPagesContent(BaseModel):
    version_summary: str
    pages: list[FrontendPageItem] = Field(default_factory=list)
    components: list[FrontendComponentItem] = Field(default_factory=list)
    directory_structure: list[Any] = Field(default_factory=list)
    data_flow: list[Any] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class FrontendPagesOutput(BaseModel):
    title: str
    summary: str
    content: FrontendPagesContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )

