from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.context_pack import ContextPackExportResponse, ContextPackResponse
from app.services.context_pack_service import ContextPackService

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


@router.post("/context-packs/{context_pack_id}/export", response_model=ContextPackExportResponse)
def export_context_pack(
    db: DbSession, current_user: CurrentUser, context_pack_id: UUID
) -> ContextPackExportResponse:
    return ContextPackService(db, current_user).export_context_pack(context_pack_id)
