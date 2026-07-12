from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.business_requirement_story import (
    GenerateBusinessRequirementStoriesRequest,
)
from app.schemas.generation_run import GenerationRunRead
from app.services.generation_queue_service import GenerationQueueService

router = APIRouter(prefix="/projects/{project_id}/generate")
run_router = APIRouter(prefix="/generation-runs")
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.post(
    "/blueprint",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_blueprint(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_blueprint(project_id)


@router.post("/blueprint/stream")
def generate_blueprint_stream() -> None:
    raise _stream_deprecated()


@router.post(
    "/api-contract",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_api_contract(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_api_contract(project_id)


@router.post("/api-contract/stream")
def generate_api_contract_stream() -> None:
    raise _stream_deprecated()


@router.post(
    "/db-model",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_db_model(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_db_model(project_id)


@router.post("/db-model/stream")
def generate_db_model_stream() -> None:
    raise _stream_deprecated()


@router.post(
    "/context-packs",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_context_packs(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_context_packs(project_id)


@router.post(
    "/business-stories",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_business_stories(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    payload: GenerateBusinessRequirementStoriesRequest,
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_business_stories(project_id, payload)


@router.post("/business-stories/stream")
def generate_business_stories_stream(
    _: GenerateBusinessRequirementStoriesRequest,
) -> None:
    raise _stream_deprecated()


@run_router.get("/{run_id}", response_model=GenerationRunRead)
def get_generation_run(db: DbSession, current_user: CurrentUser, run_id: UUID) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).get_run(run_id)


@run_router.post("/{run_id}/cancel", response_model=GenerationRunRead)
def cancel_generation_run(
    db: DbSession, current_user: CurrentUser, run_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).cancel_queued(run_id)


def _stream_deprecated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="流式生成接口已弃用，请调用普通生成接口获取 run_id 后轮询任务状态。",
    )
