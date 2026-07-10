from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.business_requirement_story import (
    BusinessRequirementStoryResponse,
    BusinessRequirementStoryUpdate,
    BusinessStoryPriority,
    BusinessStoryStatus,
)
from app.services.business_requirement_story_service import BusinessRequirementStoryService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/projects/{project_id}/business-stories",
    response_model=list[BusinessRequirementStoryResponse],
)
def list_project_business_stories(
    db: DbSession,
    project_id: UUID,
    priority: Annotated[BusinessStoryPriority | None, Query()] = None,
    status: Annotated[BusinessStoryStatus | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> list[BusinessRequirementStoryResponse]:
    return BusinessRequirementStoryService(db).list_project_stories(
        project_id=project_id,
        priority=priority,
        status_filter=status,
        q=q,
    )


@router.get(
    "/business-stories/{story_id}",
    response_model=BusinessRequirementStoryResponse,
)
def get_business_story(db: DbSession, story_id: UUID) -> BusinessRequirementStoryResponse:
    return BusinessRequirementStoryService(db).get_story(story_id)


@router.patch(
    "/business-stories/{story_id}",
    response_model=BusinessRequirementStoryResponse,
)
def update_business_story(
    db: DbSession,
    story_id: UUID,
    payload: BusinessRequirementStoryUpdate,
) -> BusinessRequirementStoryResponse:
    return BusinessRequirementStoryService(db).update_story(story_id, payload)
