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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import REQUEST_ERROR_DETAIL
from app.models.generation_run import GenerationRun
from app.models.generation_worker import GenerationWorker
from app.models.user import User
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.api_contract_service import RUN_TYPE as API_CONTRACT_RUN_TYPE
from app.services.business_story_generation_service import RUN_TYPE as BUSINESS_STORY_RUN_TYPE
from app.services.context_pack_service import ContextPackService
from app.services.db_model_service import RUN_TYPE as DB_MODEL_RUN_TYPE
from app.services.generation_service import RUN_TYPE as BLUEPRINT_RUN_TYPE
from app.services.project_service import ProjectService
from app.services.streaming_generation_service import StreamingGenerationService

logger = logging.getLogger(__name__)

CONTEXT_PACK_RUN_TYPE = "generate_context_packs"
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

        try:
            if run.run_type == CONTEXT_PACK_RUN_TYPE:
                ContextPackService(self.db).execute_context_pack_run(run)
            else:
                spec = self._build_spec_for_run(run)
                StreamingGenerationService(self.db).execute_existing_run(run, spec)
            run.locked_at = None
            run.locked_by = None
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            return self.mark_retry_or_failed(run, exc)

    def mark_retry_or_failed(self, run: GenerationRun, exc: Exception) -> GenerationRun:
        self.db.rollback()
        run = self.get_run(run.id)
        if run.status == FAILED_STATUS and not _is_retryable(exc):
            run.locked_at = None
            run.locked_by = None
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
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
            return run

        run.status = FAILED_STATUS
        run.message = _failure_message(run)
        run.error_message = _excerpt(str(exc), 1000)
        run.completed_at = datetime.now(UTC)
        run.locked_at = None
        run.locked_by = None
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
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
    ) -> GenerationRun:
        self._ensure_active_worker()
        now = datetime.now(UTC)
        run = GenerationRun(
            project_id=project_id,
            requirement_id=requirement_id,
            run_type=run_type,
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

    while True:
        with SessionLocal() as db:
            service = GenerationQueueService(db)
            service.heartbeat_worker(worker_id)
            service.recover_stale_runs()
            run = service.run_once(worker_id)
        if run is None:
            if stop_after_idle:
                return
            time.sleep(settings.queue_poll_interval_seconds)


def _queued_message(module: str) -> str:
    if module == "business_stories":
        return "业务需求故事更新已加入后台队列。"
    if module == "context_packs":
        return "Context Pack 生成已加入后台队列。"
    return "生成任务已加入后台队列。"


def _failure_message(run: GenerationRun) -> str:
    if run.run_type == BUSINESS_STORY_RUN_TYPE:
        return "业务需求故事更新失败"
    return "生成失败"


def _is_retryable(exc: Exception) -> bool:
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
