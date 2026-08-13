from typing import Any

from pydantic import BaseModel, Field


class FrontendRouteDefinition(BaseModel):
    path: str
    page_name: str
    dynamic_params: list[str] = Field(default_factory=list)
    permission_requirement: str


class FrontendDirectoryEntry(BaseModel):
    path: str
    purpose: str


class FrontendCodeLogicItem(BaseModel):
    target: str
    state_management: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    data_flow: list[str] = Field(default_factory=list)
    error_handling: list[str] = Field(default_factory=list)


class FrontendEnvironmentVariable(BaseModel):
    name: str
    purpose: str
    required: bool = True


class FrontendDependency(BaseModel):
    package_name: str
    purpose: str
    required: bool = True


class FrontendPagesContent(BaseModel):
    version_summary: str
    route_definitions: list[FrontendRouteDefinition] = Field(default_factory=list)
    directory_structure: list[FrontendDirectoryEntry] = Field(default_factory=list)
    code_logic: list[FrontendCodeLogicItem] = Field(default_factory=list)
    environment_variables: list[FrontendEnvironmentVariable] = Field(default_factory=list)
    design_theme: list[str] = Field(default_factory=list)
    dependencies: list[FrontendDependency] = Field(default_factory=list)
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
