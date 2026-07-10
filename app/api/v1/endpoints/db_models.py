from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.db_model_draft import DbModelDraftResponse
from app.services.db_model_service import DbModelService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/db-models", response_model=list[DbModelDraftResponse])
def list_project_db_models(db: DbSession, project_id: UUID) -> list[DbModelDraftResponse]:
    return DbModelService(db).list_project_db_models(project_id)


@router.get("/db-models/{db_model_id}", response_model=DbModelDraftResponse)
def get_db_model(db: DbSession, db_model_id: UUID) -> DbModelDraftResponse:
    return DbModelService(db).get_db_model(db_model_id)
