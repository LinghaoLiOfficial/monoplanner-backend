from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import OpenAICompatibleLLMClient
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import SYSTEM_PROMPT, build_change_set_payload
from app.services.llm_orchestration_runtime import generate_orchestration_json
from app.services.orchestration_context import (
    latest_assets_snapshot,
    project_config_snapshot,
    story_snapshot,
)
from app.services.orchestration_validators import validate_change_set_payload
from app.services.project_service import ProjectService

RUN_TYPE = "generate_change_set"


class ChangeSetGenerationService:
    def __init__(
        self,
        db: Session,
        llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    ) -> None:
        self.db = db
        self.llm_client_factory = llm_client_factory

    def execute_run(self, run: GenerationRun) -> ChangeSet:
        payload = run.queue_payload or {}
        story_id = payload.get("story_id")
        source_change_set_id = payload.get("source_change_set_id")
        story = self._resolve_story(story_id, source_change_set_id)
        project = ProjectService(self.db).get_project(story.project_id)

        run.status = "running"
        run.progress = max(run.progress, 10)
        run.message = "正在生成变更集..."
        run.started_at = run.started_at or datetime.now(UTC)
        run.input_snapshot = {
            "project_id": str(project.id),
            "story_id": str(story.id),
            "source_change_set_id": str(source_change_set_id) if source_change_set_id else None,
        }
        self.db.add(run)
        self.db.commit()

        parsed = generate_orchestration_json(
            SYSTEM_PROMPT,
            build_change_set_payload(
                project_config=project_config_snapshot(project),
                selected_story=story_snapshot(story) or {},
                current_assets=latest_assets_snapshot(self.db, project.id),
            ),
            llm_client_factory=self.llm_client_factory,
        )
        validated = validate_change_set_payload(parsed)

        change_set = ChangeSet(
            project_id=project.id,
            source_requirement_id=story.requirement_id,
            source_story_id=story.id,
            generation_run_id=run.id,
            version=self._next_version(project.id),
            **validated,
        )
        self.db.add(change_set)
        self.db.flush()
        run.status = "completed"
        run.progress = 100
        run.message = "变更集已生成。"
        run.output_snapshot = {
            "change_set_id": str(change_set.id),
            "version": change_set.version,
            "affected_layers": change_set.affected_layers,
            "summary": change_set.impact_summary or change_set.summary,
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(change_set)
        return change_set

    def _resolve_story(
        self,
        story_id: object,
        source_change_set_id: object,
    ) -> BusinessRequirementStory:
        if story_id:
            story = self.db.get(BusinessRequirementStory, UUID(str(story_id)))
        elif source_change_set_id:
            change_set = self.db.get(ChangeSet, UUID(str(source_change_set_id)))
            story = (
                self.db.get(BusinessRequirementStory, change_set.source_story_id)
                if change_set and change_set.source_story_id
                else None
            )
        else:
            story = None
        if story is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business requirement story not found.",
            )
        return story

    def _next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(ChangeSet)
            .where(ChangeSet.project_id == project_id)
            .order_by(ChangeSet.version.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1
