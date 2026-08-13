from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiErrorCase(BaseModel):
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
    error_model: list[ApiErrorCase] = Field(default_factory=list)


class ApiResourceGroup(BaseModel):
    group_name: str
    group_purpose: str
    endpoints: list[ApiContractEndpoint] = Field(default_factory=list)


class ApiContractOutput(BaseModel):
    api_base_path: str
    api_resource_groups: list[ApiResourceGroup] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
