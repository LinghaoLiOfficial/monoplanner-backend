from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.backend_service_design import BackendImplementation, BackendServiceDesign
from app.models.user import User
from app.schemas.design_asset import DesignAssetRead, DesignAssetUpdate
from app.services.design_asset_service import DesignAssetService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]
NOT_FOUND = "Backend service design not found."


@router.get(
    "/projects/{project_id}/backend-service-designs",
    response_model=list[DesignAssetRead],
)
def list_project_backend_service_designs(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[DesignAssetRead]:
    return DesignAssetService(db, current_user).list_project_assets(
        BackendServiceDesign, project_id
    )


@router.get(
    "/projects/{project_id}/backend-implementations",
    response_model=list[DesignAssetRead],
)
def list_project_backend_implementations(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[DesignAssetRead]:
    return DesignAssetService(db, current_user).list_project_assets(
        BackendImplementation, project_id
    )


@router.get("/backend-service-designs/{asset_id}", response_model=DesignAssetRead)
def get_backend_service_design(
    db: DbSession, current_user: CurrentUser, asset_id: UUID
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).get_asset(
        BackendServiceDesign, asset_id, not_found_detail=NOT_FOUND
    )


@router.patch("/backend-service-designs/{asset_id}", response_model=DesignAssetRead)
def update_backend_service_design(
    db: DbSession,
    current_user: CurrentUser,
    asset_id: UUID,
    payload: DesignAssetUpdate,
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).update_asset(
        BackendServiceDesign, asset_id, payload, not_found_detail=NOT_FOUND
    )


@router.get("/backend-implementations/{asset_id}", response_model=DesignAssetRead)
def get_backend_implementation(
    db: DbSession, current_user: CurrentUser, asset_id: UUID
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).get_asset(
        BackendImplementation, asset_id, not_found_detail="Backend implementation not found."
    )


@router.patch("/backend-implementations/{asset_id}", response_model=DesignAssetRead)
def update_backend_implementation(
    db: DbSession,
    current_user: CurrentUser,
    asset_id: UUID,
    payload: DesignAssetUpdate,
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).update_asset(
        BackendImplementation,
        asset_id,
        payload,
        not_found_detail="Backend implementation not found.",
    )
