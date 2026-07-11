from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.project import Project
    from app.models.requirement import Requirement

json_type = JSON().with_variant(JSONB, "postgresql")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

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
    run_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    progress: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    output_snapshot: Mapped[dict[str, Any] | None] = mapped_column(json_type, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
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
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="generation_runs")
    requirement: Mapped[Requirement | None] = relationship(back_populates="generation_runs")
    business_requirement_stories: Mapped[list[BusinessRequirementStory]] = relationship(
        back_populates="generation_run"
    )
