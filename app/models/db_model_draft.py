from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.blueprint import ProjectBlueprint
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.change_set import ChangeSet
    from app.models.context_pack import ContextPack
    from app.models.generation_run import GenerationRun
    from app.models.project import Project
    from app.models.requirement import Requirement

json_type = JSON().with_variant(JSONB, "postgresql")


class DbModelDraft(Base):
    __tablename__ = "db_model_drafts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blueprint_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_blueprints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_requirement_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_story_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("business_requirement_stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    change_set_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("change_sets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generation_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text(), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
    diff_from_previous: Mapped[dict[str, Any]] = mapped_column(
        json_type, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="db_model_drafts")
    blueprint: Mapped[ProjectBlueprint] = relationship()
    source_requirement: Mapped[Requirement | None] = relationship()
    source_story: Mapped[BusinessRequirementStory | None] = relationship()
    change_set: Mapped[ChangeSet | None] = relationship()
    generation_run: Mapped[GenerationRun | None] = relationship()
    context_packs: Mapped[list[ContextPack]] = relationship(back_populates="db_model")
