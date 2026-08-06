from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.design_asset import DesignAssetUpdate
from app.services.project_service import ProjectService
from app.services.versioning import clone_versioned_row


class DesignAssetService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def list_project_assets(self, model: type[Any], project_id: UUID) -> list[Any]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        statement = (
            select(model)
            .where(model.project_id == project_id)
            .order_by(model.version.desc(), model.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_asset(self, model: type[Any], asset_id: UUID, *, not_found_detail: str) -> Any:
        asset = self.db.get(model, asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
        ProjectService(self.db, self.current_user).get_project(asset.project_id)
        return asset

    def update_asset(
        self,
        model: type[Any],
        asset_id: UUID,
        payload: DesignAssetUpdate,
        *,
        not_found_detail: str,
        extra_fields: set[str] | None = None,
    ) -> Any:
        asset = self.get_asset(model, asset_id, not_found_detail=not_found_detail)
        allowed_fields = {"title", "summary", "content", "diff_from_previous"} | (
            extra_fields or set()
        )
        updates = payload.model_dump(exclude_unset=True)
        next_version_payload = clone_versioned_row(asset, updates, allowed_fields=allowed_fields)
        next_asset = model(**next_version_payload)
        self.db.add(next_asset)
        self.db.commit()
        self.db.refresh(next_asset)
        return next_asset
