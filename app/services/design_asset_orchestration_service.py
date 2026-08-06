from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import OpenAICompatibleLLMClient
from app.models.api_contract import ApiContractDraft
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import (
    build_blueprint_summary_prompt,
    build_design_asset_prompt,
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
logger = logging.getLogger(__name__)
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
ASSET_PROGRESS_LABELS = {
    "ux_design": "UX 设计",
    "ui_design": "UI 设计",
    "frontend_pages": "前端页面结构",
    "frontend_tools": "前端依赖与工具",
    "api_contract": "API 契约",
    "backend_services": "后端服务设计",
    "backend_tools": "后端依赖与工具",
    "database_models": "数据库模型",
    "project_blueprint": "项目蓝图",
    "prompt_assets": "指令集合",
}


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
        related_assets = dict(old_assets)
        affected_layers = _ordered_affected_asset_layers(change_set.affected_layers)
        created_assets: dict[str, Any] = {}
        generated_assets: dict[str, dict[str, Any]] = {}
        deferred_assets: dict[str, dict[str, Any]] = {}
        prompt_packs: list[ContextPack] = []
        blueprint = self._find_existing_blueprint(run, change_set)
        total_steps = (
            len(affected_layers)
            + 1
            + (1 if _should_generate_prompt_pack(change_set) else 0)
        )
        completed_steps = 0

        for layer in affected_layers:
            existing_asset = self._find_existing_asset(run, change_set, layer)
            if existing_asset is not None:
                created_assets[layer] = existing_asset
                generated_assets[layer] = _asset_payload_snapshot(existing_asset)
                related_assets[layer] = asset_snapshot(existing_asset)
                completed_steps += 1
                self._set_run_progress(
                    run,
                    self._step_progress(completed_steps, total_steps),
                    f"{ASSET_PROGRESS_LABELS.get(layer, layer)}已存在，已跳过重复生成。",
                    output_snapshot=self._progress_snapshot(
                        change_set,
                        created_assets,
                        blueprint=blueprint,
                    ),
                )
                continue
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                f"正在生成{ASSET_PROGRESS_LABELS.get(layer, layer)}...",
            )
            logger.info(
                "design_asset_orchestration.layer.start run_id=%s change_set_id=%s layer=%s",
                run.id,
                change_set.id,
                layer,
            )
            prompt = build_design_asset_prompt(
                layer=layer,
                project_config=project_config,
                selected_story=story_snapshot(story),
                change_set=change_set_snapshot(change_set),
                previous_version=old_assets.get(layer),
                related_assets=related_assets,
            )
            parsed = generate_orchestration_json(
                prompt.system,
                prompt.user,
                llm_client_factory=self.llm_client_factory,
            )
            generated_assets[layer] = validate_design_asset_payload(parsed, layer=layer)
            logger.info(
                "design_asset_orchestration.layer.generated run_id=%s change_set_id=%s layer=%s",
                run.id,
                change_set.id,
                layer,
            )
            related_assets[layer] = _generated_asset_snapshot(generated_assets[layer])
            if _requires_blueprint_id(layer) and blueprint is None:
                deferred_assets[layer] = generated_assets[layer]
                self._set_run_progress(
                    run,
                    self._step_progress(completed_steps, total_steps),
                    f"{ASSET_PROGRESS_LABELS.get(layer, layer)}已生成，等待项目蓝图绑定后保存。",
                )
                continue
            asset = self._persist_asset(
                project_id=project.id,
                run=run,
                change_set=change_set,
                blueprint_id=blueprint.id if blueprint is not None else None,
                layer=layer,
                payload=generated_assets[layer],
            )
            created_assets[layer] = asset
            related_assets[layer] = asset_snapshot(asset)
            completed_steps += 1
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                f"{ASSET_PROGRESS_LABELS.get(layer, layer)}已保存。",
                output_snapshot=self._progress_snapshot(change_set, created_assets),
            )

        if blueprint is None:
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                "正在生成项目蓝图...",
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
            self.db.commit()
        completed_steps += 1
        self._set_run_progress(
            run,
            self._step_progress(completed_steps, total_steps),
            "项目蓝图已保存。",
            output_snapshot=self._progress_snapshot(
                change_set,
                created_assets,
                blueprint=blueprint,
            ),
        )

        for layer, payload in deferred_assets.items():
            asset = self._persist_asset(
                project_id=project.id,
                run=run,
                change_set=change_set,
                blueprint_id=blueprint.id,
                layer=layer,
                payload=payload,
            )
            created_assets[layer] = asset
            completed_steps += 1
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                f"{ASSET_PROGRESS_LABELS.get(layer, layer)}已保存。",
                output_snapshot=self._progress_snapshot(
                    change_set,
                    created_assets,
                    blueprint=blueprint,
                ),
            )

        if _should_generate_prompt_pack(change_set):
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                "正在生成指令集合...",
            )
            prompt_packs = PromptPackGenerationService(
                self.db,
                llm_client_factory=self.llm_client_factory,
            ).generate_for_change_set(
                run,
                change_set,
                old_versions=old_assets,
                new_versions={
                    **{
                        layer: asset_snapshot(asset)
                        for layer, asset in created_assets.items()
                    },
                    "project_blueprint": asset_snapshot(blueprint),
                },
            )
            completed_steps += 1
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                "指令集合已保存。",
                output_snapshot=self._progress_snapshot(
                    change_set,
                    created_assets,
                    blueprint=blueprint,
                    prompt_packs=prompt_packs,
                ),
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

    def _find_existing_asset(
        self,
        run: GenerationRun,
        change_set: ChangeSet,
        layer: str,
    ) -> Any | None:
        model = ASSET_MODELS_BY_LAYER[layer]
        return self.db.scalar(
            select(model)
            .where(
                model.project_id == change_set.project_id,
                model.change_set_id == change_set.id,
            )
            .order_by(model.created_at.desc())
            .limit(1)
        )

    def _find_existing_blueprint(
        self,
        run: GenerationRun,
        change_set: ChangeSet,
    ) -> ProjectBlueprint | None:
        return self.db.scalar(
            select(ProjectBlueprint)
            .where(
                ProjectBlueprint.project_id == change_set.project_id,
                ProjectBlueprint.change_set_id == change_set.id,
                ProjectBlueprint.generation_run_id == run.id,
            )
            .order_by(ProjectBlueprint.created_at.desc())
            .limit(1)
        )

    def _progress_snapshot(
        self,
        change_set: ChangeSet,
        created_assets: dict[str, Any],
        *,
        blueprint: ProjectBlueprint | None = None,
        prompt_packs: list[ContextPack] | None = None,
    ) -> dict[str, Any]:
        completed_layers = list(created_assets.keys())
        snapshot: dict[str, Any] = {
            "change_set_id": str(change_set.id),
            "asset_ids": _asset_ids(created_assets),
            "completed_layers": completed_layers,
        }
        if blueprint is not None:
            snapshot["blueprint_id"] = str(blueprint.id)
            snapshot["completed_layers"] = completed_layers + ["project_blueprint"]
        if prompt_packs:
            snapshot["context_pack_ids"] = [str(pack.id) for pack in prompt_packs]
            snapshot["completed_layers"] = list(snapshot["completed_layers"]) + [
                "prompt_assets"
            ]
        return snapshot

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
        prompt = build_blueprint_summary_prompt(
            project_config=project_config,
            business_stories=business_stories_snapshot(self.db, project_id),
            design_assets=current_assets,
            latest_change_set=change_set_data,
        )
        parsed = generate_orchestration_json(
            prompt.system,
            prompt.user,
            llm_client_factory=self.llm_client_factory,
        )
        return validate_blueprint_summary_payload(parsed)

    def _persist_asset(
        self,
        *,
        project_id: UUID,
        run: GenerationRun,
        change_set: ChangeSet,
        blueprint_id: UUID | None,
        layer: str,
        payload: dict[str, Any],
    ) -> Any:
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
                blueprint_id=blueprint_id,
                base_path=payload["content"].get("base_path", "/api/v1"),
                **common_kwargs,
            )
        elif model is DbModelDraft:
            asset = model(blueprint_id=blueprint_id, **common_kwargs)
        else:
            asset = model(**common_kwargs)
        self.db.add(asset)
        self.db.flush()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def _set_run_progress(
        self,
        run: GenerationRun,
        progress: int,
        message: str,
        *,
        output_snapshot: dict[str, Any] | None = None,
    ) -> None:
        run.progress = progress
        run.message = message
        if output_snapshot is not None:
            run.output_snapshot = output_snapshot
        self.db.add(run)
        self.db.commit()

    @staticmethod
    def _step_progress(completed_steps: int, total_steps: int) -> int:
        if total_steps <= 0:
            return 90
        return min(95, 10 + round((80 * completed_steps) / total_steps))


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


def _asset_ids(created_assets: dict[str, Any]) -> dict[str, str]:
    return {layer: str(asset.id) for layer, asset in created_assets.items()}


def _asset_payload_snapshot(asset: Any) -> dict[str, Any]:
    return {
        "title": asset.title,
        "summary": asset.summary,
        "content": asset.content,
        "diff_from_previous": asset.diff_from_previous,
    }


def _requires_blueprint_id(layer: str) -> bool:
    return ASSET_MODELS_BY_LAYER[layer] in {ApiContractDraft, DbModelDraft}


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
