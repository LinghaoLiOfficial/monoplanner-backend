from typing import Literal

from pydantic import BaseModel, Field


class ApiContractField(BaseModel):
    name: str
    type: str
    required: bool = False
    description: str = ""


class ApiContractSchema(BaseModel):
    name: str
    fields: list[ApiContractField]


class ApiContractEndpoint(BaseModel):
    method: Literal["GET", "POST", "PATCH", "PUT", "DELETE"]
    path: str
    operation_id: str
    purpose: str
    request_body: str | None = None
    response_body: str | None = None
    auth_required: bool = True
    errors: list[str] = Field(default_factory=list)


class ApiContractResource(BaseModel):
    name: str
    description: str = ""
    endpoints: list[ApiContractEndpoint]


class ApiErrorModel(BaseModel):
    name: str = "ApiError"
    fields: list[ApiContractField] = Field(default_factory=list)


class ApiContractOutput(BaseModel):
    base_path: str
    resources: list[ApiContractResource]
    schemas: list[ApiContractSchema]
    error_model: ApiErrorModel
    notes: list[str] = Field(default_factory=list)
