from typing import Any

from pydantic import BaseModel, Field


class BackendDirectoryEntry(BaseModel):
    path: str
    purpose: str


class BackendCodeLogicItem(BaseModel):
    target: str
    service_flow: list[str] = Field(default_factory=list)
    validation_logic: list[str] = Field(default_factory=list)
    transaction_handling: list[str] = Field(default_factory=list)
    error_handling: list[str] = Field(default_factory=list)


class BackendUtilityClass(BaseModel):
    name: str
    purpose: str
    usage: list[str] = Field(default_factory=list)


class BackendLLMInteractionTemplate(BaseModel):
    template_name: str
    input_structure: list[str] = Field(default_factory=list)
    output_structure: list[str] = Field(default_factory=list)
    parsing_rules: list[str] = Field(default_factory=list)


class BackendEnvironmentVariable(BaseModel):
    name: str
    purpose: str
    required: bool = True


class BackendDependency(BaseModel):
    package_name: str
    purpose: str
    required: bool = True


class BackendImplementationContent(BaseModel):
    version_summary: str
    directory_structure: list[BackendDirectoryEntry] = Field(default_factory=list)
    code_logic: list[BackendCodeLogicItem] = Field(default_factory=list)
    utility_classes: list[BackendUtilityClass] = Field(default_factory=list)
    llm_interaction_templates: list[BackendLLMInteractionTemplate] = Field(
        default_factory=list
    )
    environment_variables: list[BackendEnvironmentVariable] = Field(default_factory=list)
    dependencies: list[BackendDependency] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class BackendImplementationOutput(BaseModel):
    title: str
    summary: str
    content: BackendImplementationContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
