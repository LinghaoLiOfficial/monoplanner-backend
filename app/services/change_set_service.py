from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.change_set import ChangeSet
from app.models.user import User
from app.schemas.change_set import ChangeSetUpdate
from app.services.project_service import ProjectService


class ChangeSetService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def list_project_change_sets(self, project_id: UUID) -> list[ChangeSet]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        return list(
            self.db.scalars(
                select(ChangeSet)
                .where(ChangeSet.project_id == project_id)
                .order_by(ChangeSet.created_at.desc())
            )
        )

    def get_change_set(self, change_set_id: UUID) -> ChangeSet:
        change_set = self.db.get(ChangeSet, change_set_id)
        if change_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Change set not found.",
            )
        ProjectService(self.db, self.current_user).get_project(change_set.project_id)
        return change_set

    def update_change_set(self, change_set_id: UUID, payload: ChangeSetUpdate) -> ChangeSet:
        change_set = self.get_change_set(change_set_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(change_set, field, value)
        self.db.add(change_set)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set

    def apply_change_set(self, change_set_id: UUID) -> ChangeSet:
        change_set = self.get_change_set(change_set_id)
        change_set.status = "applied"
        self.db.add(change_set)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set

    def discard_change_set(self, change_set_id: UUID) -> ChangeSet:
        change_set = self.get_change_set(change_set_id)
        change_set.status = "discarded"
        self.db.add(change_set)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set
