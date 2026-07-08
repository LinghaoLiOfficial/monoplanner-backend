from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.requirement import Requirement
from app.schemas.requirement import RequirementCreate
from app.services.project_service import ProjectService


class RequirementService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_requirement(self, project_id: UUID, payload: RequirementCreate) -> Requirement:
        ProjectService(self.db).get_project(project_id)
        requirement = Requirement(project_id=project_id, **payload.model_dump())
        self.db.add(requirement)
        self.db.commit()
        self.db.refresh(requirement)
        return requirement

    def list_project_requirements(self, project_id: UUID) -> list[Requirement]:
        ProjectService(self.db).get_project(project_id)
        return list(
            self.db.scalars(
                select(Requirement)
                .where(Requirement.project_id == project_id)
                .order_by(Requirement.created_at.desc())
            )
        )

    def get_latest_requirement(self, project_id: UUID) -> Requirement | None:
        return self.db.scalar(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.created_at.desc())
            .limit(1)
        )
