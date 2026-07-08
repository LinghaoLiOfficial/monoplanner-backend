from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.generators.blueprint_generator import build_mock_blueprint_content
from app.models.blueprint import ProjectBlueprint
from app.models.generation_run import GenerationRun
from app.services.blueprint_service import BlueprintService
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService


class GenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_project_blueprint(self, project_id: UUID) -> ProjectBlueprint:
        project = ProjectService(self.db).get_project(project_id)
        requirement = RequirementService(self.db).get_latest_requirement(project_id)
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no requirements to generate a blueprint from.",
            )

        content = build_mock_blueprint_content(project, requirement)
        blueprint = ProjectBlueprint(
            project_id=project_id,
            version=BlueprintService(self.db).get_next_version(project_id),
            title="项目蓝图草案",
            summary="基于用户需求生成的第一版项目蓝图草案。",
            content=content,
        )
        self.db.add(blueprint)
        self.db.flush()

        run = GenerationRun(
            project_id=project_id,
            run_type="blueprint",
            status="completed",
            input_snapshot={
                "project_id": str(project_id),
                "requirement_id": str(requirement.id),
                "raw_text": requirement.raw_text,
            },
            output_snapshot={
                "blueprint_id": str(blueprint.id),
                "version": blueprint.version,
                "content": content,
            },
            completed_at=datetime.now(UTC),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(blueprint)
        return blueprint
