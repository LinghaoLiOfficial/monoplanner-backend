from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template_item import TemplateItem
from app.schemas.template_item import TemplateItemCreate


async def get_template_items(
    db: AsyncSession,
    *,
    offset: int,
    limit: int,
) -> tuple[list[TemplateItem], int]:
    total = await db.scalar(select(func.count()).select_from(TemplateItem)) or 0
    result = await db.scalars(
        select(TemplateItem).order_by(TemplateItem.id).offset(offset).limit(limit)
    )
    return list(result), total


async def get_template_item_by_key(db: AsyncSession, key: str) -> TemplateItem | None:
    return await db.scalar(select(TemplateItem).where(TemplateItem.key == key))


async def create_template_item(db: AsyncSession, payload: TemplateItemCreate) -> TemplateItem:
    item = TemplateItem(
        key=payload.key,
        title=payload.title,
        description=payload.description,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
