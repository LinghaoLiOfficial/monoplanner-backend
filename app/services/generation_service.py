import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.generators.blueprint_generator import build_mock_blueprint_content
from app.models.blueprint import ProjectBlueprint
from app.models.generation_run import GenerationRun
from app.services.blueprint_service import BlueprintService
from app.services.business_requirement_story_service import BusinessRequirementStoryService
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_project_blueprint(self, project_id: UUID) -> ProjectBlueprint:
        project = ProjectService(self.db).get_project(project_id)
        requirement = RequirementService(self.db).get_latest_requirement(project_id)
        if requirement is None:
            self._record_failed_run(
                project_id,
                "Project has no requirements to generate a blueprint from.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no requirements to generate a blueprint from.",
            )

        try:
            content = build_mock_blueprint_content(project, requirement)
            business_stories = BusinessRequirementStoryService(
                self.db
            ).list_for_blueprint_context(project_id)
            business_story_context = [
                {
                    "id": str(story.id),
                    "title": story.title,
                    "priority": story.priority,
                    "status": story.status,
                    "user_story": story.user_story,
                }
                for story in business_stories
            ]
            if business_story_context:
                content["business_requirement_stories"] = business_story_context
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
                    "business_requirement_story_ids": [
                        story["id"] for story in business_story_context
                    ],
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
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to generate blueprint for project %s", project_id)
            self._record_failed_run(
                project_id,
                str(exc),
                requirement_id=requirement.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成蓝图草案失败，请检查项目数据或稍后重试。",
            ) from exc

    def _record_failed_run(
        self, project_id: UUID, error_message: str, requirement_id: UUID | None = None
    ) -> None:
        self.db.rollback()
        input_snapshot = {"project_id": str(project_id)}
        if requirement_id is not None:
            input_snapshot["requirement_id"] = str(requirement_id)
        self.db.add(
            GenerationRun(
                project_id=project_id,
                run_type="blueprint",
                status="failed",
                input_snapshot=input_snapshot,
                output_snapshot=None,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )
        self.db.commit()
