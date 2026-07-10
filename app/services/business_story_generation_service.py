from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import (
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseError,
    OpenAICompatibleLLMClient,
)
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
INVALID_LLM_OUTPUT_MESSAGE = "LLM 返回的业务需求故事格式不正确，请重试。"


class BusinessStoryGenerationService:
    def __init__(self, db: Session, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.db = db
        self.llm_client = llm_client or OpenAICompatibleLLMClient()

    def generate_business_stories(
        self, project_id: UUID, payload: GenerateBusinessRequirementStoriesRequest
    ) -> list[BusinessRequirementStory]:
        project = ProjectService(self.db).get_project(project_id)
        requirement = self._resolve_requirement(project_id, payload.requirement_id)
        input_snapshot = {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
            },
            "requirement": {
                "id": str(requirement.id),
                "raw_text": requirement.raw_text,
                "language": requirement.language,
                "source_type": requirement.source_type,
            },
            "overwrite": payload.overwrite,
        }

        try:
            user_payload = build_business_story_decomposition_payload(project, requirement)
            raw_output = self.llm_client.invoke(SYSTEM_PROMPT, user_payload)
            parsed = _parse_json_object(raw_output)
            story_payloads = _validate_story_payloads(parsed)

            if payload.overwrite:
                BusinessRequirementStoryService(self.db).delete_existing_for_requirement(
                    project_id, requirement.id
                )

            stories = [
                BusinessRequirementStory(
                    project_id=project_id,
                    requirement_id=requirement.id,
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
            self.db.flush()

            run = GenerationRun(
                project_id=project_id,
                run_type=RUN_TYPE,
                status="completed",
                input_snapshot=input_snapshot,
                output_snapshot={
                    "story_count": len(stories),
                    "priority_counts": _count_priorities(stories),
                    "story_ids": [str(story.id) for story in stories],
                },
                completed_at=datetime.now(UTC),
            )
            self.db.add(run)
            self.db.flush()
            for story in stories:
                story.generation_run_id = run.id
            self.db.commit()
            for story in stories:
                self.db.refresh(story)
            return stories
        except LLMConfigurationError as exc:
            self._record_failed_run(project_id, input_snapshot, str(exc))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM 服务未配置，请检查 LLM_API_KEY 和 LLM_MODEL。",
            ) from exc
        except (LLMRequestError, LLMResponseError) as exc:
            self._record_failed_run(project_id, input_snapshot, str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM 请求失败，请稍后重试。",
            ) from exc
        except ValueError as exc:
            self._record_failed_run(project_id, input_snapshot, str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=INVALID_LLM_OUTPUT_MESSAGE,
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to generate business stories for project %s", project_id)
            self._record_failed_run(project_id, input_snapshot, str(exc))
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
                    detail="Project has no requirements to generate business stories from.",
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
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found.",
            )
        return requirement

    def _record_failed_run(
        self, project_id: UUID, input_snapshot: dict[str, Any], error_message: str
    ) -> None:
        self.db.rollback()
        self.db.add(
            GenerationRun(
                project_id=project_id,
                run_type=RUN_TYPE,
                status="failed",
                input_snapshot=input_snapshot,
                output_snapshot=None,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )
        self.db.commit()


def _parse_json_object(raw_output: str) -> dict[str, Any]:
    content = raw_output.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3:
            content = "\n".join(lines[1:-1]).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM output does not contain a JSON object.")
    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("LLM output is not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM output JSON must be an object.")
    return parsed


def _validate_story_payloads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    stories = parsed.get("stories")
    if not isinstance(stories, list):
        raise ValueError("LLM output must contain a stories list.")

    validated: list[dict[str, Any]] = []
    for story in stories:
        if not isinstance(story, dict):
            raise ValueError("Each story must be an object.")
        for field in (
            "title",
            "priority",
            "user_story",
            "business_scope",
            "data_rules",
            "acceptance_criteria",
        ):
            if field not in story:
                raise ValueError(f"Story is missing required field: {field}.")
        if story["priority"] not in VALID_PRIORITIES:
            raise ValueError("Story priority is invalid.")
        if not isinstance(story["title"], str) or not story["title"].strip():
            raise ValueError("Story title is invalid.")
        if not isinstance(story["user_story"], str) or not story["user_story"].strip():
            raise ValueError("Story user_story is invalid.")
        business_scope = story["business_scope"]
        if not isinstance(business_scope, dict):
            raise ValueError("Story business_scope must be an object.")
        if "included" not in business_scope or "excluded" not in business_scope:
            raise ValueError("Story business_scope must include included and excluded.")
        if not isinstance(story["data_rules"], list):
            raise ValueError("Story data_rules must be a list.")
        if not isinstance(story["acceptance_criteria"], list):
            raise ValueError("Story acceptance_criteria must be a list.")
        if not all(isinstance(item, str) for item in story["acceptance_criteria"]):
            raise ValueError("Story acceptance_criteria items must be strings.")
        validated.append(story)
    return validated


def _count_priorities(stories: list[BusinessRequirementStory]) -> dict[str, int]:
    counts = {priority: 0 for priority in sorted(VALID_PRIORITIES)}
    for story in stories:
        counts[story.priority] = counts.get(story.priority, 0) + 1
    return counts
