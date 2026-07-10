from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.api_contract import ApiContractDraft
    from app.models.blueprint import ProjectBlueprint
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.context_pack import ContextPack
    from app.models.db_model_draft import DbModelDraft
    from app.models.generation_run import GenerationRun
    from app.models.requirement import Requirement

DEFAULT_FRONTEND_STACK = "Next.js + React + TypeScript + Tailwind CSS 4 + Shadcn/ui + pnpm"
DEFAULT_BACKEND_STACK = (
    "Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2.x + Alembic + PostgreSQL + uv"
)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_frontend_stack: Mapped[str] = mapped_column(
        Text(), nullable=False, default=DEFAULT_FRONTEND_STACK
    )
    target_backend_stack: Mapped[str] = mapped_column(
        Text(), nullable=False, default=DEFAULT_BACKEND_STACK
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
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

    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    blueprints: Mapped[list[ProjectBlueprint]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    generation_runs: Mapped[list[GenerationRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    api_contract_drafts: Mapped[list[ApiContractDraft]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    db_model_drafts: Mapped[list[DbModelDraft]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    context_packs: Mapped[list[ContextPack]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    business_requirement_stories: Mapped[list[BusinessRequirementStory]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
