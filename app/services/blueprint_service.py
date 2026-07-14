from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.blueprint import ProjectBlueprint
from app.models.user import User
from app.schemas.blueprint import ProjectBlueprintUpdate
from app.services.design_asset_service import DesignAssetService
from app.services.project_service import ProjectService


class BlueprintService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def list_project_blueprints(self, project_id: UUID) -> list[ProjectBlueprint]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        return list(
            self.db.scalars(
                select(ProjectBlueprint)
                .where(ProjectBlueprint.project_id == project_id)
                .order_by(ProjectBlueprint.created_at.desc())
            )
        )

    def get_blueprint(self, blueprint_id: UUID) -> ProjectBlueprint:
        blueprint = self.db.get(ProjectBlueprint, blueprint_id)
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project blueprint not found.",
            )
        ProjectService(self.db, self.current_user).get_project(blueprint.project_id)
        return blueprint

    def get_next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(ProjectBlueprint)
            .where(ProjectBlueprint.project_id == project_id)
            .order_by(ProjectBlueprint.version.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1

    def get_latest_blueprint(self, project_id: UUID) -> ProjectBlueprint | None:
        return self.db.scalar(
            select(ProjectBlueprint)
            .where(ProjectBlueprint.project_id == project_id)
            .order_by(ProjectBlueprint.created_at.desc())
            .limit(1)
        )

    def update_blueprint(
        self, blueprint_id: UUID, payload: ProjectBlueprintUpdate
    ) -> ProjectBlueprint:
        return DesignAssetService(self.db, self.current_user).update_asset(
            ProjectBlueprint,
            blueprint_id,
            payload,
            not_found_detail="Project blueprint not found.",
        )
