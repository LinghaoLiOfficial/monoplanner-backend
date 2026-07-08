from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.blueprint import ProjectBlueprintRead
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/projects/{project_id}/generate")
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/blueprint",
    response_model=ProjectBlueprintRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_blueprint(db: DbSession, project_id: UUID) -> ProjectBlueprintRead:
    return GenerationService(db).generate_project_blueprint(project_id)
