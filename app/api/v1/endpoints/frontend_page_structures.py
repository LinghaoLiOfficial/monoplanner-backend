from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.frontend_page_structure import FrontendPageStructure
from app.models.user import User
from app.schemas.design_asset import DesignAssetRead, DesignAssetUpdate
from app.services.design_asset_service import DesignAssetService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]
NOT_FOUND = "Frontend page structure not found."


@router.get(
    "/projects/{project_id}/frontend-page-structures",
    response_model=list[DesignAssetRead],
)
def list_project_frontend_page_structures(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[DesignAssetRead]:
    return DesignAssetService(db, current_user).list_project_assets(
        FrontendPageStructure, project_id
    )


@router.get("/frontend-page-structures/{asset_id}", response_model=DesignAssetRead)
def get_frontend_page_structure(
    db: DbSession, current_user: CurrentUser, asset_id: UUID
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).get_asset(
        FrontendPageStructure, asset_id, not_found_detail=NOT_FOUND
    )


@router.patch("/frontend-page-structures/{asset_id}", response_model=DesignAssetRead)
def update_frontend_page_structure(
    db: DbSession,
    current_user: CurrentUser,
    asset_id: UUID,
    payload: DesignAssetUpdate,
) -> DesignAssetRead:
    return DesignAssetService(db, current_user).update_asset(
        FrontendPageStructure, asset_id, payload, not_found_detail=NOT_FOUND
    )
