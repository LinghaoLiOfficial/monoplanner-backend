from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
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
from app.llm.json_client import generate_json
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement
from app.prompts.business_story_decomposer import (
    build_business_story_decomposition_payload,
    build_business_story_decomposition_prompt,
)
from app.prompts.templates.business_story_decomposer.output_schema import (
    BusinessStoryDecompositionOutput,
)
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.business_requirement_story_service import BusinessRequirementStoryService
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)

VALID_PRIORITIES = {"p1_must", "p2_should", "p3_could", "p4_wont"}
VALID_IMPLEMENTATION_SCOPES = {"frontend_only", "backend_only", "fullstack", "non_code"}
VALID_STORY_AFFECTED_LAYERS = {
    "ux_design",
    "ui_design",
    "frontend_pages",
    "api_contract",
    "backend_services",
    "database_models",
    "documentation",
}
LEGACY_LAYER_ALIASES = {
    "frontend_tools": "frontend_pages",
    "backend_tools": "backend_services",
    "backend_implementation": "backend_services",
    "database": "database_models",
    "db_model": "database_models",
    "db_models": "database_models",
}
RUN_TYPE = "generate_business_requirement_stories"
NO_REQUIREMENT_MESSAGE = "请先在“用户需求”模块提交至少一条用户需求。"
EMPTY_REQUIREMENT_MESSAGE = "用户需求内容为空，无法生成业务需求故事。"
REQUIREMENT_NOT_FOUND_MESSAGE = "用户需求不存在或不属于当前项目。"
REQUIREMENT_ALREADY_APPLIED_MESSAGE = "该原始用户需求已应用，不能重复更新业务需求故事池。"
JSON_OBJECT_RESPONSE_FORMAT = {"response_format": {"type": "json_object"}}
BUSINESS_STORY_RUNNING_MESSAGE = "正在更新业务需求故事..."
BUSINESS_STORY_SUCCEEDED_MESSAGE = "业务需求故事已更新。"
BUSINESS_STORY_FAILED_MESSAGE = "业务需求故事更新失败"
NO_VALID_BUSINESS_STORIES_MESSAGE = "未生成有效业务需求故事。"
JsonGenerator = Callable[..., dict[str, Any]]


class BusinessStoryGenerationService:
    def __init__(
        self,
        db: Session,
        json_generator: JsonGenerator | None = None,
    ) -> None:
        self.db = db
        self.json_generator = json_generator or generate_json

    def generate_business_stories(
        self, project_id: UUID, payload: GenerateBusinessRequirementStoriesRequest
    ) -> list[BusinessRequirementStory]:
        project = ProjectService(self.db).get_project(project_id)
        requirement = self._resolve_requirement(project_id, payload.requirement_id)
        if not requirement.raw_text or not requirement.raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EMPTY_REQUIREMENT_MESSAGE,
            )
        if requirement.status == "applied":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=REQUIREMENT_ALREADY_APPLIED_MESSAGE,
            )

        current_business_stories = _current_story_snapshots(self.db, project_id)
        input_snapshot = _build_input_snapshot(
            project,
            requirement,
            payload.overwrite,
            current_business_stories=current_business_stories,
        )
        run = GenerationRun(
            project_id=project_id,
            requirement_id=requirement.id,
            run_type=RUN_TYPE,
            status="running",
            progress=0,
            message=BUSINESS_STORY_RUNNING_MESSAGE,
            input_snapshot=input_snapshot,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        logger.info(
            "business_stories.generate.start project_id=%s requirement_id=%s run_id=%s",
            project_id,
            requirement.id,
            run.id,
        )
        try:
            user_payload = build_business_story_decomposition_payload(
                project,
                requirement,
                current_business_stories,
            )
            prompt = build_business_story_decomposition_prompt(
                project,
                requirement,
                current_business_stories,
            )
            parsed = _generate_business_story_json(self.json_generator, prompt, user_payload)
            run.progress = 60
            run.message = "正在解析业务需求故事..."
            self.db.add(run)
            self.db.commit()
            story_payloads = _validate_story_payloads(parsed)

            BusinessRequirementStoryService(self.db).mark_current_pool_inactive(project_id)

            stories = [
                BusinessRequirementStory(
                    project_id=project_id,
                    requirement_id=requirement.id,
                    generation_run_id=run.id,
                    title=story_payload["title"],
                    priority=story_payload["priority"],
                    status="draft",
                    implementation_scope=story_payload["implementation_scope"],
                    affected_layers=story_payload["affected_layers"],
                    user_story=story_payload["user_story"],
                    business_scope=story_payload["business_scope"],
                    data_rules=story_payload["data_rules"],
                    acceptance_criteria=story_payload["acceptance_criteria"],
                    vertical_slice_note=story_payload.get("vertical_slice_note"),
                    depends_on=story_payload["depends_on"],
                    source_requirement_ids=story_payload["source_requirement_ids"],
                    execution_notes=story_payload.get("execution_notes"),
                    source_requirement_excerpt=requirement.raw_text[:500],
                    sort_order=index,
                    is_current=True,
                )
                for index, story_payload in enumerate(story_payloads, start=1)
            ]
            for story in stories:
                self.db.add(story)
            requirement.status = "applied"
            requirement.applied_at = datetime.now(UTC)
            self.db.add(requirement)
            run.status = "succeeded"
            run.progress = 100
            run.message = BUSINESS_STORY_SUCCEEDED_MESSAGE
            run.output_snapshot = {
                "story_count": len(stories),
                "priority_counts": _count_priority_payloads(story_payloads),
            }
            run.completed_at = datetime.now(UTC)
            self.db.add(run)
            self.db.commit()
            for story in stories:
                self.db.refresh(story)
            logger.info(
                "business_stories.generate.success project_id=%s requirement_id=%s count=%s",
                project_id,
                requirement.id,
                len(stories),
            )
            return stories
        except LLMConfigurationError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "business_stories.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=CONFIGURATION_ERROR_DETAIL,
            ) from exc
        except LLMRequestError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "business_stories.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=REQUEST_ERROR_DETAIL,
            ) from exc
        except LLMEmptyResponseError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "business_stories.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EMPTY_RESPONSE_DETAIL,
            ) from exc
        except (LLMResponseFormatError, ValueError) as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "business_stories.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=RESPONSE_FORMAT_ERROR_DETAIL,
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to generate business stories for project %s", project_id)
            self._mark_run_failed(run, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成业务需求故事失败，请检查项目数据或稍后重试。",
            ) from exc

    def _resolve_requirement(
        self, project_id: UUID, requirement_id: UUID | None
    ) -> Requirement:
        if requirement_id is None:
            requirement = RequirementService(self.db).get_latest_requirement(project_id)
            if requirement is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=NO_REQUIREMENT_MESSAGE,
                )
            return requirement

        requirement = self.db.scalar(
            select(Requirement).where(
                Requirement.id == requirement_id,
                Requirement.project_id == project_id,
            )
        )
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=REQUIREMENT_NOT_FOUND_MESSAGE,
            )
        return requirement

    def _mark_run_failed(self, run: GenerationRun, exc: Exception) -> None:
        self.db.rollback()
        run.status = "failed"
        run.message = BUSINESS_STORY_FAILED_MESSAGE
        run.error_message = _excerpt(str(exc), 1000)
        run.completed_at = datetime.now(UTC)
        run.output_snapshot = None
        self.db.add(run)
        self.db.commit()


def _generate_business_story_json(
    json_generator: JsonGenerator,
    prompt: Any,
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        if settings.llm_use_response_format:
            return json_generator(
                prompt.system,
                prompt.user,
                extra_params=JSON_OBJECT_RESPONSE_FORMAT,
                response_model=BusinessStoryDecompositionOutput,
            )
        return json_generator(
            prompt.system,
            prompt.user,
            response_model=BusinessStoryDecompositionOutput,
        )
    except TypeError:
        return json_generator(prompt.system, prompt.user)


def _validate_story_payloads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    stories = parsed.get("stories")
    if not isinstance(stories, list):
        raise ValueError("LLM output must contain a stories list.")
    if not stories:
        raise ValueError(NO_VALID_BUSINESS_STORIES_MESSAGE)

    validated: list[dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, dict):
            raise ValueError("Each story must be an object.")
        validated.append(_normalize_story(story))
    return validated


def _normalize_story(story: dict[str, Any]) -> dict[str, Any]:
    required_fields = (
        "title",
        "priority",
        "user_story",
        "business_scope",
        "data_rules",
        "acceptance_criteria",
    )
    for field in required_fields:
        if field not in story:
            raise ValueError(f"Story is missing required field: {field}.")

    vertical_slice_note = story.get("vertical_slice_note")
    if vertical_slice_note is not None and not isinstance(vertical_slice_note, str):
        vertical_slice_note = str(vertical_slice_note)

    return {
        "title": _require_non_empty_string(story["title"], "title"),
        "priority": _normalize_priority(story["priority"]),
        "implementation_scope": _normalize_implementation_scope(
            story.get("implementation_scope")
        ),
        "affected_layers": _normalize_affected_layers(story.get("affected_layers", [])),
        "user_story": _require_non_empty_string(story["user_story"], "user_story"),
        "business_scope": _normalize_business_scope(story["business_scope"]),
        "data_rules": _normalize_data_rules(story["data_rules"]),
        "acceptance_criteria": _normalize_acceptance_criteria(story["acceptance_criteria"]),
        "vertical_slice_note": vertical_slice_note,
        "depends_on": story.get("depends_on") if isinstance(story.get("depends_on"), list) else [],
        "source_requirement_ids": _normalize_story_string_list(
            story.get("source_requirement_ids", [])
        ),
        "execution_notes": story.get("execution_notes")
        if isinstance(story.get("execution_notes"), str)
        else None,
    }


def _normalize_priority(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Story priority is invalid.")
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = normalized.replace("'", "")
    aliases = {
        "p1": "p1_must",
        "p1_must": "p1_must",
        "must": "p1_must",
        "必须": "p1_must",
        "必须完成": "p1_must",
        "p2": "p2_should",
        "p2_should": "p2_should",
        "should": "p2_should",
        "应该": "p2_should",
        "应该完成": "p2_should",
        "p3": "p3_could",
        "p3_could": "p3_could",
        "could": "p3_could",
        "可以": "p3_could",
        "可以完成": "p3_could",
        "p4": "p4_wont",
        "p4_wont": "p4_wont",
        "p4_won_t": "p4_wont",
        "wont": "p4_wont",
        "won_t": "p4_wont",
        "本阶段不做": "p4_wont",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in VALID_PRIORITIES:
        return normalized
    match = re.search(r"\bp([1-4])\b", normalized)
    if match:
        return {
            "1": "p1_must",
            "2": "p2_should",
            "3": "p3_could",
            "4": "p4_wont",
        }[match.group(1)]
    for marker, priority in (
        ("must", "p1_must"),
        ("必须", "p1_must"),
        ("should", "p2_should"),
        ("应该", "p2_should"),
        ("could", "p3_could"),
        ("可以", "p3_could"),
        ("won", "p4_wont"),
        ("不做", "p4_wont"),
    ):
        if marker in normalized:
            return priority
    raise ValueError("Story priority is invalid.")


def _normalize_implementation_scope(value: Any) -> str:
    if not isinstance(value, str):
        return "fullstack"
    normalized = value.strip()
    return normalized if normalized in VALID_IMPLEMENTATION_SCOPES else "fullstack"


def _normalize_story_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return normalized


def _normalize_affected_layers(value: Any) -> list[str]:
    layers: list[str] = []
    for item in _normalize_story_string_list(value):
        normalized = LEGACY_LAYER_ALIASES.get(item, item)
        if normalized in VALID_STORY_AFFECTED_LAYERS and normalized not in layers:
            layers.append(normalized)
    return layers


def _normalize_business_scope(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise ValueError("Story business_scope must be an object.")
    return {
        "included": _normalize_string_list(value.get("included", []), "business_scope.included"),
        "excluded": _normalize_string_list(value.get("excluded", []), "business_scope.excluded"),
    }


def _normalize_data_rules(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("Story data_rules must be a list.")
    normalized_rules = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Story data_rules items must be objects.")
        field = item.get("field")
        rule = item.get("rule")
        if not isinstance(field, str) or not field.strip():
            raise ValueError("Story data_rules item field is invalid.")
        if not isinstance(rule, str) or not rule.strip():
            raise ValueError("Story data_rules item rule is invalid.")
        normalized_rules.append({"field": field.strip(), "rule": rule.strip()})
    return normalized_rules


def _normalize_acceptance_criteria(value: Any) -> list[str]:
    criteria = _normalize_string_list(value, "acceptance_criteria")
    if not criteria:
        raise ValueError("Story acceptance_criteria must not be empty.")
    return criteria


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Story {field_name} must be a list.")
    normalized = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"Story {field_name} items must be strings.")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Story {field_name} is invalid.")
    return value.strip()


def _build_input_snapshot(
    project: Any,
    requirement: Requirement,
    overwrite: bool,
    *,
    current_business_stories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
        },
        "requirement": {
            "id": str(requirement.id),
            "raw_text_excerpt": requirement.raw_text[:500],
            "language": requirement.language,
            "source_type": requirement.source_type,
        },
        "overwrite": overwrite,
        "current_business_story_count": len(current_business_stories or []),
        "source": "project_config + new_raw_requirement + current_business_stories",
    }


def _current_story_snapshots(db: Session, project_id: UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(story.id),
            "title": story.title,
            "priority": story.priority,
            "status": story.status,
            "implementation_scope": story.implementation_scope,
            "affected_layers": story.affected_layers,
            "user_story": story.user_story,
            "business_scope": story.business_scope,
            "data_rules": story.data_rules,
            "acceptance_criteria": story.acceptance_criteria,
            "depends_on": story.depends_on,
            "execution_notes": story.execution_notes,
        }
        for story in db.scalars(
            select(BusinessRequirementStory)
            .where(
                BusinessRequirementStory.project_id == project_id,
                BusinessRequirementStory.is_current.is_(True),
            )
            .order_by(
                BusinessRequirementStory.sort_order.asc(),
                BusinessRequirementStory.created_at.asc(),
            )
        )
    ]


def _count_priority_payloads(story_payloads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {priority: 0 for priority in sorted(VALID_PRIORITIES)}
    for story in story_payloads:
        priority = story["priority"]
        counts[priority] = counts.get(priority, 0) + 1
    return counts


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
