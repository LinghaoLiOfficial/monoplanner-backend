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
from app.llm.json_client import LLMJsonGenerationError, generate_json
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement
from app.prompts.business_story_decomposer import (
    SYSTEM_PROMPT,
    build_business_story_decomposition_payload,
)
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.business_requirement_story_service import BusinessRequirementStoryService
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)

VALID_PRIORITIES = {"p1_must", "p2_should", "p3_could", "p4_wont"}
RUN_TYPE = "generate_business_requirement_stories"
NO_REQUIREMENT_MESSAGE = "请先在“用户需求”模块提交至少一条用户需求。"
EMPTY_REQUIREMENT_MESSAGE = "用户需求内容为空，无法生成业务需求故事。"
REQUIREMENT_NOT_FOUND_MESSAGE = "用户需求不存在或不属于当前项目。"
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

        input_snapshot = _build_input_snapshot(project, requirement, payload.overwrite)
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
            user_payload = build_business_story_decomposition_payload(project, requirement)
            parsed = _generate_business_story_json(self.json_generator, user_payload)
            run.progress = 60
            run.message = "正在解析业务需求故事..."
            self.db.add(run)
            self.db.commit()
            story_payloads = _validate_story_payloads(parsed)

            if payload.overwrite:
                BusinessRequirementStoryService(self.db).delete_existing_for_requirement(
                    project_id, requirement.id
                )

            stories = [
                BusinessRequirementStory(
                    project_id=project_id,
                    requirement_id=requirement.id,
                    generation_run_id=run.id,
                    title=story_payload["title"],
                    priority=story_payload["priority"],
                    status="draft",
                    user_story=story_payload["user_story"],
                    business_scope=story_payload["business_scope"],
                    data_rules=story_payload["data_rules"],
                    acceptance_criteria=story_payload["acceptance_criteria"],
                    vertical_slice_note=story_payload.get("vertical_slice_note"),
                    source_requirement_excerpt=requirement.raw_text[:500],
                    sort_order=index,
                )
                for index, story_payload in enumerate(story_payloads, start=1)
            ]
            for story in stories:
                self.db.add(story)
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
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        if settings.llm_use_response_format:
            return json_generator(
                SYSTEM_PROMPT,
                user_payload,
                extra_params=JSON_OBJECT_RESPONSE_FORMAT,
            )
        return json_generator(SYSTEM_PROMPT, user_payload)
    except TypeError:
        return json_generator(SYSTEM_PROMPT, user_payload)
    except LLMJsonGenerationError as exc:
        if "not valid JSON" not in str(exc) and "does not contain a JSON object" not in str(exc):
            raise
        repair_payload = {
            "invalid_output_error": str(exc),
            "project_name": user_payload["project_name"],
            "project_description": user_payload["project_description"],
            "raw_requirement": user_payload["raw_requirement"],
            "target_output_schema": user_payload["target_output_schema"],
            "priority_definitions": user_payload["priority_definitions"],
            "decomposition_rules": user_payload["decomposition_rules"],
            "repair_rules": [
                "只输出一个 JSON object",
                "顶层必须包含 stories 数组",
                "不要添加 JSON 之外的说明文字",
                "根据 raw_requirement 重新生成业务需求故事，不要只复制示例",
                "保留原始业务含义，并按目标 schema 补全所有必填字段",
            ],
        }
        repair_prompt = (
            "你是 JSON 格式修复器和资深产品经理。上一次业务需求故事生成结果不是合法 JSON。"
            "请只返回一个严格合法的 JSON object，不要返回 Markdown、解释、注释或 "
            "JSON 之外的任何字符。必须使用双引号，禁止尾随逗号，字符串内部换行必须转义为 \\n。"
        )
        if settings.llm_use_response_format:
            return generate_json(
                repair_prompt,
                repair_payload,
                extra_params=JSON_OBJECT_RESPONSE_FORMAT,
            )
        return generate_json(repair_prompt, repair_payload)


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
        "user_story": _require_non_empty_string(story["user_story"], "user_story"),
        "business_scope": _normalize_business_scope(story["business_scope"]),
        "data_rules": _normalize_data_rules(story["data_rules"]),
        "acceptance_criteria": _normalize_acceptance_criteria(story["acceptance_criteria"]),
        "vertical_slice_note": vertical_slice_note,
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
    project: Any, requirement: Requirement, overwrite: bool
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
    }


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
