from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.context_pack import ContextPackExportResponse, ContextPackResponse
from app.services.context_pack_service import ContextPackService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/context-packs", response_model=list[ContextPackResponse])
def list_project_context_packs(
    db: DbSession,
    project_id: UUID,
    role: str | None = None,
) -> list[ContextPackResponse]:
    return ContextPackService(db).list_project_context_packs(project_id, role)


@router.get("/context-packs/{context_pack_id}", response_model=ContextPackResponse)
def get_context_pack(db: DbSession, context_pack_id: UUID) -> ContextPackResponse:
    return ContextPackService(db).get_context_pack(context_pack_id)


@router.post("/context-packs/{context_pack_id}/export", response_model=ContextPackExportResponse)
def export_context_pack(db: DbSession, context_pack_id: UUID) -> ContextPackExportResponse:
    return ContextPackService(db).export_context_pack(context_pack_id)
