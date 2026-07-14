from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.db_model_draft import DbModelDraftResponse, DbModelDraftUpdate
from app.services.db_model_service import DbModelService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/db-models", response_model=list[DbModelDraftResponse])
def list_project_db_models(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[DbModelDraftResponse]:
    return DbModelService(db, current_user).list_project_db_models(project_id)


@router.get("/db-models/{db_model_id}", response_model=DbModelDraftResponse)
def get_db_model(
    db: DbSession, current_user: CurrentUser, db_model_id: UUID
) -> DbModelDraftResponse:
    return DbModelService(db, current_user).get_db_model(db_model_id)


@router.patch("/db-models/{db_model_id}", response_model=DbModelDraftResponse)
def update_db_model(
    db: DbSession,
    current_user: CurrentUser,
    db_model_id: UUID,
    payload: DbModelDraftUpdate,
) -> DbModelDraftResponse:
    return DbModelService(db, current_user).update_db_model(db_model_id, payload)
