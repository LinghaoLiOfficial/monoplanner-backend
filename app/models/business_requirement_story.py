from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.generation_run import GenerationRun
    from app.models.project import Project
    from app.models.requirement import Requirement

json_type = JSON().with_variant(JSONB, "postgresql")


class BusinessRequirementStory(Base):
    __tablename__ = "business_requirement_stories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("requirements.id", ondelete="SET NULL"),
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
    priority: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    implementation_scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default="fullstack", server_default="fullstack"
    )
    affected_layers: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    user_story: Mapped[str] = mapped_column(Text(), nullable=False)
    business_scope: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False)
    data_rules: Mapped[list[dict[str, Any]]] = mapped_column(json_type, nullable=False)
    acceptance_criteria: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    vertical_slice_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    depends_on: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    source_requirement_ids: Mapped[list[str]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    execution_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_requirement_excerpt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_current: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True, server_default="true", index=True
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

    project: Mapped[Project] = relationship(back_populates="business_requirement_stories")
    requirement: Mapped[Requirement | None] = relationship(
        back_populates="business_requirement_stories"
    )
    generation_run: Mapped[GenerationRun | None] = relationship(
        back_populates="business_requirement_stories"
    )
