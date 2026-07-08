from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects")
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(db: DbSession, payload: ProjectCreate) -> ProjectRead:
    return ProjectService(db).create_project(payload)


@router.get("", response_model=list[ProjectRead])
def list_projects(db: DbSession) -> list[ProjectRead]:
    return ProjectService(db).list_projects()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(db: DbSession, project_id: UUID) -> ProjectRead:
    return ProjectService(db).get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(db: DbSession, project_id: UUID, payload: ProjectUpdate) -> ProjectRead:
    return ProjectService(db).update_project(project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(db: DbSession, project_id: UUID) -> Response:
    ProjectService(db).delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
