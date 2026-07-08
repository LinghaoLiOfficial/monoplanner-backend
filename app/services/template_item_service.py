from math import ceil

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ErrorCode
from app.crud.template_item import (
    create_template_item,
    get_template_item_by_key,
    get_template_items,
)
from app.models.template_item import TemplateItem
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.template_item import TemplateItemCreate, TemplateItemRead


def list_template_items(
    db: Session, *, page: int, page_size: int
) -> PaginatedResponse[TemplateItemRead]:
    offset = (page - 1) * page_size
    items, total = get_template_items(db, offset=offset, limit=page_size)
    total_pages = ceil(total / page_size) if total else 0
    return PaginatedResponse[TemplateItemRead](
        items=[TemplateItemRead.model_validate(item) for item in items],
        pagination=PaginationMeta(
            page=page, page_size=page_size, total=total, total_pages=total_pages
        ),
    )


def create_template_item_or_raise(db: Session, payload: TemplateItemCreate) -> TemplateItem:
    existing_item = get_template_item_by_key(db, payload.key)
    if existing_item is not None:
        raise AppError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            message="Template item key already exists.",
        )
    return create_template_item(db, payload)
