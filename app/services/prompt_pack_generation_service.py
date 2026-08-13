from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import OpenAICompatibleLLMClient
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.change_set import ChangeSet
from app.models.context_pack import ContextPack
from app.models.generation_run import GenerationRun
from app.prompts.orchestration import build_prompt_pack_prompt
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.services.llm_orchestration_runtime import generate_orchestration_json
from app.services.orchestration_context import (
    change_set_snapshot,
    latest_assets_snapshot,
    project_config_snapshot,
    story_snapshot,
)
from app.services.orchestration_validators import validate_prompt_pack_payload
from app.services.project_service import ProjectService

RUN_TYPE = "generate_prompt_pack"


class PromptPackGenerationService:
    def __init__(
        self,
        db: Session,
        llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    ) -> None:
        self.db = db
        self.llm_client_factory = llm_client_factory

    def execute_run(self, run: GenerationRun) -> list[ContextPack]:
        payload = run.queue_payload or {}
        change_set_id = payload.get("change_set_id")
        if not change_set_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="change_set_id is required.",
            )
        change_set = self.db.get(ChangeSet, UUID(str(change_set_id)))
        if change_set is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Change set not found.",
            )
        run.status = "running"
        run.progress = max(run.progress, 10)
        run.message = "正在生成指令集合..."
        run.started_at = run.started_at or datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        change_sets = self._batch_change_sets(change_set)
        packs = self.generate_for_change_set_batch(
            run,
            change_set,
            change_sets=change_sets,
            old_versions={},
            new_versions=latest_assets_snapshot(self.db, change_set.project_id),
        )
        run.status = "completed"
        run.progress = 100
        run.message = "指令集合已生成。"
        run.output_snapshot = {
            "change_set_id": str(change_set.id),
            "context_pack_ids": [str(pack.id) for pack in packs],
            "roles": [pack.role for pack in packs],
            "counts": {"context_packs": len(packs)},
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        return packs

    def generate_for_change_set(
        self,
        run: GenerationRun,
        change_set: ChangeSet,
        *,
        old_versions: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> list[ContextPack]:
        return self.generate_for_change_set_batch(
            run,
            change_set,
            change_sets=[change_set],
            old_versions=old_versions,
            new_versions=new_versions,
        )

    def generate_for_change_set_batch(
        self,
        run: GenerationRun,
        change_set: ChangeSet,
        *,
        change_sets: list[ChangeSet],
        old_versions: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> list[ContextPack]:
        existing_pack = self._find_existing_prompt_pack(run, change_set)
        if existing_pack is not None:
            return [existing_pack]
        project = ProjectService(self.db).get_project(change_set.project_id)
        story = (
            self.db.get(BusinessRequirementStory, change_set.source_story_id)
            if change_set.source_story_id
            else None
        )
        prompt = build_prompt_pack_prompt(
            project_config=project_config_snapshot(project),
            selected_story=story_snapshot(story),
            change_set=change_set_snapshot(change_set),
            change_sets=[change_set_snapshot(item) for item in change_sets],
            old_versions=old_versions,
            new_versions=new_versions,
            project_blueprint={},
        )
        parsed = generate_orchestration_json(
            prompt.system,
            prompt.user,
            response_model=PromptPackOutput,
            llm_client_factory=self.llm_client_factory,
        )
        content = validate_prompt_pack_payload(parsed)
        pack = ContextPack(
            project_id=project.id,
            blueprint_id=None,
            version=self._next_version(project.id),
            source_requirement_id=change_set.source_requirement_id,
            source_story_id=change_set.source_story_id,
            change_set_id=change_set.id,
            generation_run_id=run.id,
            role="prompt_pack",
            title=content["batch_summary"],
            summary=content["batch_summary"],
            content=content,
            diff_from_previous=content.get("diff_summary", {}),
            prompt_text=_prompt_text_from_content(content),
            format="markdown",
        )
        self.db.add(pack)
        self.db.flush()
        self.db.commit()
        self.db.refresh(pack)
        return [pack]

    def _find_existing_prompt_pack(
        self,
        run: GenerationRun,
        change_set: ChangeSet,
    ) -> ContextPack | None:
        return self.db.scalar(
            select(ContextPack)
            .where(
                ContextPack.project_id == change_set.project_id,
                ContextPack.change_set_id == change_set.id,
                ContextPack.role == "prompt_pack",
            )
            .order_by(ContextPack.created_at.desc())
            .limit(1)
        )

    def _batch_change_sets(self, change_set: ChangeSet) -> list[ChangeSet]:
        if change_set.batch_id is None:
            return [change_set]
        return list(
            self.db.scalars(
                select(ChangeSet)
                .where(
                    ChangeSet.project_id == change_set.project_id,
                    ChangeSet.batch_id == change_set.batch_id,
                )
                .order_by(ChangeSet.created_at.asc())
            )
        )

    def _next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(ContextPack)
            .where(ContextPack.project_id == project_id)
            .order_by(ContextPack.version.desc(), ContextPack.created_at.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1


def _prompt_text_from_content(content: dict[str, Any]) -> str:
    frontend = content.get("frontend_prompt", {})
    backend = content.get("backend_prompt", {})
    parts = [f"# {content.get('batch_summary', 'Prompt Pack')}"]
    diff_summary = content.get("diff_summary")
    if isinstance(diff_summary, dict):
        ux_ui_lines = _diff_summary_lines(diff_summary, ("ux_design", "ui_design"))
        if ux_ui_lines:
            parts.append("## UX/UI 差异\n\n" + "\n".join(ux_ui_lines))
    if frontend.get("needed"):
        parts.append(f"## {frontend.get('title', 'Frontend')}\n\n{frontend.get('prompt', '')}")
    if backend.get("needed"):
        parts.append(f"## {backend.get('title', 'Backend')}\n\n{backend.get('prompt', '')}")
    return "\n\n".join(parts).strip()


def _diff_summary_lines(diff_summary: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for key in keys:
        value = diff_summary.get(key)
        if value is None:
            continue
        lines.append(f"- {key}: {_compact_diff_value(value)}")
    return lines


def _compact_diff_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}={item}")
        return "；".join(parts)
    return str(value)
