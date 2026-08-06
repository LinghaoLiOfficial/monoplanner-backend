from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_contract import ApiContractDraft
from app.models.backend_service_design import BackendImplementation
from app.models.backend_tooling import BackendTooling
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.frontend_page_structure import FrontendImplementation
from app.models.frontend_tooling import FrontendTooling
from app.models.project import Project
from app.models.ui_design import UIDesign
from app.models.ux_design import UXDesign

ASSET_MODELS_BY_LAYER = {
    "ux_design": UXDesign,
    "ui_design": UIDesign,
    "frontend_pages": FrontendImplementation,
    "frontend_tools": FrontendTooling,
    "api_contract": ApiContractDraft,
    "backend_services": BackendImplementation,
    "backend_tools": BackendTooling,
    "database_models": DbModelDraft,
}


def project_config_snapshot(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "target_frontend_stack": project.target_frontend_stack,
        "target_backend_stack": project.target_backend_stack,
        "global_constraints": project.global_constraints,
        "coding_preferences": project.coding_preferences,
        "prompt_preferences": project.prompt_preferences,
    }


def story_snapshot(story: BusinessRequirementStory | None) -> dict[str, Any] | None:
    if story is None:
        return None
    return {
        "id": str(story.id),
        "project_id": str(story.project_id),
        "requirement_id": str(story.requirement_id) if story.requirement_id else None,
        "title": story.title,
        "priority": story.priority,
        "status": story.status,
        "implementation_scope": story.implementation_scope,
        "affected_layers": story.affected_layers,
        "user_story": story.user_story,
        "business_scope": story.business_scope,
        "data_rules": story.data_rules,
        "acceptance_criteria": story.acceptance_criteria,
        "depends_on": story.depends_on,
        "source_requirement_ids": story.source_requirement_ids,
        "execution_notes": story.execution_notes,
    }


def asset_snapshot(asset: Any | None) -> dict[str, Any] | None:
    if asset is None:
        return None
    return {
        "id": str(asset.id),
        "version": getattr(asset, "version", None),
        "title": getattr(asset, "title", None),
        "summary": getattr(asset, "summary", None),
        "content": getattr(asset, "content", None),
        "diff_from_previous": getattr(asset, "diff_from_previous", None),
        "created_at": asset.created_at.isoformat() if getattr(asset, "created_at", None) else None,
    }


def change_set_snapshot(change_set: Any) -> dict[str, Any]:
    return {
        "id": str(change_set.id),
        "project_id": str(change_set.project_id),
        "version": change_set.version,
        "title": change_set.title,
        "status": change_set.status,
        "implementation_scope": change_set.implementation_scope,
        "affected_layers": change_set.affected_layers,
        "impact_summary": change_set.impact_summary,
        "module_changes": change_set.module_changes,
        "risks": change_set.risks,
        "open_questions": change_set.open_questions,
        "recommended_prompt_strategy": change_set.recommended_prompt_strategy,
        "content": change_set.content,
        "diff_from_previous": change_set.diff_from_previous,
    }


def latest_asset(db: Session, model: type[Any], project_id: UUID) -> Any | None:
    return db.scalar(
        select(model)
        .where(model.project_id == project_id)
        .order_by(model.version.desc(), model.created_at.desc())
        .limit(1)
    )


def next_asset_version(db: Session, model: type[Any], project_id: UUID) -> int:
    latest = latest_asset(db, model, project_id)
    return 1 if latest is None else int(latest.version) + 1


def latest_assets_snapshot(db: Session, project_id: UUID) -> dict[str, Any]:
    assets = {
        layer: asset_snapshot(latest_asset(db, model, project_id))
        for layer, model in ASSET_MODELS_BY_LAYER.items()
    }
    assets["project_blueprint"] = asset_snapshot(latest_asset(db, ProjectBlueprint, project_id))
    assets["prompt_assets"] = [
        asset_snapshot(item)
        for item in db.scalars(
            select(ContextPack)
            .where(ContextPack.project_id == project_id)
            .order_by(ContextPack.created_at.desc())
            .limit(5)
        )
    ]
    return assets


def business_stories_snapshot(db: Session, project_id: UUID) -> list[dict[str, Any]]:
    return [
        story_snapshot(story) or {}
        for story in db.scalars(
            select(BusinessRequirementStory)
            .where(BusinessRequirementStory.project_id == project_id)
            .order_by(
                BusinessRequirementStory.sort_order.asc(),
                BusinessRequirementStory.created_at.asc(),
            )
        )
    ]
