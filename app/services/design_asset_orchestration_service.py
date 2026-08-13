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
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.context_pack import ContextPack
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import build_design_asset_prompt
from app.prompts.templates.backend_implementation.output_schema import (
    BackendImplementationOutput,
)
from app.prompts.templates.design_asset.output_schema import DesignAssetOutput
from app.prompts.templates.frontend_pages.output_schema import FrontendPagesOutput
from app.prompts.templates.ui_design.output_schema import UIDesignOutput
from app.prompts.templates.ux_design.output_schema import UXDesignOutput
from app.services.llm_orchestration_runtime import generate_orchestration_json
from app.services.orchestration_context import (
    ASSET_MODELS_BY_LAYER,
    asset_snapshot,
    change_set_snapshot,
    latest_assets_snapshot,
    next_asset_version,
    project_config_snapshot,
    story_snapshot,
)
from app.services.orchestration_validators import (
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
    "api_contract",
    "backend_services",
    "database_models",
]
ASSET_PROGRESS_LABELS = {
    "ux_design": "UX 设计",
    "ui_design": "UI 设计",
    "frontend_pages": "前端工程实现",
    "api_contract": "API 契约",
    "backend_services": "后端工程实现",
    "database_models": "数据库模型",
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
        change_sets = self._batch_change_sets(change_set)
        if any(item.status not in APPLIABLE_STATUSES for item in change_sets):
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
        old_assets = latest_assets_snapshot(self.db, project.id)
        related_assets = dict(old_assets)
        change_sets_by_layer: dict[str, ChangeSet] = {}
        for item in change_sets:
            if item.layer in ASSET_GENERATION_ORDER:
                change_sets_by_layer[item.layer] = item
                continue
            for layer in item.affected_layers:
                if layer in ASSET_GENERATION_ORDER:
                    change_sets_by_layer[layer] = item
        affected_layers = [
            layer for layer in ASSET_GENERATION_ORDER if layer in change_sets_by_layer
        ]
        created_assets: dict[str, Any] = {}
        generated_assets: dict[str, dict[str, Any]] = {}
        prompt_packs: list[ContextPack] = []
        total_steps = len(affected_layers) + (1 if affected_layers else 0)
        completed_steps = 0

        for layer in affected_layers:
            layer_change_set = change_sets_by_layer[layer]
            existing_asset = self._find_existing_asset(run, layer_change_set, layer)
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
                        change_sets=change_sets,
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
                layer_change_set.id,
                layer,
            )
            prompt = build_design_asset_prompt(
                layer=layer,
                project_config=project_config,
                selected_story=story_snapshot(story),
                change_set=change_set_snapshot(layer_change_set),
                previous_version=old_assets.get(layer),
                related_assets=related_assets,
            )
            parsed = generate_orchestration_json(
                prompt.system,
                prompt.user,
                response_model=_design_asset_response_model(layer),
                llm_client_factory=self.llm_client_factory,
            )
            generated_assets[layer] = validate_design_asset_payload(parsed, layer=layer)
            logger.info(
                "design_asset_orchestration.layer.generated run_id=%s change_set_id=%s layer=%s",
                run.id,
                layer_change_set.id,
                layer,
            )
            related_assets[layer] = _generated_asset_snapshot(generated_assets[layer])
            asset = self._persist_asset(
                project_id=project.id,
                run=run,
                change_set=layer_change_set,
                blueprint_id=None,
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
                output_snapshot=self._progress_snapshot(
                    change_set,
                    created_assets,
                    change_sets=change_sets,
                ),
            )

        if affected_layers:
            self._set_run_progress(
                run,
                self._step_progress(completed_steps, total_steps),
                "正在生成指令集合...",
            )
            prompt_packs = PromptPackGenerationService(
                self.db,
                llm_client_factory=self.llm_client_factory,
            ).generate_for_change_set_batch(
                run,
                change_set,
                change_sets=change_sets,
                old_versions=old_assets,
                new_versions={
                    **{layer: asset_snapshot(asset) for layer, asset in created_assets.items()},
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
                    change_sets=change_sets,
                    prompt_packs=prompt_packs,
                ),
            )

        now = datetime.now(UTC)
        for item in change_sets:
            item.status = "applied"
            item.is_current = False
            item.applied_at = now
            self.db.add(item)
        if story is not None:
            story.status = "applied"
            self.db.add(story)
        run.status = "completed"
        run.progress = 100
        run.message = "分层变更集已应用。"
        run.output_snapshot = {
            "change_set_id": str(change_set.id),
            "change_set_ids": [str(item.id) for item in change_sets],
            "batch_id": str(change_set.batch_id) if change_set.batch_id else None,
            "asset_ids": {layer: str(asset.id) for layer, asset in created_assets.items()},
            "context_pack_ids": [str(pack.id) for pack in prompt_packs],
            "affected_layers": affected_layers,
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

    def _batch_change_sets(self, change_set: ChangeSet) -> list[ChangeSet]:
        if change_set.batch_id is None:
            return [change_set]
        return list(
            self.db.scalars(
                select(ChangeSet)
                .where(
                    ChangeSet.project_id == change_set.project_id,
                    ChangeSet.batch_id == change_set.batch_id,
                    ChangeSet.is_current.is_(True),
                )
                .order_by(ChangeSet.created_at.asc())
            )
        )

    def _progress_snapshot(
        self,
        change_set: ChangeSet,
        created_assets: dict[str, Any],
        *,
        change_sets: list[ChangeSet] | None = None,
        prompt_packs: list[ContextPack] | None = None,
    ) -> dict[str, Any]:
        completed_layers = list(created_assets.keys())
        snapshot: dict[str, Any] = {
            "change_set_id": str(change_set.id),
            "change_set_ids": [str(item.id) for item in (change_sets or [change_set])],
            "batch_id": str(change_set.batch_id) if change_set.batch_id else None,
            "asset_ids": _asset_ids(created_assets),
            "completed_layers": completed_layers,
        }
        if prompt_packs:
            snapshot["context_pack_ids"] = [str(pack.id) for pack in prompt_packs]
            snapshot["completed_layers"] = list(snapshot["completed_layers"]) + [
                "prompt_assets"
            ]
        return snapshot

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
                base_path=payload["content"].get("api_base_path")
                or payload["content"].get("base_path", "/api/v1"),
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


def _design_asset_response_model(layer: str):
    if layer == "ux_design":
        return UXDesignOutput
    if layer == "ui_design":
        return UIDesignOutput
    if layer == "frontend_pages":
        return FrontendPagesOutput
    if layer == "backend_services":
        return BackendImplementationOutput
    return DesignAssetOutput


def _asset_ids(created_assets: dict[str, Any]) -> dict[str, str]:
    return {layer: str(asset.id) for layer, asset in created_assets.items()}


def _asset_payload_snapshot(asset: Any) -> dict[str, Any]:
    return {
        "title": asset.title,
        "summary": asset.summary,
        "content": asset.content,
        "diff_from_previous": asset.diff_from_previous,
    }


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
