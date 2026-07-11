from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.generation_run import BusinessStoryGenerationStatus
from app.schemas.requirement import RequirementCreate, RequirementRead
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/projects/{project_id}/requirements")
status_router = APIRouter(prefix="/requirements")
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=RequirementRead, status_code=status.HTTP_201_CREATED)
def create_requirement(
    db: DbSession,
    project_id: UUID,
    payload: RequirementCreate,
) -> RequirementRead:
    return RequirementService(db).create_requirement(project_id, payload)


@router.get("", response_model=list[RequirementRead])
def list_requirements(db: DbSession, project_id: UUID) -> list[RequirementRead]:
    return RequirementService(db).list_project_requirements(project_id)


@status_router.get(
    "/{requirement_id}/business-story-generation",
    response_model=BusinessStoryGenerationStatus | None,
)
def get_business_story_generation_status(
    db: DbSession,
    requirement_id: UUID,
) -> BusinessStoryGenerationStatus | None:
    return RequirementService(db).get_business_story_generation_status(requirement_id)
