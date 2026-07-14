from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.api_contract import ApiContractDraftResponse, ApiContractDraftUpdate
from app.services.api_contract_service import ApiContractService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/api-contracts", response_model=list[ApiContractDraftResponse])
def list_project_api_contracts(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[ApiContractDraftResponse]:
    return ApiContractService(db, current_user).list_project_api_contracts(project_id)


@router.get("/api-contracts/{api_contract_id}", response_model=ApiContractDraftResponse)
def get_api_contract(
    db: DbSession, current_user: CurrentUser, api_contract_id: UUID
) -> ApiContractDraftResponse:
    return ApiContractService(db, current_user).get_api_contract(api_contract_id)


@router.patch("/api-contracts/{api_contract_id}", response_model=ApiContractDraftResponse)
def update_api_contract(
    db: DbSession,
    current_user: CurrentUser,
    api_contract_id: UUID,
    payload: ApiContractDraftUpdate,
) -> ApiContractDraftResponse:
    return ApiContractService(db, current_user).update_api_contract(api_contract_id, payload)
