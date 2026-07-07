from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ErrorCode
from app.crud.template_item import (
    create_template_item,
    get_template_item_by_key,
    get_template_items,
)
from app.models.template_item import TemplateItem
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.template_item import TemplateItemCreate, TemplateItemRead


async def list_template_items(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
) -> PaginatedResponse[TemplateItemRead]:
    offset = (page - 1) * page_size
    items, total = await get_template_items(db, offset=offset, limit=page_size)
    total_pages = ceil(total / page_size) if total else 0

    return PaginatedResponse[TemplateItemRead](
        items=[TemplateItemRead.model_validate(item) for item in items],
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


async def create_template_item_or_raise(
    db: AsyncSession,
    payload: TemplateItemCreate,
) -> TemplateItem:
    existing_item = await get_template_item_by_key(db, payload.key)
    if existing_item is not None:
        raise AppError(
            status_code=409,
            code=ErrorCode.CONFLICT,
            message="Template item key already exists.",
        )

    return await create_template_item(db, payload)
