from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.models.ux_design import UXDesign
from app.schemas.ux_design import UXDesignRead, UXDesignUpdate
from app.services.design_asset_service import DesignAssetService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]
NOT_FOUND = "UX design not found."


@router.get("/projects/{project_id}/ux-designs", response_model=list[UXDesignRead])
def list_project_ux_designs(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[UXDesignRead]:
    return DesignAssetService(db, current_user).list_project_assets(UXDesign, project_id)


@router.get("/ux-designs/{ux_design_id}", response_model=UXDesignRead)
def get_ux_design(
    db: DbSession, current_user: CurrentUser, ux_design_id: UUID
) -> UXDesignRead:
    return DesignAssetService(db, current_user).get_asset(
        UXDesign, ux_design_id, not_found_detail=NOT_FOUND
    )


@router.patch("/ux-designs/{ux_design_id}", response_model=UXDesignRead)
def update_ux_design(
    db: DbSession,
    current_user: CurrentUser,
    ux_design_id: UUID,
    payload: UXDesignUpdate,
) -> UXDesignRead:
    return DesignAssetService(db, current_user).update_asset(
        UXDesign, ux_design_id, payload, not_found_detail=NOT_FOUND
    )
