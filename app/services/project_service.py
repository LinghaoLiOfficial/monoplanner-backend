from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

PROJECT_NAME_EMPTY_MESSAGE = "项目名称不能为空。"
PROJECT_NAME_EXISTS_MESSAGE = "项目名称已存在，请使用其他名称。"


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, payload: ProjectCreate) -> Project:
        name = self._normalize_project_name(payload.name)
        self._ensure_name_available(name)
        project = Project(name=name, description=payload.description)
        self.db.add(project)
        self._commit_project_change()
        self.db.refresh(project)
        return project

    def list_projects(self, q: str | None = None) -> list[Project]:
        statement = select(Project)
        keyword = q.strip() if q is not None else ""
        if keyword:
            statement = statement.where(Project.name.ilike(f"%{keyword}%"))
        return list(self.db.scalars(statement.order_by(Project.created_at.desc())))

    def get_project(self, project_id: UUID) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    def update_project(self, project_id: UUID, payload: ProjectUpdate) -> Project:
        project = self.get_project(project_id)
        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates:
            if updates["name"] is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PROJECT_NAME_EMPTY_MESSAGE,
                )
            updates["name"] = self._normalize_project_name(updates["name"])
            self._ensure_name_available(updates["name"], exclude_project_id=project_id)
        for field, value in updates.items():
            setattr(project, field, value)
        self.db.add(project)
        self._commit_project_change()
        self.db.refresh(project)
        return project

    def delete_project(self, project_id: UUID) -> None:
        project = self.get_project(project_id)
        try:
            self.db.delete(project)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _normalize_project_name(self, name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=PROJECT_NAME_EMPTY_MESSAGE,
            )
        return normalized_name

    def _ensure_name_available(
        self, name: str, exclude_project_id: UUID | None = None
    ) -> None:
        statement = select(Project.id).where(Project.name == name)
        if exclude_project_id is not None:
            statement = statement.where(Project.id != exclude_project_id)
        existing_project_id = self.db.scalar(statement)
        if existing_project_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=PROJECT_NAME_EXISTS_MESSAGE,
            )

    def _commit_project_change(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=PROJECT_NAME_EXISTS_MESSAGE,
            ) from exc
