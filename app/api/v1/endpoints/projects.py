from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectDescriptionOptionsRead,
    ProjectDescriptionOptionsRequest,
    ProjectRead,
    ProjectUpdate,
)
from app.schemas.project_config import ProjectConfigRead, ProjectConfigUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects")
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(db: DbSession, current_user: CurrentUser, payload: ProjectCreate) -> ProjectRead:
    return ProjectService(db, current_user).create_project(payload)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: DbSession, current_user: CurrentUser, q: str | None = None
) -> list[ProjectRead]:
    return ProjectService(db, current_user).list_projects(q=q)


@router.post("/description-options", response_model=ProjectDescriptionOptionsRead)
def generate_project_description_options(
    db: DbSession,
    current_user: CurrentUser,
    payload: ProjectDescriptionOptionsRequest,
) -> ProjectDescriptionOptionsRead:
    return ProjectService(db, current_user).generate_description_options(payload)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(db: DbSession, current_user: CurrentUser, project_id: UUID) -> ProjectRead:
    return ProjectService(db, current_user).get_project(project_id)


@router.get("/{project_id}/config", response_model=ProjectConfigRead)
def get_project_config(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> ProjectConfigRead:
    return ProjectService(db, current_user).get_project_config(project_id)


@router.get("/{project_id}/configuration", response_model=ProjectConfigRead)
def get_project_configuration(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> ProjectConfigRead:
    return ProjectService(db, current_user).get_project_config(project_id)


@router.patch("/{project_id}/config", response_model=ProjectConfigRead)
def update_project_config(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    payload: ProjectConfigUpdate,
) -> ProjectConfigRead:
    return ProjectService(db, current_user).update_project_config(project_id, payload)


@router.patch("/{project_id}/configuration", response_model=ProjectConfigRead)
def update_project_configuration(
    db: DbSession,
    current_user: CurrentUser,
    project_id: UUID,
    payload: ProjectConfigUpdate,
) -> ProjectConfigRead:
    return ProjectService(db, current_user).update_project_config(project_id, payload)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    db: DbSession, current_user: CurrentUser, project_id: UUID, payload: ProjectUpdate
) -> ProjectRead:
    return ProjectService(db, current_user).update_project(project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(db: DbSession, current_user: CurrentUser, project_id: UUID) -> Response:
    ProjectService(db, current_user).delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
