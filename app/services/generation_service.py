import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.core.tech_stack import tech_stack_items_to_payload, tech_stack_items_to_text
from app.generators.blueprint_generator import (
    BlueprintValidationError,
    build_project_blueprint_content,
)
from app.llm.client import (
    CONFIGURATION_ERROR_DETAIL,
    EMPTY_RESPONSE_DETAIL,
    REQUEST_ERROR_DETAIL,
    RESPONSE_FORMAT_ERROR_DETAIL,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMRequestError,
    LLMResponseFormatError,
)
from app.models.blueprint import ProjectBlueprint
from app.models.generation_run import GenerationRun
from app.services.blueprint_service import BlueprintService
from app.services.business_requirement_story_service import BusinessRequirementStoryService
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)
RUN_TYPE = "generate_blueprint"
NO_REQUIREMENT_MESSAGE = "请先在“用户需求”模块提交至少一条用户需求。"
EMPTY_REQUIREMENT_MESSAGE = "用户需求内容为空，无法生成项目蓝图。"


class GenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_project_blueprint(self, project_id: UUID) -> ProjectBlueprint:
        project = ProjectService(self.db).get_project(project_id)
        requirement = RequirementService(self.db).get_latest_requirement(project_id)
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=NO_REQUIREMENT_MESSAGE,
            )
        if not requirement.raw_text or not requirement.raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EMPTY_REQUIREMENT_MESSAGE,
            )

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
        frontend_stack = (
            tech_stack_items_to_text(getattr(project, "target_frontend_stack_items", []))
            or project.target_frontend_stack
            or DEFAULT_FRONTEND_STACK
        )
        backend_stack = (
            tech_stack_items_to_text(getattr(project, "target_backend_stack_items", []))
            or project.target_backend_stack
            or DEFAULT_BACKEND_STACK
        )
        run = GenerationRun(
            project_id=project_id,
            run_type=RUN_TYPE,
            status="running",
            input_snapshot={
                "project_id": str(project_id),
                "requirement_id": str(requirement.id),
                "source": "requirement + business_stories",
                "business_requirement_story_ids": [
                    story["id"] for story in business_story_context
                ],
                "target_frontend_stack": frontend_stack,
                "target_backend_stack": backend_stack,
                "target_frontend_stack_items": tech_stack_items_to_payload(
                    getattr(project, "target_frontend_stack_items", [])
                ),
                "target_backend_stack_items": tech_stack_items_to_payload(
                    getattr(project, "target_backend_stack_items", [])
                ),
            },
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "blueprint.generate.start project_id=%s requirement_id=%s run_id=%s",
            project_id,
            requirement.id,
            run.id,
        )
        try:
            content = build_project_blueprint_content(project, requirement, business_story_context)
            blueprint = ProjectBlueprint(
                project_id=project_id,
                version=BlueprintService(self.db).get_next_version(project_id),
                title="项目蓝图",
                summary="基于用户需求生成的第一版项目蓝图草案。",
                content=content,
            )
            self.db.add(blueprint)
            self.db.flush()

            run.status = "completed"
            run.output_snapshot = {
                "blueprint_id": str(blueprint.id),
                "version": blueprint.version,
                "summary": blueprint.summary,
                "counts": _count_blueprint_content(content),
            }
            run.completed_at = datetime.now(UTC)
            self.db.add(run)
            self.db.commit()
            self.db.refresh(blueprint)
            logger.info(
                "blueprint.generate.success project_id=%s blueprint_id=%s",
                project_id,
                blueprint.id,
            )
            return blueprint
        except LLMConfigurationError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "blueprint.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=CONFIGURATION_ERROR_DETAIL,
            ) from exc
        except LLMRequestError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "blueprint.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=REQUEST_ERROR_DETAIL,
            ) from exc
        except LLMEmptyResponseError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "blueprint.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EMPTY_RESPONSE_DETAIL,
            ) from exc
        except (LLMResponseFormatError, BlueprintValidationError, ValueError) as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "blueprint.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=RESPONSE_FORMAT_ERROR_DETAIL,
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to generate blueprint for project %s", project_id)
            self._mark_run_failed(run, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成蓝图草案失败，请检查项目数据或稍后重试。",
            ) from exc

    def _mark_run_failed(self, run: GenerationRun, exc: Exception) -> None:
        self.db.rollback()
        run.status = "failed"
        run.error_message = _excerpt(str(exc), 1000)
        run.output_snapshot = None
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()


def _count_blueprint_content(content: dict[str, Any]) -> dict[str, int]:
    return {
        "product_goals": len(content.get("product_goals", [])),
        "user_roles": len(content.get("user_roles", [])),
        "core_modules": len(content.get("core_modules", [])),
        "domain_entities": len(content.get("domain_entities", [])),
        "pages": len(content.get("pages", [])),
        "api_needs": len(content.get("api_needs", [])),
        "business_requirement_stories": len(content.get("business_requirement_stories", [])),
    }


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
