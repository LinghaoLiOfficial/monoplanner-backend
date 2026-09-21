from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrontendEnvironmentVariable(StrictModel):
    variable_name: str
    variable_description: str
    default_value: str


class FrontendRouteDefinition(StrictModel):
    route_name: str
    route_path: str
    route_params: list[str] = Field(default_factory=list)
    route_target_component: str


class FrontendDirectoryEntry(StrictModel):
    path: str
    purpose: str


class FrontendDependencyPackage(StrictModel):
    package_name: str
    package_description: str


class FrontendPageCodeLogic(StrictModel):
    target: str
    logic_description: str


class FrontendInterfaceDefinition(StrictModel):
    interface_name: str
    interface_description: str


class FrontendPagesContent(StrictModel):
    version_summary: str
    environment_variables: list[FrontendEnvironmentVariable] = Field(default_factory=list)
    route_definitions: list[FrontendRouteDefinition] = Field(default_factory=list)
    directory_structure: list[FrontendDirectoryEntry] = Field(default_factory=list)
    layout_library: str = ""
    component_library: str = ""
    dependency_package_management: list[FrontendDependencyPackage] = Field(default_factory=list)
    page_code_logic: list[FrontendPageCodeLogic] = Field(default_factory=list)
    frontend_interfaces: list[FrontendInterfaceDefinition] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class FrontendPagesOutput(StrictModel):
    title: str
    summary: str
    content: FrontendPagesContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
