from uuid import UUID

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.generation_queue_service import GenerationQueueService


def run_next_generation_job(db_session: Session, worker_id: str = "test-worker"):
    run = GenerationQueueService(db_session).run_once(worker_id)
    assert run is not None
    return run


def run_generation_job(db_session: Session, run_id: str | UUID, worker_id: str = "test-worker"):
    return GenerationQueueService(db_session).execute_run(UUID(str(run_id)))


def run_next_generation_job_in_new_session(worker_id: str = "test-worker"):
    with SessionLocal() as db:
        run = GenerationQueueService(db).run_once(worker_id)
        assert run is not None
        return run


def run_generation_job_in_new_session(run_id: str | UUID, worker_id: str = "test-worker"):
    with SessionLocal() as db:
        service = GenerationQueueService(db)
        root_id = UUID(str(run_id))
        service.execute_run(root_id)
        for _ in range(32):
            refreshed = service.get_run(root_id)
            if refreshed.status in {"completed", "failed", "partially_completed"}:
                return refreshed
            next_run = service.run_once(worker_id)
            if next_run is None:
                return service.get_run(root_id)
        return service.get_run(root_id)
