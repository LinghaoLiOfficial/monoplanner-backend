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
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.generation_run import GenerationRun
    from app.models.project import Project
    from app.models.requirement import Requirement

json_type = JSON().with_variant(JSONB, "postgresql")


class ChangeSet(Base):
    __tablename__ = "change_sets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    generation_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    implementation_scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="fullstack", server_default="fullstack"
    )
    affected_layers: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    impact_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    module_changes: Mapped[dict[str, Any]] = mapped_column(
        json_type, nullable=False, default=dict, server_default="{}"
    )
    risks: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    open_questions: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    recommended_prompt_strategy: Mapped[dict[str, Any]] = mapped_column(
        json_type, nullable=False, default=dict, server_default="{}"
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        json_type, nullable=False, default=dict, server_default="{}"
    )
    diff_from_previous: Mapped[dict[str, Any]] = mapped_column(
        json_type, nullable=False, default=dict, server_default="{}"
    )
    summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
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

    project: Mapped[Project] = relationship(back_populates="change_sets")
    source_requirement: Mapped[Requirement | None] = relationship()
    source_story: Mapped[BusinessRequirementStory | None] = relationship()
    generation_run: Mapped[GenerationRun | None] = relationship()
