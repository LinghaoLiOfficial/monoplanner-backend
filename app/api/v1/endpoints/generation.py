from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api_contract import ApiContractDraftResponse
from app.schemas.blueprint import ProjectBlueprintRead
from app.schemas.business_requirement_story import (
    GenerateBusinessRequirementStoriesRequest,
    GenerateBusinessRequirementStoriesResponse,
)
from app.schemas.context_pack import ContextPackResponse
from app.schemas.db_model_draft import DbModelDraftResponse
from app.services.api_contract_service import ApiContractService
from app.services.business_story_generation_service import BusinessStoryGenerationService
from app.services.context_pack_service import ContextPackService
from app.services.db_model_service import DbModelService
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


@router.post(
    "/api-contract",
    response_model=ApiContractDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_api_contract(db: DbSession, project_id: UUID) -> ApiContractDraftResponse:
    return ApiContractService(db).generate_api_contract(project_id)


@router.post(
    "/db-model",
    response_model=DbModelDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_db_model(db: DbSession, project_id: UUID) -> DbModelDraftResponse:
    return DbModelService(db).generate_db_model(project_id)


@router.post(
    "/context-packs",
    response_model=list[ContextPackResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_context_packs(db: DbSession, project_id: UUID) -> list[ContextPackResponse]:
    return ContextPackService(db).generate_context_packs(project_id)


@router.post(
    "/business-stories",
    response_model=GenerateBusinessRequirementStoriesResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_business_stories(
    db: DbSession,
    project_id: UUID,
    payload: GenerateBusinessRequirementStoriesRequest,
) -> GenerateBusinessRequirementStoriesResponse:
    stories = BusinessStoryGenerationService(db).generate_business_stories(project_id, payload)
    return GenerateBusinessRequirementStoriesResponse(items=stories)
