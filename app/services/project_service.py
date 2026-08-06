from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.project_config import ProjectConfigUpdate

PROJECT_NAME_EMPTY_MESSAGE = "项目名称不能为空。"
PROJECT_NAME_EXISTS_MESSAGE = "项目名称已存在，请使用其他名称。"


class ProjectService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def create_project(self, payload: ProjectCreate) -> Project:
        user = self._require_user()
        name = self._normalize_project_name(payload.name)
        self._ensure_name_available(name, owner_user_id=user.id)
        project = Project(
            owner_user_id=user.id,
            name=name,
            description=payload.description,
            target_frontend_stack=DEFAULT_FRONTEND_STACK,
            target_backend_stack=DEFAULT_BACKEND_STACK,
            target_stacks_configured=False,
        )
        self.db.add(project)
        self._commit_project_change()
        self.db.refresh(project)
        return project

    def list_projects(self, q: str | None = None) -> list[Project]:
        user = self._require_user()
        statement = select(Project)
        if user.role != "admin":
            statement = statement.where(Project.owner_user_id == user.id)
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
        self.ensure_project_access(project)
        return project

    def ensure_project_access(self, project: Project) -> None:
        if self.current_user is None:
            return
        user = self.current_user
        if user.role == "admin" or project.owner_user_id == user.id:
            return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    def update_project(self, project_id: UUID, payload: ProjectUpdate) -> Project:
        project = self.get_project(project_id)
        updates = payload.model_dump(exclude_unset=True)
        self._apply_project_updates(project, updates)
        self.db.add(project)
        self._commit_project_change()
        self.db.refresh(project)
        return project

    def get_project_config(self, project_id: UUID) -> Project:
        return self.get_project(project_id)

    def get_project_configuration(self, project_id: UUID) -> Project:
        return self.get_project(project_id)

    def update_project_config(self, project_id: UUID, payload: ProjectConfigUpdate) -> Project:
        project = self.get_project(project_id)
        updates = payload.model_dump(exclude_unset=True)
        self._apply_project_updates(project, updates)
        self.db.add(project)
        self._commit_project_change()
        self.db.refresh(project)
        return project

    def update_project_configuration(
        self, project_id: UUID, payload: ProjectConfigUpdate
    ) -> Project:
        return self.update_project_config(project_id, payload)

    def _apply_project_updates(self, project: Project, updates: dict[str, Any]) -> None:
        if "name" in updates:
            if updates["name"] is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=PROJECT_NAME_EMPTY_MESSAGE,
                )
            updates["name"] = self._normalize_project_name(updates["name"])
            self._ensure_name_available(
                updates["name"],
                owner_user_id=project.owner_user_id,
                exclude_project_id=project.id,
            )
        if "target_frontend_stack" in updates:
            updates["target_frontend_stack"] = normalize_stack(
                updates["target_frontend_stack"],
                DEFAULT_FRONTEND_STACK,
            )
        if "target_backend_stack" in updates:
            updates["target_backend_stack"] = normalize_stack(
                updates["target_backend_stack"],
                DEFAULT_BACKEND_STACK,
            )
        if "target_frontend_stack" in updates or "target_backend_stack" in updates:
            updates["target_frontend_stack"] = normalize_stack(
                updates.get("target_frontend_stack", project.target_frontend_stack),
                DEFAULT_FRONTEND_STACK,
            )
            updates["target_backend_stack"] = normalize_stack(
                updates.get("target_backend_stack", project.target_backend_stack),
                DEFAULT_BACKEND_STACK,
            )
            updates["target_stacks_configured"] = True
        for field, value in updates.items():
            setattr(project, field, value)

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
        self,
        name: str,
        *,
        owner_user_id: UUID,
        exclude_project_id: UUID | None = None,
    ) -> None:
        statement = select(Project.id).where(
            Project.owner_user_id == owner_user_id,
            Project.name == name,
        )
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

    def _require_user(self) -> User:
        if self.current_user is None:
            raise RuntimeError("ProjectService requires current_user for protected operations.")
        return self.current_user
