from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import SessionLocal
from app.llm.client import LLMRequestError
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.context_pack import ContextPack
from app.models.generation_run import GenerationRun
from app.models.generation_worker import GenerationWorker
from app.services.generation_queue_service import (
    CANCELLED_STATUS,
    COMPLETED_STATUS,
    FAILED_STATUS,
    QUEUE_STATUS,
    RUNNING_STATUS,
    WORKER_OFFLINE_DETAIL,
    GenerationQueueService,
    run_worker_loop,
)
from tests.llm_stream_helpers import patch_llm_stream, patch_llm_stream_sequence
from tests.test_blueprint_generation import _mock_blueprint_content
from tests.test_business_requirement_stories import VALID_LLM_OUTPUT_DICT
from tests.test_structured_drafts import _mock_api_contract_content, _mock_db_model_content


def _create_project_with_requirement(client: TestClient, name: str = "Queue Project") -> dict:
    project = client.post("/api/v1/projects", json={"name": name}).json()
    requirement = client.post(
        f"/api/v1/projects/{project['id']}/requirements",
        json={"raw_text": "做一个可以把业务需求转成结构化上下文包的工具"},
    ).json()
    project["requirement_id"] = requirement["id"]
    return project


def _run_next(db_session: Session) -> GenerationRun:
    run = GenerationQueueService(db_session).run_once("test-worker")
    assert run is not None
    return run


def _enqueue_and_run_blueprint(client: TestClient, db_session: Session, monkeypatch) -> dict:
    project = _create_project_with_requirement(client)
    patch_llm_stream(monkeypatch, _mock_blueprint_content())
    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    assert response.status_code == 202
    run = _run_next(db_session)
    assert run.status == COMPLETED_STATUS
    return project


def test_enqueue_returns_queued_run_and_status_endpoint(client: TestClient) -> None:
    project = _create_project_with_requirement(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/generate/business-stories",
        json={"requirement_id": project["requirement_id"], "overwrite": False},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == QUEUE_STATUS
    assert payload["progress"] == 0
    assert payload["queue_payload"]["project_id"] == project["id"]
    assert payload["queue_payload"]["requirement_id"] == project["requirement_id"]
    status_response = client.get(f"/api/v1/generation-runs/{payload['id']}")
    assert status_response.status_code == 200
    assert status_response.json()["id"] == payload["id"]


def test_enqueue_returns_503_when_worker_is_offline(
    client: TestClient, db_session: Session
) -> None:
    project = _create_project_with_requirement(client)
    db_session.query(GenerationRun).delete()
    from app.models.generation_worker import GenerationWorker

    db_session.query(GenerationWorker).delete()
    db_session.commit()

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    assert response.status_code == 503
    assert response.json()["detail"] == WORKER_OFFLINE_DETAIL
    assert db_session.scalars(select(GenerationRun)).all() == []


def test_claim_next_job_locks_oldest_run(client: TestClient, db_session: Session) -> None:
    first_project = _create_project_with_requirement(client)
    second_project = client.post("/api/v1/projects", json={"name": "Queue Project 2"}).json()
    client.post(
        f"/api/v1/projects/{second_project['id']}/requirements",
        json={"raw_text": "另一个需求"},
    )
    first = client.post(f"/api/v1/projects/{first_project['id']}/generate/blueprint").json()
    second = client.post(f"/api/v1/projects/{second_project['id']}/generate/blueprint").json()

    claimed = GenerationQueueService(db_session).claim_next_job("worker-a")

    assert claimed is not None
    assert str(claimed.id) == first["id"]
    assert claimed.status == RUNNING_STATUS
    assert claimed.locked_by == "worker-a"
    assert claimed.locked_at is not None
    remaining = db_session.get(GenerationRun, second["id"])
    assert remaining.status == QUEUE_STATUS


def test_run_worker_loop_single_concurrency_uses_base_worker_id(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    queued = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()

    def complete_run(self, run_id):
        run = self.get_run(run_id)
        run.status = COMPLETED_STATUS
        run.progress = 100
        run.completed_at = datetime.now(UTC)
        run.locked_at = None
        run.locked_by = None
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    monkeypatch.setattr(GenerationQueueService, "execute_run", complete_run)

    run_worker_loop(worker_id="single-worker", stop_after_idle=True, concurrency=1)

    db_session.expire_all()
    run = db_session.get(GenerationRun, queued["id"])
    worker_ids = set(db_session.scalars(select(GenerationWorker.worker_id)).all())
    assert run.status == COMPLETED_STATUS
    assert "single-worker" in worker_ids
    assert "single-worker:1" not in worker_ids


def test_run_worker_loop_concurrency_executes_multiple_runs_once(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    projects = [
        _create_project_with_requirement(client, f"Queue Project {index}") for index in range(3)
    ]
    queued_ids = [
        client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()["id"]
        for project in projects
    ]
    executed_run_ids: list[str] = []
    locked_by_values: list[str] = []
    lock = Lock()
    execution_barrier = Barrier(3, timeout=5)

    def complete_run(self, run_id):
        run = self.get_run(run_id)
        with lock:
            executed_run_ids.append(str(run.id))
            locked_by_values.append(str(run.locked_by))
        execution_barrier.wait()
        run.status = COMPLETED_STATUS
        run.progress = 100
        run.completed_at = datetime.now(UTC)
        run.locked_at = None
        run.locked_by = None
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    monkeypatch.setattr(GenerationQueueService, "execute_run", complete_run)

    run_worker_loop(worker_id="pool-worker", stop_after_idle=True, concurrency=3)

    db_session.expire_all()
    runs = db_session.scalars(select(GenerationRun).where(GenerationRun.id.in_(queued_ids))).all()
    worker_ids = set(db_session.scalars(select(GenerationWorker.worker_id)).all())
    assert {run.status for run in runs} == {COMPLETED_STATUS}
    assert sorted(executed_run_ids) == sorted(queued_ids)
    assert len(executed_run_ids) == len(set(executed_run_ids))
    assert worker_ids.issuperset({"pool-worker:1", "pool-worker:2", "pool-worker:3"})
    assert set(locked_by_values).issubset({"pool-worker:1", "pool-worker:2", "pool-worker:3"})
    assert len(set(locked_by_values)) >= 2


def test_cancel_only_allows_queued_runs(client: TestClient, db_session: Session) -> None:
    project = _create_project_with_requirement(client)
    queued = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()

    cancel_response = client.post(f"/api/v1/generation-runs/{queued['id']}/cancel")

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == CANCELLED_STATUS
    running = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()
    GenerationQueueService(db_session).claim_next_job("worker-a")
    conflict = client.post(f"/api/v1/generation-runs/{running['id']}/cancel")
    assert conflict.status_code == 409


def test_worker_executes_all_generation_modules(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    patch_llm_stream_sequence(
        monkeypatch,
        VALID_LLM_OUTPUT_DICT,
        _mock_blueprint_content(),
        _mock_api_contract_content(),
        _mock_db_model_content(),
    )

    for path in (
        "business-stories",
        "blueprint",
        "api-contract",
        "db-model",
        "context-packs",
    ):
        response = client.post(
            f"/api/v1/projects/{project['id']}/generate/{path}",
            json={} if path == "business-stories" else None,
        )
        assert response.status_code == 202
        run = _run_next(db_session)
        assert run.status == COMPLETED_STATUS

    assert len(db_session.scalars(select(BusinessRequirementStory)).all()) == 2
    assert len(db_session.scalars(select(ProjectBlueprint)).all()) == 1
    assert len(db_session.scalars(select(ContextPack)).all()) == 2


def test_retryable_llm_request_failure_is_requeued(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)

    def fail_request(*_args, **_kwargs):
        raise LLMRequestError("temporary upstream failure")
        yield ""

    monkeypatch.setattr("app.llm.client.OpenAICompatibleLLMClient.stream", fail_request)
    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    run_id = response.json()["id"]

    run = _run_next(db_session)

    assert str(run.id) == run_id
    assert run.status == QUEUE_STATUS
    assert run.attempt_count == 1
    assert run.next_attempt_at is not None


def test_non_retryable_format_failure_becomes_failed(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    monkeypatch.setattr(
        "app.llm.client.OpenAICompatibleLLMClient.stream",
        lambda *_args, **_kwargs: iter(["not json"]),
    )
    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")

    run = _run_next(db_session)

    assert str(run.id) == response.json()["id"]
    assert run.status == FAILED_STATUS
    assert run.completed_at is not None


def test_stale_running_runs_are_recovered(client: TestClient, db_session: Session) -> None:
    project = _create_project_with_requirement(client)
    run = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()
    claimed = GenerationQueueService(db_session).claim_next_job("worker-a")
    claimed.locked_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(claimed)
    db_session.commit()

    recovered = GenerationQueueService(db_session).recover_stale_runs()

    assert recovered == 1
    refreshed = db_session.get(GenerationRun, run["id"])
    assert refreshed.status == QUEUE_STATUS
    assert refreshed.locked_by is None


def test_stale_running_recovery_is_safe_under_concurrent_workers(
    client: TestClient, db_session: Session
) -> None:
    project = _create_project_with_requirement(client)
    run = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint").json()
    claimed = GenerationQueueService(db_session).claim_next_job("worker-a")
    claimed.locked_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(claimed)
    db_session.commit()

    def recover_in_new_session() -> int:
        with SessionLocal() as db:
            return GenerationQueueService(db).recover_stale_runs()

    with ThreadPoolExecutor(max_workers=2) as executor:
        recovered_counts = list(executor.map(lambda _: recover_in_new_session(), range(2)))

    db_session.expire_all()
    refreshed = db_session.get(GenerationRun, run["id"])
    assert sum(recovered_counts) == 1
    assert refreshed.status == QUEUE_STATUS
    assert refreshed.locked_by is None


def test_queue_worker_concurrency_settings_validation() -> None:
    assert Settings(queue_worker_concurrency=3).queue_worker_concurrency == 3
    with pytest.raises(ValidationError):
        Settings(queue_worker_concurrency=0)


def test_stream_endpoints_are_deprecated(client: TestClient) -> None:
    project = _create_project_with_requirement(client)

    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint/stream")

    assert response.status_code == 410
    assert "已弃用" in response.json()["detail"]


def test_execute_run_never_leaves_unknown_exception_running(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    project = _create_project_with_requirement(client)
    response = client.post(f"/api/v1/projects/{project['id']}/generate/blueprint")
    run = GenerationQueueService(db_session).claim_next_job("worker-a")

    def fail_spec(*_args, **_kwargs):
        raise HTTPException(status_code=500, detail="boom")

    monkeypatch.setattr(
        "app.services.generation_queue_service.StreamingGenerationService.build_blueprint_spec",
        fail_spec,
    )
    result = GenerationQueueService(db_session).execute_run(run.id)

    assert str(result.id) == response.json()["id"]
    assert result.status == FAILED_STATUS
    assert result.locked_at is None
