from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
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
from app.services.context_pack_service import ContextPackService
from app.services.streaming_generation_service import SSE_HEADERS, StreamingGenerationService

router = APIRouter(prefix="/projects/{project_id}/generate")
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/blueprint",
    response_model=ProjectBlueprintRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_blueprint(db: DbSession, project_id: UUID) -> ProjectBlueprintRead:
    service = StreamingGenerationService(db)
    return service.generate(service.build_blueprint_spec(project_id))


@router.post("/blueprint/stream")
def generate_blueprint_stream(db: DbSession, project_id: UUID) -> StreamingResponse:
    service = StreamingGenerationService(db)
    spec = service.build_blueprint_spec(project_id)
    return StreamingResponse(
        service.stream(spec),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/api-contract",
    response_model=ApiContractDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_api_contract(db: DbSession, project_id: UUID) -> ApiContractDraftResponse:
    service = StreamingGenerationService(db)
    return service.generate(service.build_api_contract_spec(project_id))


@router.post("/api-contract/stream")
def generate_api_contract_stream(db: DbSession, project_id: UUID) -> StreamingResponse:
    service = StreamingGenerationService(db)
    spec = service.build_api_contract_spec(project_id)
    return StreamingResponse(
        service.stream(spec),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/db-model",
    response_model=DbModelDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_db_model(db: DbSession, project_id: UUID) -> DbModelDraftResponse:
    service = StreamingGenerationService(db)
    return service.generate(service.build_db_model_spec(project_id))


@router.post("/db-model/stream")
def generate_db_model_stream(db: DbSession, project_id: UUID) -> StreamingResponse:
    service = StreamingGenerationService(db)
    spec = service.build_db_model_spec(project_id)
    return StreamingResponse(
        service.stream(spec),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


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
    service = StreamingGenerationService(db)
    stories = service.generate(service.build_business_stories_spec(project_id, payload))
    return GenerateBusinessRequirementStoriesResponse(items=stories)


@router.post("/business-stories/stream")
def generate_business_stories_stream(
    db: DbSession,
    project_id: UUID,
    payload: GenerateBusinessRequirementStoriesRequest,
) -> StreamingResponse:
    service = StreamingGenerationService(db)
    spec = service.build_business_stories_spec(project_id, payload)
    return StreamingResponse(
        service.stream(spec),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
