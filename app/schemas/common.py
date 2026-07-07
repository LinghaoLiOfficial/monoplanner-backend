from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ApiStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class ErrorResponse(BaseModel):
    status: ApiStatus = ApiStatus.ERROR
    code: str
    message: str


class ApiResponse[DataT](BaseModel):
    status: ApiStatus = ApiStatus.SUCCESS
    data: DataT
    message: str | None = None


class PaginationMeta(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PaginatedResponse[DataT](BaseModel):
    items: list[DataT]
    pagination: PaginationMeta


class MessageResponse(BaseModel):
    message: str

    model_config = ConfigDict(from_attributes=True)
