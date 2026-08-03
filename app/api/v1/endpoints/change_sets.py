from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.change_set import ChangeSetRead, ChangeSetUpdate
from app.schemas.generation_run import GenerationRunRead
from app.services.change_set_service import ChangeSetService
from app.services.generation_queue_service import GenerationQueueService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/change-sets", response_model=list[ChangeSetRead])
def list_project_change_sets(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[ChangeSetRead]:
    return ChangeSetService(db, current_user).list_project_change_sets(project_id)


@router.get("/change-sets/{change_set_id}", response_model=ChangeSetRead)
def get_change_set(
    db: DbSession, current_user: CurrentUser, change_set_id: UUID
) -> ChangeSetRead:
    return ChangeSetService(db, current_user).get_change_set(change_set_id)


@router.patch("/change-sets/{change_set_id}", response_model=ChangeSetRead)
def update_change_set(
    db: DbSession,
    current_user: CurrentUser,
    change_set_id: UUID,
    payload: ChangeSetUpdate,
) -> ChangeSetRead:
    return ChangeSetService(db, current_user).update_change_set(change_set_id, payload)


@router.post(
    "/change-sets/{change_set_id}/apply",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def apply_change_set(
    db: DbSession, current_user: CurrentUser, change_set_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_apply_change_set(change_set_id)


@router.post("/change-sets/{change_set_id}/discard", response_model=ChangeSetRead)
def discard_change_set(
    db: DbSession, current_user: CurrentUser, change_set_id: UUID
) -> ChangeSetRead:
    return ChangeSetService(db, current_user).discard_change_set(change_set_id)


@router.post(
    "/change-sets/{change_set_id}/regenerate",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def regenerate_change_set(
    db: DbSession, current_user: CurrentUser, change_set_id: UUID
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_regenerate_change_set(change_set_id)
