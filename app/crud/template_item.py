from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.template_item import TemplateItem
from app.schemas.template_item import TemplateItemCreate


def get_template_items(db: Session, *, offset: int, limit: int) -> tuple[list[TemplateItem], int]:
    total = db.scalar(select(func.count()).select_from(TemplateItem)) or 0
    result = db.scalars(select(TemplateItem).order_by(TemplateItem.id).offset(offset).limit(limit))
    return list(result), total


def get_template_item_by_key(db: Session, key: str) -> TemplateItem | None:
    return db.scalar(select(TemplateItem).where(TemplateItem.key == key))


def create_template_item(db: Session, payload: TemplateItemCreate) -> TemplateItem:
    item = TemplateItem(key=payload.key, title=payload.title, description=payload.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
