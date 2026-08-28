from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiContractError(BaseModel):
    status_code: int
    error_code: str
    error_message: str
    recovery_suggestion: str = ""


class ApiContractEndpoint(BaseModel):
    http_method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
    endpoint_path: str
    endpoint_purpose: str
    requires_auth: bool = True
    request_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    error_model: list[ApiContractError] = Field(default_factory=list)


class ApiContractResourceGroup(BaseModel):
    group_name: str
    group_purpose: str
    endpoints: list[ApiContractEndpoint] = Field(default_factory=list)


class ApiContractContent(BaseModel):
    version_summary: str
    api_base_path: str
    api_resource_groups: list[ApiContractResourceGroup] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class ApiContractAssetOutput(BaseModel):
    title: str
    summary: str
    content: ApiContractContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
