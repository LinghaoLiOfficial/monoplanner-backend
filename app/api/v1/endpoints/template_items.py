from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.template_item import TemplateItemCreate, TemplateItemRead
from app.services.template_item_service import create_template_item_or_raise, list_template_items

router = APIRouter(prefix="/template-items")
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/", response_model=ApiResponse[PaginatedResponse[TemplateItemRead]])
def get_template_items(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[PaginatedResponse[TemplateItemRead]]:
    data = list_template_items(db, page=page, page_size=page_size)
    return ApiResponse(data=data)


@router.post("/", response_model=ApiResponse[TemplateItemRead], status_code=status.HTTP_201_CREATED)
def create_template_item(
    db: DbSession, payload: TemplateItemCreate
) -> ApiResponse[TemplateItemRead]:
    item = create_template_item_or_raise(db, payload)
    return ApiResponse(data=TemplateItemRead.model_validate(item))
