from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import OpenAICompatibleLLMClient
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import build_change_set_prompt
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.services.llm_orchestration_runtime import generate_orchestration_json
from app.services.orchestration_context import (
    latest_assets_snapshot,
    project_config_snapshot,
    story_snapshot,
)
from app.services.orchestration_validators import validate_change_set_payload
from app.services.project_service import ProjectService

RUN_TYPE = "generate_change_set"
CHILD_RUN_TYPE = "generate_change_set_asset"
LAYER_GENERATION_ORDER = [
    "ux_design",
    "ui_design",
    "frontend_pages",
    "api_contract",
    "backend_services",
    "database_models",
]


class ChangeSetGenerationService:
    def __init__(
        self,
        db: Session,
        llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    ) -> None:
        self.db = db
        self.llm_client_factory = llm_client_factory

    def execute_asset_run(self, run: GenerationRun) -> ChangeSet:
        payload = run.queue_payload or {}
        story_id = payload.get("story_id")
        source_change_set_id = payload.get("source_change_set_id")
        layer = run.asset_layer or payload.get("layer")
        if not isinstance(layer, str) or not layer:
            raise ValueError("ChangeSet asset run requires an asset layer.")
        story = self._resolve_story(story_id, source_change_set_id)
        project = ProjectService(self.db).get_project(story.project_id)
        run.status = "running"
        run.progress = max(run.progress, 10)
        run.message = "正在生成变更集..."
        run.started_at = run.started_at or datetime.now(UTC)
        run.input_snapshot = {
            "project_id": str(project.id),
            "story_id": str(story.id),
            "source_change_set_id": str(source_change_set_id) if source_change_set_id else None,
        }
        self.db.add(run)
        self.db.commit()

        batch_id = UUID(str(payload["batch_id"])) if payload.get("batch_id") else uuid4()
        project_config = project_config_snapshot(project)
        selected_story = story_snapshot(story) or {}
        current_assets = latest_assets_snapshot(self.db, project.id)
        prompt = build_change_set_prompt(
            layer=layer,
            project_config=project_config,
            selected_story=selected_story,
            current_assets={
                "layer": layer,
                "current_layer_asset": current_assets.get(layer),
                "related_assets": current_assets,
            },
        )
        parsed = generate_orchestration_json(
            prompt.system,
            prompt.user,
            response_model=ChangeSetOutput,
            llm_client_factory=self.llm_client_factory,
        )
        parsed = _narrow_change_set_to_layer(parsed, layer)
        validated = validate_change_set_payload(parsed, expected_layer=layer)
        content = dict(validated["content"])
        content["layer"] = layer
        content["batch_id"] = str(batch_id)
        change_set = ChangeSet(
            project_id=project.id,
            source_requirement_id=story.requirement_id,
            source_story_id=story.id,
            generation_run_id=run.id,
            version=self._next_version(project.id, layer),
            layer=layer,
            batch_id=batch_id,
            content=content,
            **{key: value for key, value in validated.items() if key != "content"},
        )
        self.db.add(change_set)
        self.db.flush()
        run.status = "completed"
        run.progress = 100
        run.message = f"{layer} 变更集已生成。"
        run.output_snapshot = {
            "batch_id": str(batch_id),
            "change_set_ids": [str(change_set.id)],
            "affected_layers": [layer],
            "counts": {"change_sets": 1},
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set

    def execute_run(self, run: GenerationRun) -> ChangeSet:
        """Backward-compatible single-layer entry point for legacy callers."""
        return self.execute_asset_run(run)

    def _resolve_story(
        self,
        story_id: object,
        source_change_set_id: object,
    ) -> BusinessRequirementStory:
        if story_id:
            story = self.db.get(BusinessRequirementStory, UUID(str(story_id)))
        elif source_change_set_id:
            change_set = self.db.get(ChangeSet, UUID(str(source_change_set_id)))
            story = (
                self.db.get(BusinessRequirementStory, change_set.source_story_id)
                if change_set and change_set.source_story_id
                else None
            )
        else:
            story = None
        if story is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business requirement story not found.",
            )
        return story

    def _next_version(self, project_id: UUID, layer: str) -> int:
        existing_change_sets = self.db.scalars(
            select(ChangeSet)
            .where(ChangeSet.project_id == project_id)
            .order_by(ChangeSet.version.desc())
        ).all()
        layer_versions = [
            change_set.version
            for change_set in existing_change_sets
            if _change_set_layer_key(change_set) == layer
        ]
        return 1 if not layer_versions else max(layer_versions) + 1


def _ordered_story_layers(affected_layers: list[str]) -> list[str]:
    affected = set(affected_layers)
    return [layer for layer in LAYER_GENERATION_ORDER if layer in affected]


def _ordered_generation_layers(
    story_layers: list[str],
    source_change_set: ChangeSet | None,
) -> list[str]:
    if source_change_set is not None:
        if source_change_set.layer in LAYER_GENERATION_ORDER:
            return [source_change_set.layer]
        source_layers = _ordered_story_layers(source_change_set.affected_layers)
        if source_layers:
            return source_layers
    return _ordered_story_layers(story_layers)


def _change_set_layer_key(change_set: ChangeSet) -> str | None:
    return change_set.layer or next(iter(change_set.affected_layers or []), None)


def _narrow_change_set_to_layer(parsed: dict[str, Any], layer: str) -> dict[str, Any]:
    narrowed = dict(parsed)
    module_changes = narrowed.get("module_changes")
    if isinstance(module_changes, dict):
        narrowed["module_changes"] = {layer: module_changes.get(layer, {})}
    narrowed["affected_layers"] = [layer]
    content = narrowed.get("content") if isinstance(narrowed.get("content"), dict) else {}
    narrowed["content"] = {**content, "layer": layer}
    return narrowed
