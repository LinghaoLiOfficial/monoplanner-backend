from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.ui_design import UIDesign
from app.models.user import User
from app.schemas.ui_design import UIDesignRead, UIDesignUpdate
from app.services.design_asset_service import DesignAssetService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]
NOT_FOUND = "UI design not found."


@router.get("/projects/{project_id}/ui-designs", response_model=list[UIDesignRead])
def list_project_ui_designs(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[UIDesignRead]:
    return DesignAssetService(db, current_user).list_project_assets(UIDesign, project_id)


@router.get("/ui-designs/{ui_design_id}", response_model=UIDesignRead)
def get_ui_design(
    db: DbSession, current_user: CurrentUser, ui_design_id: UUID
) -> UIDesignRead:
    return DesignAssetService(db, current_user).get_asset(
        UIDesign, ui_design_id, not_found_detail=NOT_FOUND
    )


@router.patch("/ui-designs/{ui_design_id}", response_model=UIDesignRead)
def update_ui_design(
    db: DbSession,
    current_user: CurrentUser,
    ui_design_id: UUID,
    payload: UIDesignUpdate,
) -> UIDesignRead:
    return DesignAssetService(db, current_user).update_asset(
        UIDesign, ui_design_id, payload, not_found_detail=NOT_FOUND
    )
