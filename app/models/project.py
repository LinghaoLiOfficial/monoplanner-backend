from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.api_contract import ApiContractDraft
    from app.models.backend_service_design import BackendServiceDesign
    from app.models.backend_tooling import BackendTooling
    from app.models.blueprint import ProjectBlueprint
    from app.models.business_requirement_story import BusinessRequirementStory
    from app.models.change_set import ChangeSet
    from app.models.context_pack import ContextPack
    from app.models.db_model_draft import DbModelDraft
    from app.models.frontend_page_structure import FrontendPageStructure
    from app.models.frontend_tooling import FrontendTooling
    from app.models.generation_run import GenerationRun
    from app.models.requirement import Requirement
    from app.models.ui_design import UIDesign
    from app.models.user import User
    from app.models.ux_design import UXDesign

json_type = JSON().with_variant(JSONB, "postgresql")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner_user_id", "name", name="uq_projects_owner_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    target_frontend_stack: Mapped[str] = mapped_column(
        Text(), nullable=False, default=DEFAULT_FRONTEND_STACK
    )
    target_backend_stack: Mapped[str] = mapped_column(
        Text(), nullable=False, default=DEFAULT_BACKEND_STACK
    )
    target_frontend_stack_items: Mapped[list[dict[str, Any]]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    target_backend_stack_items: Mapped[list[dict[str, Any]]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    target_stacks_configured: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=False, server_default="false"
    )
    global_constraints: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    coding_preferences: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
    )
    prompt_preferences: Mapped[list[Any]] = mapped_column(
        json_type, nullable=False, default=list, server_default="[]"
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

    owner: Mapped[User] = relationship(back_populates="projects")
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
    change_sets: Mapped[list[ChangeSet]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    frontend_page_structures: Mapped[list[FrontendPageStructure]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    frontend_toolings: Mapped[list[FrontendTooling]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    backend_service_designs: Mapped[list[BackendServiceDesign]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    backend_toolings: Mapped[list[BackendTooling]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    ux_designs: Mapped[list[UXDesign]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
    ui_designs: Mapped[list[UIDesign]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
