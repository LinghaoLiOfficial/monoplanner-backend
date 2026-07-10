from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api_contract import ApiContractDraftResponse
from app.services.api_contract_service import ApiContractService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/api-contracts", response_model=list[ApiContractDraftResponse])
def list_project_api_contracts(db: DbSession, project_id: UUID) -> list[ApiContractDraftResponse]:
    return ApiContractService(db).list_project_api_contracts(project_id)


@router.get("/api-contracts/{api_contract_id}", response_model=ApiContractDraftResponse)
def get_api_contract(db: DbSession, api_contract_id: UUID) -> ApiContractDraftResponse:
    return ApiContractService(db).get_api_contract(api_contract_id)
