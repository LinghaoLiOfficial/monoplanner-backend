from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_active_user, get_db
from app.models.user import User
from app.schemas.blueprint import ProjectBlueprintRead
from app.services.blueprint_service import BlueprintService

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_active_user)]


@router.get("/projects/{project_id}/blueprints", response_model=list[ProjectBlueprintRead])
def list_project_blueprints(
    db: DbSession, current_user: CurrentUser, project_id: UUID
) -> list[ProjectBlueprintRead]:
    return BlueprintService(db, current_user).list_project_blueprints(project_id)


@router.get("/blueprints/{blueprint_id}", response_model=ProjectBlueprintRead)
def get_blueprint(
    db: DbSession, current_user: CurrentUser, blueprint_id: UUID
) -> ProjectBlueprintRead:
    return BlueprintService(db, current_user).get_blueprint(blueprint_id)
