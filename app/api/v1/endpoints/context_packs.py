from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.context_pack import (
    ContextPackExportResponse,
    ContextPackResponse,
    ContextPackUpdate,
    PromptPackGenerateRequest,
)
from app.schemas.generation_run import GenerationRunRead
from app.services.context_pack_service import ContextPackService
from app.services.generation_queue_service import GenerationQueueService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/context-packs", response_model=list[ContextPackResponse])
def list_project_context_packs(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    role: str | None = None,
) -> list[ContextPackResponse]:
    return ContextPackService(db, current_user).list_project_context_packs(project_id, role)


@router.get("/context-packs/{context_pack_id}", response_model=ContextPackResponse)
def get_context_pack(
    db: DbSession, current_user: CurrentUser, context_pack_id: UUID
) -> ContextPackResponse:
    return ContextPackService(db, current_user).get_context_pack(context_pack_id)


@router.patch("/context-packs/{context_pack_id}", response_model=ContextPackResponse)
def update_context_pack(
    db: DbSession,
    current_user: CurrentUser,
    context_pack_id: UUID,
    payload: ContextPackUpdate,
) -> ContextPackResponse:
    return ContextPackService(db, current_user).update_context_pack(context_pack_id, payload)


@router.post("/context-packs/{context_pack_id}/export", response_model=ContextPackExportResponse)
def export_context_pack(
    db: DbSession, current_user: CurrentUser, context_pack_id: UUID
) -> ContextPackExportResponse:
    return ContextPackService(db, current_user).export_context_pack(context_pack_id)


@router.get("/projects/{project_id}/prompt-packs", response_model=list[ContextPackResponse])
def list_project_prompt_packs(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    role: str | None = None,
) -> list[ContextPackResponse]:
    return ContextPackService(db, current_user).list_project_context_packs(project_id, role)


@router.get("/prompt-packs/{context_pack_id}", response_model=ContextPackResponse)
def get_prompt_pack(
    db: DbSession, current_user: CurrentUser, context_pack_id: UUID
) -> ContextPackResponse:
    return ContextPackService(db, current_user).get_context_pack(context_pack_id)


@router.post(
    "/projects/{project_id}/prompt-packs/generate",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_prompt_pack(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    payload: PromptPackGenerateRequest,
) -> GenerationRunRead:
    return GenerationQueueService(db, current_user).enqueue_prompt_pack(
        project_id,
        payload.change_set_id,
    )
