from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.generation_run import GenerationRun
    from app.models.project import Project


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_text: Mapped[str] = mapped_column(Text(), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh-CN")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="requirements")
    business_requirement_stories: Mapped[list[BusinessRequirementStory]] = relationship(
        back_populates="requirement"
    )
    generation_runs: Mapped[list[GenerationRun]] = relationship(back_populates="requirement")
