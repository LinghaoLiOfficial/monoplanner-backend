from __future__ import annotations

import logging
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha1
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import REQUEST_ERROR_DETAIL, LLMRequestError
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.generation_run import GenerationRun
from app.models.generation_worker import GenerationWorker
from app.models.user import User
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.api_contract_service import RUN_TYPE as API_CONTRACT_RUN_TYPE
from app.services.business_story_generation_service import RUN_TYPE as BUSINESS_STORY_RUN_TYPE
from app.services.change_set_generation_service import (
    LAYER_GENERATION_ORDER,
)
from app.services.change_set_generation_service import (
    RUN_TYPE as CHANGE_SET_RUN_TYPE,
)
from app.services.context_pack_service import ContextPackService
from app.services.db_model_service import RUN_TYPE as DB_MODEL_RUN_TYPE
from app.services.design_asset_orchestration_service import (
    APPLIABLE_STATUSES,
    ASSET_GENERATION_ORDER,
)
from app.services.design_asset_orchestration_service import (
    RUN_TYPE as APPLY_CHANGE_SET_RUN_TYPE,
)
from app.services.generation_service import RUN_TYPE as BLUEPRINT_RUN_TYPE
from app.services.orchestration_context import latest_assets_snapshot
from app.services.project_service import ProjectService
from app.services.prompt_pack_generation_service import RUN_TYPE as PROMPT_PACK_RUN_TYPE
from app.services.streaming_generation_service import StreamingGenerationService

logger = logging.getLogger(__name__)

CONTEXT_PACK_RUN_TYPE = "generate_context_packs"
CHANGE_SET_ASSET_RUN_TYPE = "generate_change_set_asset"
DESIGN_ASSET_RUN_TYPE = "generate_design_asset"
QUEUE_STATUS = "queued"
RUNNING_STATUS = "running"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"
CANCELLED_STATUS = "cancelled"
WORKER_OFFLINE_DETAIL = "后台任务队列 worker 未启动，请先启动 worker 后再提交生成任务。"
WORKER_ID_MAX_LENGTH = 100

MODULE_BY_RUN_TYPE = {
    BUSINESS_STORY_RUN_TYPE: "business_stories",
    BLUEPRINT_RUN_TYPE: "blueprint",
    API_CONTRACT_RUN_TYPE: "api_contract",
    DB_MODEL_RUN_TYPE: "db_model",
    CONTEXT_PACK_RUN_TYPE: "context_packs",
    CHANGE_SET_RUN_TYPE: "change_set",
    CHANGE_SET_ASSET_RUN_TYPE: "change_set",
    APPLY_CHANGE_SET_RUN_TYPE: "apply_change_set",
    DESIGN_ASSET_RUN_TYPE: "apply_change_set",
    PROMPT_PACK_RUN_TYPE: "prompt_pack",
}


class GenerationQueueService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def enqueue_business_stories(
        self,
        project_id: UUID,
        payload: GenerateBusinessRequirementStoriesRequest,
    ) -> GenerationRun:
        self._ensure_project_access(project_id)
        service = StreamingGenerationService(self.db)
        spec = service.build_business_stories_spec(project_id, payload)
        existing_run = self._find_active_requirement_run(
            project_id,
            spec.requirement_id,
            spec.run_type,
        )
        if existing_run is not None:
            if existing_run.status == "partially_completed":
                self._resume_failed_children(existing_run)
            return existing_run
        return self._enqueue(
            project_id=project_id,
            requirement_id=spec.requirement_id,
            run_type=spec.run_type,
            module=spec.module,
            queue_payload={
                "project_id": str(project_id),
                "requirement_id": str(spec.requirement_id) if spec.requirement_id else None,
                "overwrite": payload.overwrite,
            },
            input_snapshot=spec.input_snapshot,
        )

    def enqueue_blueprint(self, project_id: UUID) -> GenerationRun:
        self._ensure_project_access(project_id)
        service = StreamingGenerationService(self.db)
        spec = service.build_blueprint_spec(project_id)
        return self._enqueue(
            project_id=project_id,
            requirement_id=spec.requirement_id,
            run_type=spec.run_type,
            module=spec.module,
            queue_payload={"project_id": str(project_id)},
            input_snapshot=spec.input_snapshot,
        )

    def enqueue_api_contract(self, project_id: UUID) -> GenerationRun:
        self._ensure_project_access(project_id)
        service = StreamingGenerationService(self.db)
        spec = service.build_api_contract_spec(project_id)
        return self._enqueue(
            project_id=project_id,
            requirement_id=spec.requirement_id,
            run_type=spec.run_type,
            module=spec.module,
            queue_payload={"project_id": str(project_id)},
            input_snapshot=spec.input_snapshot,
        )

    def enqueue_db_model(self, project_id: UUID) -> GenerationRun:
        self._ensure_project_access(project_id)
        service = StreamingGenerationService(self.db)
        spec = service.build_db_model_spec(project_id)
        return self._enqueue(
            project_id=project_id,
            requirement_id=spec.requirement_id,
            run_type=spec.run_type,
            module=spec.module,
            queue_payload={"project_id": str(project_id)},
            input_snapshot=spec.input_snapshot,
        )

    def enqueue_context_packs(self, project_id: UUID) -> GenerationRun:
        from app.services.blueprint_service import BlueprintService
        self._ensure_project_access(project_id)
        if BlueprintService(self.db, self.current_user).get_latest_blueprint(project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no blueprint to generate context packs from.",
            )
        return self._enqueue(
            project_id=project_id,
            requirement_id=None,
            run_type=CONTEXT_PACK_RUN_TYPE,
            module="context_packs",
            queue_payload={"project_id": str(project_id)},
            input_snapshot={"project_id": str(project_id)},
        )

    def enqueue_change_set_for_story(self, story_id: UUID) -> GenerationRun:
        story = self.db.get(BusinessRequirementStory, story_id)
        if story is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business requirement story not found.",
            )
        self._ensure_project_access(story.project_id)
        active_run = self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.project_id == story.project_id,
                GenerationRun.run_type == CHANGE_SET_RUN_TYPE,
                GenerationRun.status.in_([QUEUE_STATUS, RUNNING_STATUS, "waiting"]),
            )
            .order_by(GenerationRun.created_at.desc())
            .limit(1)
        )
        if active_run is not None:
            active_story_id = str((active_run.queue_payload or {}).get("story_id") or "")
            if active_story_id == str(story.id):
                return active_run
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="当前项目已有其他需求正在执行，请等待完成后再试。",
            )
        run = self._enqueue(
            project_id=story.project_id,
            requirement_id=story.requirement_id,
            run_type=CHANGE_SET_RUN_TYPE,
            module="change_set",
            queue_payload={
                "project_id": str(story.project_id),
                "story_id": str(story.id),
            },
            input_snapshot={
                "project_id": str(story.project_id),
                "story_id": str(story.id),
                "source": "business_story",
            },
        )
        story.execution_generation_run_id = run.id
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return run

    def enqueue_apply_change_set(self, change_set_id: UUID) -> GenerationRun:
        change_set = self._get_change_set_for_workflow(change_set_id)
        existing_run = self._find_active_apply_change_set_run(change_set)
        if existing_run is not None:
            if existing_run.status == "partially_completed":
                self._resume_failed_children(existing_run)
            return existing_run
        if change_set.status not in APPLIABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft, ready, or failed change sets can be applied.",
            )
        return self._enqueue(
            project_id=change_set.project_id,
            requirement_id=change_set.source_requirement_id,
            run_type=APPLY_CHANGE_SET_RUN_TYPE,
            module="apply_change_set",
            queue_payload={
                "project_id": str(change_set.project_id),
                "change_set_id": str(change_set.id),
                "batch_id": str(change_set.batch_id) if change_set.batch_id else None,
            },
            input_snapshot={
                "project_id": str(change_set.project_id),
                "change_set_id": str(change_set.id),
                "batch_id": str(change_set.batch_id) if change_set.batch_id else None,
                "affected_layers": change_set.affected_layers,
            },
        )

    def enqueue_apply_change_set_batch(
        self,
        project_id: UUID,
        batch_id: UUID,
    ) -> GenerationRun:
        self._ensure_project_access(project_id)
        change_set = self._get_change_set_for_batch(project_id, batch_id)
        return self.enqueue_apply_change_set(change_set.id)

    def enqueue_regenerate_change_set(self, change_set_id: UUID) -> GenerationRun:
        change_set = self._get_change_set_for_workflow(change_set_id)
        existing_run = self._find_active_change_set_run(change_set.id, CHANGE_SET_RUN_TYPE)
        if existing_run is not None:
            return existing_run
        if change_set.source_story_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Change set has no source story to regenerate from.",
            )
        return self._enqueue(
            project_id=change_set.project_id,
            requirement_id=change_set.source_requirement_id,
            run_type=CHANGE_SET_RUN_TYPE,
            module="change_set",
            queue_payload={
                "project_id": str(change_set.project_id),
                "story_id": str(change_set.source_story_id),
                "source_change_set_id": str(change_set.id),
            },
            input_snapshot={
                "project_id": str(change_set.project_id),
                "story_id": str(change_set.source_story_id),
                "source_change_set_id": str(change_set.id),
                "source": "regenerate_change_set",
            },
        )

    def enqueue_prompt_pack(self, project_id: UUID, change_set_id: UUID) -> GenerationRun:
        self._ensure_project_access(project_id)
        change_set = self.db.get(ChangeSet, change_set_id)
        if change_set is None or change_set.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Change set not found.",
            )
        return self._enqueue(
            project_id=project_id,
            requirement_id=change_set.source_requirement_id,
            run_type=PROMPT_PACK_RUN_TYPE,
            module="prompt_pack",
            queue_payload={
                "project_id": str(project_id),
                "change_set_id": str(change_set.id),
            },
            input_snapshot={
                "project_id": str(project_id),
                "change_set_id": str(change_set.id),
            },
        )

    def get_run(self, run_id: UUID) -> GenerationRun:
        run = self.db.get(GenerationRun, run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Generation run not found.",
            )
        self._ensure_project_access(run.project_id)
        return run

    def heartbeat_worker(self, worker_id: str) -> GenerationWorker:
        now = datetime.now(UTC)
        worker = self.db.scalar(
            select(GenerationWorker).where(GenerationWorker.worker_id == worker_id)
        )
        if worker is None:
            worker = GenerationWorker(worker_id=worker_id)
        worker.status = "online"
        worker.last_heartbeat_at = now
        self.db.add(worker)
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def has_active_worker(self) -> bool:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.queue_worker_heartbeat_timeout_seconds
        )
        return (
            self.db.scalar(
                select(GenerationWorker.id)
                .where(
                    GenerationWorker.status == "online",
                    GenerationWorker.last_heartbeat_at >= cutoff,
                )
                .limit(1)
            )
            is not None
        )

    def cancel_queued(self, run_id: UUID) -> GenerationRun:
        run = self.get_run(run_id)
        if run.status != QUEUE_STATUS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only queued generation runs can be cancelled.",
            )
        now = datetime.now(UTC)
        run.status = CANCELLED_STATUS
        run.progress = 0
        run.message = "任务已取消。"
        run.cancelled_at = now
        run.completed_at = now
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def claim_next_job(self, worker_id: str) -> GenerationRun | None:
        now = datetime.now(UTC)
        statement = (
            select(GenerationRun)
            .where(
                GenerationRun.status == QUEUE_STATUS,
                (GenerationRun.next_attempt_at.is_(None))
                | (GenerationRun.next_attempt_at <= now),
            )
            .order_by(GenerationRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        run = self.db.scalar(statement)
        if run is None:
            return None
        run.status = RUNNING_STATUS
        run.locked_by = worker_id
        run.locked_at = now
        run.started_at = run.started_at or now
        run.attempt_count += 1
        run.progress = max(run.progress, 1)
        run.message = "后台任务已开始执行。"
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "generation.worker.job.claimed worker_id=%s run_id=%s run_type=%s "
            "project_id=%s attempt=%s/%s",
            worker_id,
            run.id,
            run.run_type,
            run.project_id,
            run.attempt_count,
            run.max_attempts,
        )
        return run

    def execute_run(self, run_id: UUID) -> GenerationRun:
        run = self.get_run(run_id)
        if run.status not in {RUNNING_STATUS, QUEUE_STATUS}:
            return run
        if run.status == QUEUE_STATUS:
            run.status = RUNNING_STATUS
            run.started_at = run.started_at or datetime.now(UTC)
            run.attempt_count += 1
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)

        worker_id = run.locked_by
        logger.info(
            "generation.worker.job.started worker_id=%s run_id=%s run_type=%s project_id=%s",
            worker_id,
            run.id,
            run.run_type,
            run.project_id,
        )
        try:
            if run.run_type == CONTEXT_PACK_RUN_TYPE:
                ContextPackService(self.db).execute_context_pack_run(run)
            elif run.run_type == CHANGE_SET_RUN_TYPE:
                from app.services.change_set_generation_service import ChangeSetGenerationService
                self._initialize_change_set_parent(run)
            elif run.run_type == CHANGE_SET_ASSET_RUN_TYPE:
                from app.services.change_set_generation_service import ChangeSetGenerationService

                ChangeSetGenerationService(self.db).execute_asset_run(run)
                self._mark_child_completed(run)
            elif run.run_type == APPLY_CHANGE_SET_RUN_TYPE:
                from app.services.design_asset_orchestration_service import (
                    DesignAssetOrchestrationService,
                )
                self._initialize_apply_parent(run)
            elif run.run_type == DESIGN_ASSET_RUN_TYPE:
                from app.services.design_asset_orchestration_service import (
                    DesignAssetOrchestrationService,
                )

                DesignAssetOrchestrationService(self.db).execute_asset_run(run)
                self._mark_child_completed(run)
            elif run.run_type == PROMPT_PACK_RUN_TYPE:
                from app.services.prompt_pack_generation_service import PromptPackGenerationService

                PromptPackGenerationService(self.db).execute_run(run)
                self._mark_prompt_pack_completed(run)
            else:
                spec = self._build_spec_for_run(run)
                StreamingGenerationService(self.db).execute_existing_run(run, spec)
            run.locked_at = None
            run.locked_by = None
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            logger.info(
                "generation.worker.job.finished worker_id=%s run_id=%s run_type=%s "
                "status=%s progress=%s",
                worker_id,
                run.id,
                run.run_type,
                run.status,
                run.progress,
            )
            return run
        except Exception as exc:
            return self.mark_retry_or_failed(run, exc)

    def _initialize_change_set_parent(self, run: GenerationRun) -> None:
        payload = run.queue_payload or {}
        story_id = payload.get("story_id")
        source_id = payload.get("source_change_set_id")
        story = self.db.get(BusinessRequirementStory, UUID(str(story_id))) if story_id else None
        source = self.db.get(ChangeSet, UUID(str(source_id))) if source_id else None
        if story is None and source is not None and source.source_story_id:
            story = self.db.get(BusinessRequirementStory, source.source_story_id)
        if story is None:
            raise HTTPException(status_code=404, detail="Business requirement story not found.")
        layers = _ordered_layers(
            source.affected_layers if source is not None else story.affected_layers,
            LAYER_GENERATION_ORDER,
            source.layer if source is not None else None,
        )
        batch_id = str(payload.get("batch_id") or uuid4())
        payload["batch_id"] = batch_id
        run.queue_payload = payload
        existing = self._children(run)
        if not existing:
            for index, layer in enumerate(layers):
                self._new_run(
                    project_id=story.project_id,
                    requirement_id=story.requirement_id,
                    run_type=CHANGE_SET_ASSET_RUN_TYPE,
                    module="change_set",
                    parent_run_id=run.id,
                    asset_layer=layer,
                    status=QUEUE_STATUS if index == 0 else "waiting",
                    queue_payload={
                        "project_id": str(story.project_id),
                        "story_id": str(story.id),
                        "layer": layer,
                        "batch_id": batch_id,
                        "source_change_set_id": source_id,
                    },
                    input_snapshot={
                        "story_id": str(story.id),
                        "layer": layer,
                        "batch_id": batch_id,
                    },
                )
        if not layers:
            run.status = COMPLETED_STATUS
            run.progress = 100
            run.message = "变更集生成已完成。"
            run.completed_at = datetime.now(UTC)
            run.output_snapshot = self._aggregate_snapshot(run, batch_id=batch_id)
            self.db.add(run)
            self.db.commit()
            return
        run.status = "waiting"
        run.progress = 5
        run.message = "变更集子任务已创建，等待按资产层生成。"
        run.output_snapshot = self._aggregate_snapshot(run, batch_id=batch_id)
        self.db.add(run)
        self.db.commit()

    def _initialize_apply_parent(self, run: GenerationRun) -> None:
        payload = run.queue_payload or {}
        change_set_id = payload.get("change_set_id")
        change_set = self.db.get(ChangeSet, UUID(str(change_set_id))) if change_set_id else None
        if change_set is None:
            raise HTTPException(status_code=404, detail="Change set not found.")
        batch = self._batch_change_sets(change_set)
        by_layer = {item.layer: item for item in batch if item.layer in ASSET_GENERATION_ORDER}
        for item in batch:
            for layer in item.affected_layers:
                if layer in ASSET_GENERATION_ORDER:
                    by_layer.setdefault(layer, item)
        layers = [layer for layer in ASSET_GENERATION_ORDER if layer in by_layer]
        batch_id = str(change_set.batch_id) if change_set.batch_id else str(uuid4())
        payload["batch_id"] = batch_id
        payload.setdefault(
            "previous_assets", latest_assets_snapshot(self.db, change_set.project_id)
        )
        run.queue_payload = payload
        existing = self._children(run)
        if not existing:
            for index, layer in enumerate(layers):
                item = by_layer[layer]
                self._new_run(
                    project_id=change_set.project_id,
                    requirement_id=change_set.source_requirement_id,
                    run_type=DESIGN_ASSET_RUN_TYPE,
                    module="apply_change_set",
                    parent_run_id=run.id,
                    asset_layer=layer,
                    status=QUEUE_STATUS if index == 0 else "waiting",
                    queue_payload={
                        "project_id": str(change_set.project_id),
                        "change_set_id": str(item.id),
                        "batch_id": batch_id,
                        "layer": layer,
                    },
                    input_snapshot={
                        "change_set_id": str(item.id),
                        "layer": layer,
                        "batch_id": batch_id,
                    },
                )
        if not layers:
            run.status = COMPLETED_STATUS
            run.progress = 100
            run.message = "变更集应用已完成。"
            run.completed_at = datetime.now(UTC)
            run.output_snapshot = self._aggregate_snapshot(run, batch_id=batch_id)
            self.db.add(run)
            self.db.commit()
            return
        run.status = "waiting"
        run.progress = 5
        run.message = "资产生成子任务已创建，等待按依赖顺序应用。"
        run.output_snapshot = self._aggregate_snapshot(run, batch_id=batch_id)
        self.db.add(run)
        self.db.commit()

    def _mark_child_completed(self, child: GenerationRun) -> None:
        parent = child.parent_run
        if parent is None:
            return
        self._activate_next_child(parent)
        self._aggregate_parent(parent)

    def _resume_failed_children(self, parent: GenerationRun) -> None:
        children = self._children(parent)
        resumed = False
        for child in children:
            if child.status == FAILED_STATUS:
                child.status = QUEUE_STATUS
                child.progress = 0
                child.error_message = None
                child.completed_at = None
                child.next_attempt_at = datetime.now(UTC)
                child.message = "失败子任务已重新加入队列。"
                self.db.add(child)
                resumed = True
        if resumed:
            parent.status = "waiting"
            parent.message = "失败子任务已重新加入队列。"
            self.db.add(parent)
            self.db.commit()

    def _mark_prompt_pack_completed(self, prompt_run: GenerationRun) -> None:
        parent = prompt_run.parent_run
        if parent is None:
            return
        change_set_id = (prompt_run.queue_payload or {}).get("change_set_id")
        change_set = self.db.get(ChangeSet, UUID(str(change_set_id))) if change_set_id else None
        if change_set is not None:
            now = datetime.now(UTC)
            for item in self._batch_change_sets(change_set):
                item.status = "applied"
                item.is_current = False
                item.applied_at = now
                self.db.add(item)
            if change_set.source_story_id:
                story = self.db.get(BusinessRequirementStory, change_set.source_story_id)
                if story is not None:
                    story.status = "applied"
                    self.db.add(story)
        parent.status = COMPLETED_STATUS
        parent.progress = 100
        parent.message = "变更集已应用。"
        parent.completed_at = datetime.now(UTC)
        parent.output_snapshot = self._aggregate_snapshot(parent, include_prompt=True)
        self.db.add(parent)
        self.db.commit()

    def _activate_next_child(self, parent: GenerationRun) -> None:
        children = self._children(parent)
        if any(child.status in {QUEUE_STATUS, RUNNING_STATUS} for child in children):
            return
        if any(child.status == FAILED_STATUS for child in children):
            return
        waiting = next((child for child in children if child.status == "waiting"), None)
        if waiting is not None:
            waiting.status = QUEUE_STATUS
            waiting.next_attempt_at = datetime.now(UTC)
            waiting.message = "子任务已就绪，等待 worker 执行。"
            self.db.add(waiting)
            self.db.commit()

    def _aggregate_parent(self, parent: GenerationRun) -> None:
        children = self._children(parent)
        completed = [child for child in children if child.status == COMPLETED_STATUS]
        failed = [child for child in children if child.status == FAILED_STATUS]
        if failed:
            parent.status = "partially_completed" if completed else FAILED_STATUS
            parent.message = (
                "部分资产生成失败，可单独重试失败子任务。"
                if completed
                else "资产子任务全部失败。"
            )
        elif children and len(completed) == len(children):
            if parent.run_type == APPLY_CHANGE_SET_RUN_TYPE and not any(
                child.run_type == PROMPT_PACK_RUN_TYPE for child in children
            ):
                self._create_prompt_pack_child(parent, completed)
                return
            parent.status = COMPLETED_STATUS
            parent.progress = 100
            parent.message = "变更集生成已完成。"
            parent.completed_at = datetime.now(UTC)
        elif children:
            parent.status = "waiting"
            parent.progress = min(95, 5 + round(90 * len(completed) / len(children)))
        parent.output_snapshot = self._aggregate_snapshot(parent)
        self.db.add(parent)
        self.db.commit()

    def _create_prompt_pack_child(
        self, parent: GenerationRun, children: list[GenerationRun]
    ) -> None:
        payload = parent.queue_payload or {}
        change_set_id = payload.get("change_set_id")
        if not change_set_id:
            first_payload = children[0].queue_payload or {}
            change_set_id = first_payload.get("change_set_id")
        self._new_run(
            project_id=parent.project_id,
            requirement_id=parent.requirement_id,
            run_type=PROMPT_PACK_RUN_TYPE,
            module="prompt_pack",
            parent_run_id=parent.id,
            status=QUEUE_STATUS,
            queue_payload={
                "project_id": str(parent.project_id),
                "change_set_id": change_set_id,
                "batch_id": payload.get("batch_id"),
                "parent_run_id": str(parent.id),
                "previous_assets": payload.get("previous_assets", {}),
            },
            input_snapshot={"change_set_id": change_set_id, "parent_run_id": str(parent.id)},
        )
        parent.status = "waiting"
        parent.message = "资产已生成，正在生成指令集合。"

    def _children(self, parent: GenerationRun) -> list[GenerationRun]:
        return list(
            self.db.scalars(
                select(GenerationRun)
                .where(GenerationRun.parent_run_id == parent.id)
                .order_by(GenerationRun.created_at.asc())
            )
        )

    def _aggregate_snapshot(
        self,
        parent: GenerationRun,
        *,
        batch_id: str | None = None,
        include_prompt: bool = False,
    ) -> dict[str, Any]:
        children = self._children(parent)
        snapshot = {
            "child_run_ids": [str(child.id) for child in children],
            "completed_layers": [
                child.asset_layer
                for child in children
                if child.status == COMPLETED_STATUS and child.asset_layer
            ],
            "failed_layers": [
                child.asset_layer
                for child in children
                if child.status == FAILED_STATUS and child.asset_layer
            ],
            "asset_ids": {},
            "change_set_ids": [],
            "batch_id": batch_id or (parent.queue_payload or {}).get("batch_id"),
        }
        for child in children:
            output = child.output_snapshot or {}
            snapshot["asset_ids"].update(output.get("asset_ids", {}))
            snapshot["change_set_ids"].extend(output.get("change_set_ids", []))
            if include_prompt or child.run_type == PROMPT_PACK_RUN_TYPE:
                snapshot.setdefault("context_pack_ids", []).extend(
                    output.get("context_pack_ids", [])
                )
        return snapshot

    def _new_run(
        self,
        *,
        project_id: UUID,
        requirement_id: UUID | None,
        run_type: str,
        module: str,
        queue_payload: dict[str, Any],
        input_snapshot: dict[str, Any],
        parent_run_id: UUID | None = None,
        asset_layer: str | None = None,
        status: str = QUEUE_STATUS,
    ) -> GenerationRun:
        now = datetime.now(UTC)
        run = GenerationRun(
            project_id=project_id,
            requirement_id=requirement_id,
            run_type=run_type,
            parent_run_id=parent_run_id,
            asset_layer=asset_layer,
            status=status,
            progress=0,
            message=_queued_message(module),
            queue_payload=queue_payload,
            input_snapshot=input_snapshot,
            queued_at=now,
            next_attempt_at=now if status == QUEUE_STATUS else None,
            max_attempts=settings.queue_max_attempts,
        )
        self.db.add(run)
        self.db.flush()
        return run

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

    def mark_retry_or_failed(self, run: GenerationRun, exc: Exception) -> GenerationRun:
        self.db.rollback()
        run = self.get_run(run.id)
        worker_id = run.locked_by
        if run.status == FAILED_STATUS and not _is_retryable(exc):
            run.locked_at = None
            run.locked_by = None
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            logger.warning(
                "generation.worker.job.failed worker_id=%s run_id=%s run_type=%s "
                "status=%s error=%s",
                worker_id,
                run.id,
                run.run_type,
                run.status,
                _excerpt(str(exc), 300),
            )
            return run
        if _is_retryable(exc) and run.attempt_count < run.max_attempts:
            delay_seconds = 2 ** max(run.attempt_count - 1, 0)
            run.status = QUEUE_STATUS
            run.progress = 0
            run.message = f"任务执行失败，将在 {delay_seconds} 秒后重试。"
            run.error_message = _excerpt(str(exc), 1000)
            run.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            run.locked_at = None
            run.locked_by = None
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            logger.warning(
                "generation.worker.job.retry_scheduled worker_id=%s run_id=%s "
                "run_type=%s attempt=%s/%s retry_in_seconds=%s error=%s",
                worker_id,
                run.id,
                run.run_type,
                run.attempt_count,
                run.max_attempts,
                delay_seconds,
                _excerpt(str(exc), 300),
            )
            return run

        run.status = FAILED_STATUS
        run.message = _failure_message(run)
        run.error_message = _excerpt(str(exc), 1000)
        run.completed_at = datetime.now(UTC)
        run.locked_at = None
        run.locked_by = None
        self.db.add(run)
        self.db.commit()
        if run.parent_run_id is not None:
            parent = self.db.get(GenerationRun, run.parent_run_id)
            if parent is not None:
                self._aggregate_parent(parent)
                self.db.refresh(run)
        self.db.refresh(run)
        logger.exception(
            "generation.worker.job.failed worker_id=%s run_id=%s run_type=%s "
            "attempt=%s/%s error=%s",
            worker_id,
            run.id,
            run.run_type,
            run.attempt_count,
            run.max_attempts,
            _excerpt(str(exc), 300),
        )
        return run

    def recover_stale_runs(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.queue_stale_after_seconds)
        runs = list(
            self.db.scalars(
                select(GenerationRun).where(
                    GenerationRun.status == RUNNING_STATUS,
                    GenerationRun.locked_at.is_not(None),
                    GenerationRun.locked_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            )
        )
        recovered = 0
        for run in runs:
            if run.attempt_count < run.max_attempts:
                run.status = QUEUE_STATUS
                run.progress = 0
                run.message = "检测到任务执行超时，已重新加入队列。"
                run.next_attempt_at = datetime.now(UTC)
                run.locked_at = None
                run.locked_by = None
            else:
                run.status = FAILED_STATUS
                run.message = _failure_message(run)
                run.error_message = "Generation run exceeded stale recovery attempts."
                run.completed_at = datetime.now(UTC)
                run.locked_at = None
                run.locked_by = None
            self.db.add(run)
            recovered += 1
        self.db.commit()
        if recovered:
            logger.warning("generation.worker.stale_runs.recovered count=%s", recovered)
        return recovered

    def run_once(self, worker_id: str) -> GenerationRun | None:
        run = self.claim_next_job(worker_id)
        if run is None:
            return None
        return self.execute_run(run.id)

    def _enqueue(
        self,
        *,
        project_id: UUID,
        requirement_id: UUID | None,
        run_type: str,
        module: str,
        queue_payload: dict[str, Any],
        input_snapshot: dict[str, Any],
        parent_run_id: UUID | None = None,
        asset_layer: str | None = None,
    ) -> GenerationRun:
        self._ensure_active_worker()
        now = datetime.now(UTC)
        run = GenerationRun(
            project_id=project_id,
            requirement_id=requirement_id,
            run_type=run_type,
            parent_run_id=parent_run_id,
            asset_layer=asset_layer,
            status=QUEUE_STATUS,
            progress=0,
            message=_queued_message(module),
            queue_payload=queue_payload,
            input_snapshot=input_snapshot,
            queued_at=now,
            next_attempt_at=now,
            max_attempts=settings.queue_max_attempts,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _ensure_active_worker(self) -> None:
        if self.has_active_worker():
            return
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=WORKER_OFFLINE_DETAIL,
        )

    def _ensure_project_access(self, project_id: UUID) -> None:
        if self.current_user is None:
            return
        ProjectService(self.db, self.current_user).get_project(project_id)

    def _get_change_set_for_workflow(self, change_set_id: UUID) -> ChangeSet:
        change_set = self.db.get(ChangeSet, change_set_id)
        if change_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Change set not found.",
            )
        self._ensure_project_access(change_set.project_id)
        return change_set

    def _find_active_change_set_run(
        self,
        change_set_id: UUID,
        run_type: str,
    ) -> GenerationRun | None:
        return self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.run_type == run_type,
                GenerationRun.status.in_(
                    [QUEUE_STATUS, RUNNING_STATUS, "waiting", "partially_completed"]
                ),
                GenerationRun.queue_payload["change_set_id"].as_string()
                == str(change_set_id),
            )
            .order_by(GenerationRun.created_at.desc())
            .limit(1)
        )

    def _find_active_apply_change_set_run(self, change_set: ChangeSet) -> GenerationRun | None:
        active_statuses = [QUEUE_STATUS, RUNNING_STATUS, "waiting", "partially_completed"]
        conditions = [
            GenerationRun.run_type == APPLY_CHANGE_SET_RUN_TYPE,
            GenerationRun.status.in_(active_statuses),
        ]
        if change_set.batch_id is not None:
            conditions.append(GenerationRun.project_id == change_set.project_id)
            batch_match = GenerationRun.queue_payload["batch_id"].as_string() == str(
                change_set.batch_id
            )
            batch_change_set_ids = [
                str(item.id) for item in self._batch_change_sets(change_set)
            ]
            conditions.append(
                or_(
                    batch_match,
                    GenerationRun.queue_payload["change_set_id"].as_string().in_(
                        batch_change_set_ids
                    ),
                )
            )
        else:
            conditions.append(
                GenerationRun.queue_payload["change_set_id"].as_string()
                == str(change_set.id)
            )
        return self.db.scalar(
            select(GenerationRun)
            .where(*conditions)
            .order_by(GenerationRun.created_at.desc())
            .limit(1)
        )

    def _get_change_set_for_batch(self, project_id: UUID, batch_id: UUID) -> ChangeSet:
        change_set = self.db.scalar(
            select(ChangeSet)
            .where(
                ChangeSet.project_id == project_id,
                ChangeSet.batch_id == batch_id,
                ChangeSet.is_current.is_(True),
                ChangeSet.status.in_(list(APPLIABLE_STATUSES)),
            )
            .order_by(ChangeSet.created_at.asc())
            .limit(1)
        )
        if change_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Applicable change set batch not found.",
            )
        return change_set

    def _find_active_requirement_run(
        self,
        project_id: UUID,
        requirement_id: UUID | None,
        run_type: str,
    ) -> GenerationRun | None:
        if requirement_id is None:
            return None
        return self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.project_id == project_id,
                GenerationRun.requirement_id == requirement_id,
                GenerationRun.run_type == run_type,
                GenerationRun.status.in_({QUEUE_STATUS, RUNNING_STATUS}),
            )
            .order_by(GenerationRun.created_at.desc())
            .limit(1)
        )

    def _build_spec_for_run(self, run: GenerationRun):
        payload = run.queue_payload or {}
        project_id = UUID(str(payload.get("project_id") or run.project_id))
        service = StreamingGenerationService(self.db)
        if run.run_type == BUSINESS_STORY_RUN_TYPE:
            request = GenerateBusinessRequirementStoriesRequest(
                requirement_id=(
                    UUID(str(payload["requirement_id"])) if payload.get("requirement_id") else None
                ),
                overwrite=bool(payload.get("overwrite", False)),
            )
            return service.build_business_stories_spec(project_id, request)
        if run.run_type == BLUEPRINT_RUN_TYPE:
            return service.build_blueprint_spec(project_id)
        if run.run_type == API_CONTRACT_RUN_TYPE:
            return service.build_api_contract_spec(project_id)
        if run.run_type == DB_MODEL_RUN_TYPE:
            return service.build_db_model_spec(project_id)
        raise ValueError(f"Unsupported generation run type: {run.run_type}")


def run_worker_loop(
    worker_id: str | None = None,
    *,
    stop_after_idle: bool = False,
    concurrency: int | None = None,
) -> None:
    resolved_concurrency = concurrency or settings.queue_worker_concurrency
    if resolved_concurrency < 1:
        raise ValueError("Worker concurrency must be at least 1.")

    base_worker_id = worker_id or settings.queue_worker_id or _default_worker_id()
    worker_ids = _worker_ids(base_worker_id, resolved_concurrency)
    if resolved_concurrency == 1:
        logger.info(
            "generation.worker.start concurrency=1 worker_id=%s",
            worker_ids[0],
        )
        _run_worker_slot(worker_ids[0], stop_after_idle=stop_after_idle)
        return

    logger.info(
        "generation.worker_pool.start concurrency=%s base_worker_id=%s",
        resolved_concurrency,
        _fit_worker_id(base_worker_id),
    )
    with ThreadPoolExecutor(
        max_workers=resolved_concurrency,
        thread_name_prefix="generation-worker",
    ) as executor:
        futures = [
            executor.submit(_run_worker_slot, slot_worker_id, stop_after_idle=stop_after_idle)
            for slot_worker_id in worker_ids
        ]
        for future in futures:
            future.result()


def _run_worker_slot(worker_id: str, *, stop_after_idle: bool) -> None:
    from app.db.session import SessionLocal

    logger.info("generation.worker.slot.start worker_id=%s", worker_id)
    idle_logged = False
    while True:
        with SessionLocal() as db:
            service = GenerationQueueService(db)
            service.heartbeat_worker(worker_id)
            service.recover_stale_runs()
            run = service.run_once(worker_id)
        if run is None:
            if stop_after_idle:
                logger.info("generation.worker.slot.stop_after_idle worker_id=%s", worker_id)
                return
            if not idle_logged:
                logger.info(
                    "generation.worker.slot.idle worker_id=%s poll_interval_seconds=%s",
                    worker_id,
                    settings.queue_poll_interval_seconds,
                )
                idle_logged = True
            time.sleep(settings.queue_poll_interval_seconds)
            continue
        idle_logged = False


def _queued_message(module: str) -> str:
    if module == "business_stories":
        return "业务需求故事更新已加入后台队列。"
    if module == "context_packs":
        return "Context Pack 生成已加入后台队列。"
    if module == "change_set":
        return "变更集生成已加入后台队列。"
    if module == "apply_change_set":
        return "变更集应用已加入后台队列。"
    if module == "prompt_pack":
        return "指令集合生成已加入后台队列。"
    return "生成任务已加入后台队列。"


def _ordered_layers(
    affected_layers: list[str], order: list[str], preferred_layer: str | None = None
) -> list[str]:
    if preferred_layer in order:
        return [preferred_layer]
    affected = set(affected_layers or [])
    return [layer for layer in order if layer in affected]


def _failure_message(run: GenerationRun) -> str:
    if run.run_type == BUSINESS_STORY_RUN_TYPE:
        return "业务需求故事更新失败"
    if run.run_type == CHANGE_SET_RUN_TYPE:
        return "变更集生成失败"
    if run.run_type == APPLY_CHANGE_SET_RUN_TYPE:
        return "变更集应用失败"
    if run.run_type == PROMPT_PACK_RUN_TYPE:
        return "指令集合生成失败"
    return "生成失败"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, LLMRequestError):
        return True
    if isinstance(exc, HTTPException):
        return exc.detail == REQUEST_ERROR_DETAIL
    return False


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


def _worker_ids(base_worker_id: str, concurrency: int) -> list[str]:
    if concurrency == 1:
        return [_fit_worker_id(base_worker_id)]
    return [_fit_worker_id(f"{base_worker_id}:{slot}") for slot in range(1, concurrency + 1)]


def _fit_worker_id(worker_id: str) -> str:
    if len(worker_id) <= WORKER_ID_MAX_LENGTH:
        return worker_id
    digest = sha1(worker_id.encode("utf-8")).hexdigest()[:10]
    prefix_limit = WORKER_ID_MAX_LENGTH - len(digest) - 1
    return f"{worker_id[:prefix_limit]}:{digest}"


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
