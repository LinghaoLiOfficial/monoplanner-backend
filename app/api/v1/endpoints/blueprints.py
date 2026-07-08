from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.blueprint import ProjectBlueprintRead
from app.services.blueprint_service import BlueprintService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/blueprints", response_model=list[ProjectBlueprintRead])
def list_project_blueprints(db: DbSession, project_id: UUID) -> list[ProjectBlueprintRead]:
    return BlueprintService(db).list_project_blueprints(project_id)


@router.get("/blueprints/{blueprint_id}", response_model=ProjectBlueprintRead)
def get_blueprint(db: DbSession, blueprint_id: UUID) -> ProjectBlueprintRead:
    return BlueprintService(db).get_blueprint(blueprint_id)
