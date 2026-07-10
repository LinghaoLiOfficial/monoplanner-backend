from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.consistency import ConsistencyCheckResponse
from app.services.consistency_service import ConsistencyService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/consistency-check", response_model=ConsistencyCheckResponse)
def check_project_consistency(db: DbSession, project_id: UUID) -> ConsistencyCheckResponse:
    return ConsistencyService(db).check_project_consistency(project_id)
