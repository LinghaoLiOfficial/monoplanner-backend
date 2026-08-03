from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.llm.client import OpenAICompatibleLLMClient
from app.models.api_contract import ApiContractDraft
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import (
    SYSTEM_PROMPT,
    build_blueprint_summary_payload,
    build_design_asset_payload,
)
from app.services.llm_orchestration_runtime import generate_orchestration_json
from app.services.orchestration_context import (
    ASSET_MODELS_BY_LAYER,
    asset_snapshot,
    business_stories_snapshot,
    change_set_snapshot,
    latest_assets_snapshot,
    next_asset_version,
    project_config_snapshot,
    story_snapshot,
)
from app.services.orchestration_validators import (
    validate_blueprint_summary_payload,
    validate_design_asset_payload,
)
from app.services.project_service import ProjectService
from app.services.prompt_pack_generation_service import PromptPackGenerationService

RUN_TYPE = "apply_change_set"
APPLIABLE_STATUSES = {"draft", "ready", "failed"}
ASSET_GENERATION_ORDER = [
    "ux_design",
    "ui_design",
    "frontend_pages",
    "frontend_tools",
    "api_contract",
    "backend_services",
    "backend_tools",
    "database_models",
]


class DesignAssetOrchestrationService:
    def __init__(
        self,
        db: Session,
        llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    ) -> None:
        self.db = db
        self.llm_client_factory = llm_client_factory

    def execute_run(self, run: GenerationRun) -> dict[str, Any]:
        payload = run.queue_payload or {}
        change_set_id = payload.get("change_set_id")
        if not change_set_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="change_set_id is required.",
            )
        change_set = self.db.get(ChangeSet, UUID(str(change_set_id)))
        if change_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Change set not found.",
            )
        if change_set.status not in APPLIABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft, ready, or failed change sets can be applied.",
            )

        project = ProjectService(self.db).get_project(change_set.project_id)
        story = (
            self.db.get(BusinessRequirementStory, change_set.source_story_id)
            if change_set.source_story_id
            else None
        )
        run.status = "running"
        run.progress = max(run.progress, 10)
        run.message = "正在应用变更集..."
        run.started_at = run.started_at or datetime.now(UTC)
        self.db.add(run)
        self.db.commit()

        project_config = project_config_snapshot(project)
        change_set_data = change_set_snapshot(change_set)
        old_assets = latest_assets_snapshot(self.db, project.id)
        generated_assets = self._generate_asset_payloads(
            project_id=project.id,
            project_config=project_config,
            story=story,
            change_set=change_set,
            old_assets=old_assets,
        )
        blueprint_content = self._generate_blueprint_summary(
            project_id=project.id,
            project_config=project_config,
            generated_assets=generated_assets,
            change_set_data=change_set_data,
        )

        blueprint = ProjectBlueprint(
            project_id=project.id,
            version=next_asset_version(self.db, ProjectBlueprint, project.id),
            source_requirement_id=change_set.source_requirement_id,
            source_story_id=change_set.source_story_id,
            change_set_id=change_set.id,
            generation_run_id=run.id,
            title="项目蓝图",
            summary=blueprint_content["version_summary"],
            content=blueprint_content,
            diff_from_previous=change_set.diff_from_previous,
        )
        self.db.add(blueprint)
        self.db.flush()

        created_assets = self._persist_assets(
            project_id=project.id,
            run=run,
            change_set=change_set,
            blueprint=blueprint,
            generated_assets=generated_assets,
        )
        new_versions = {layer: asset_snapshot(asset) for layer, asset in created_assets.items()}
        new_versions["project_blueprint"] = asset_snapshot(blueprint)

        prompt_packs = []
        if _should_generate_prompt_pack(change_set):
            prompt_packs = PromptPackGenerationService(
                self.db,
                llm_client_factory=self.llm_client_factory,
            ).generate_for_change_set(
                run,
                change_set,
                old_versions=old_assets,
                new_versions=new_versions,
            )

        change_set.status = "applied"
        self.db.add(change_set)
        run.status = "completed"
        run.progress = 100
        run.message = "变更集已应用。"
        run.output_snapshot = {
            "change_set_id": str(change_set.id),
            "asset_ids": {layer: str(asset.id) for layer, asset in created_assets.items()},
            "blueprint_id": str(blueprint.id),
            "context_pack_ids": [str(pack.id) for pack in prompt_packs],
            "affected_layers": change_set.affected_layers,
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        return run.output_snapshot

    def _generate_asset_payloads(
        self,
        *,
        project_id: UUID,
        project_config: dict[str, Any],
        story: BusinessRequirementStory | None,
        change_set: ChangeSet,
        old_assets: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        generated: dict[str, dict[str, Any]] = {}
        related_assets = dict(latest_assets_snapshot(self.db, project_id))
        for layer in _ordered_affected_asset_layers(change_set.affected_layers):
            if layer not in ASSET_MODELS_BY_LAYER:
                continue
            parsed = generate_orchestration_json(
                SYSTEM_PROMPT,
                build_design_asset_payload(
                    layer=layer,
                    project_config=project_config,
                    selected_story=story_snapshot(story),
                    change_set=change_set_snapshot(change_set),
                    previous_version=old_assets.get(layer),
                    related_assets=related_assets,
                ),
                llm_client_factory=self.llm_client_factory,
            )
            generated[layer] = validate_design_asset_payload(parsed, layer=layer)
            related_assets[layer] = _generated_asset_snapshot(generated[layer])
        return generated

    def _generate_blueprint_summary(
        self,
        *,
        project_id: UUID,
        project_config: dict[str, Any],
        generated_assets: dict[str, dict[str, Any]],
        change_set_data: dict[str, Any],
    ) -> dict[str, Any]:
        current_assets = latest_assets_snapshot(self.db, project_id)
        for layer, payload in generated_assets.items():
            current_assets[layer] = {
                "title": payload["title"],
                "summary": payload["summary"],
                "content": payload["content"],
                "diff_from_previous": payload["diff_from_previous"],
            }
        parsed = generate_orchestration_json(
            SYSTEM_PROMPT,
            build_blueprint_summary_payload(
                project_config=project_config,
                business_stories=business_stories_snapshot(self.db, project_id),
                design_assets=current_assets,
                latest_change_set=change_set_data,
            ),
            llm_client_factory=self.llm_client_factory,
        )
        return validate_blueprint_summary_payload(parsed)

    def _persist_assets(
        self,
        *,
        project_id: UUID,
        run: GenerationRun,
        change_set: ChangeSet,
        blueprint: ProjectBlueprint,
        generated_assets: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        created: dict[str, Any] = {}
        for layer, payload in generated_assets.items():
            model = ASSET_MODELS_BY_LAYER[layer]
            common_kwargs = {
                "project_id": project_id,
                "version": next_asset_version(self.db, model, project_id),
                "source_requirement_id": change_set.source_requirement_id,
                "source_story_id": change_set.source_story_id,
                "change_set_id": change_set.id,
                "generation_run_id": run.id,
                "title": payload["title"],
                "summary": payload["summary"],
                "content": payload["content"],
                "diff_from_previous": payload["diff_from_previous"],
            }
            if model is ApiContractDraft:
                asset = model(
                    blueprint_id=blueprint.id,
                    base_path=payload["content"].get("base_path", "/api/v1"),
                    **common_kwargs,
                )
            elif model is DbModelDraft:
                asset = model(blueprint_id=blueprint.id, **common_kwargs)
            else:
                asset = model(**common_kwargs)
            self.db.add(asset)
            self.db.flush()
            created[layer] = asset
        return created


def _should_generate_prompt_pack(change_set: ChangeSet) -> bool:
    strategy = change_set.recommended_prompt_strategy or {}
    return (
        "prompt_assets" in change_set.affected_layers
        or bool(strategy.get("generate_frontend_prompt"))
        or bool(strategy.get("generate_backend_prompt"))
    )


def _ordered_affected_asset_layers(affected_layers: list[str]) -> list[str]:
    affected = set(affected_layers)
    return [layer for layer in ASSET_GENERATION_ORDER if layer in affected]


def _generated_asset_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": None,
        "version": None,
        "title": payload["title"],
        "summary": payload["summary"],
        "content": payload["content"],
        "diff_from_previous": payload["diff_from_previous"],
        "created_at": None,
    }
