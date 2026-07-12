from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.consistency import ConsistencyCheckResponse
from app.services.consistency_service import ConsistencyService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/consistency-check", response_model=ConsistencyCheckResponse)
def check_project_consistency(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> ConsistencyCheckResponse:
    return ConsistencyService(db, current_user).check_project_consistency(project_id)
