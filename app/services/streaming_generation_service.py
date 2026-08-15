from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.core.tech_stack import tech_stack_items_to_payload, tech_stack_items_to_text
from app.generators.api_contract_generator import (
    ApiContractValidationError,
    validate_api_contract_content,
)
from app.generators.blueprint_generator import BlueprintValidationError, validate_blueprint_content
from app.generators.db_model_generator import DbModelValidationError, validate_db_model_content
from app.llm.client import (
    CONFIGURATION_ERROR_DETAIL,
    EMPTY_RESPONSE_DETAIL,
    REQUEST_ERROR_DETAIL,
    RESPONSE_FORMAT_ERROR_DETAIL,
    LLMConfigurationError,
    LLMEmptyResponseError,
    LLMRequestError,
    LLMResponseFormatError,
    OpenAICompatibleLLMClient,
)
from app.llm.json_client import LLMJsonGenerationError
from app.llm.structured_client import generate_structured_json
from app.models.api_contract import ApiContractDraft
from app.models.blueprint import ProjectBlueprint
from app.models.business_requirement_story import BusinessRequirementStory
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement
from app.prompts.api_contract_generator import (
    build_api_contract_generation_prompt,
)
from app.prompts.blueprint_generator import (
    build_blueprint_generation_prompt,
)
from app.prompts.business_story_decomposer import (
    build_business_story_decomposition_prompt,
)
from app.prompts.db_model_generator import (
    build_db_model_generation_prompt,
)
from app.prompts.templates.api_contract_generator.output_schema import ApiContractOutput
from app.prompts.templates.blueprint_generator.output_schema import ProjectBlueprintOutput
from app.prompts.templates.business_story_decomposer.output_schema import (
    BusinessStoryDecompositionOutput,
)
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput
from app.schemas.api_contract import ApiContractDraftResponse
from app.schemas.blueprint import ProjectBlueprintRead
from app.schemas.business_requirement_story import (
    BusinessRequirementStoryResponse,
    GenerateBusinessRequirementStoriesRequest,
)
from app.schemas.db_model_draft import DbModelDraftResponse
from app.services.api_contract_service import (
    NO_BLUEPRINT_MESSAGE as API_CONTRACT_NO_BLUEPRINT_MESSAGE,
)
from app.services.api_contract_service import RUN_TYPE as API_CONTRACT_RUN_TYPE
from app.services.api_contract_service import ApiContractService, _count_api_contract_content
from app.services.blueprint_service import BlueprintService
from app.services.business_requirement_story_service import BusinessRequirementStoryService
from app.services.business_story_generation_service import (
    BUSINESS_STORY_FAILED_MESSAGE,
    BUSINESS_STORY_RUNNING_MESSAGE,
    BUSINESS_STORY_SUCCEEDED_MESSAGE,
    JSON_OBJECT_RESPONSE_FORMAT,
    REQUIREMENT_ALREADY_APPLIED_MESSAGE,
    REQUIREMENT_NOT_FOUND_MESSAGE,
    _count_priority_payloads,
    _current_story_snapshots,
    _validate_story_payloads,
)
from app.services.business_story_generation_service import (
    EMPTY_REQUIREMENT_MESSAGE as BUSINESS_STORY_EMPTY_REQUIREMENT_MESSAGE,
)
from app.services.business_story_generation_service import (
    NO_REQUIREMENT_MESSAGE as BUSINESS_STORY_NO_REQUIREMENT_MESSAGE,
)
from app.services.business_story_generation_service import (
    RUN_TYPE as BUSINESS_STORY_RUN_TYPE,
)
from app.services.business_story_generation_service import (
    _build_input_snapshot as build_business_story_input_snapshot,
)
from app.services.db_model_service import NO_BLUEPRINT_MESSAGE as DB_MODEL_NO_BLUEPRINT_MESSAGE
from app.services.db_model_service import RUN_TYPE as DB_MODEL_RUN_TYPE
from app.services.db_model_service import DbModelService, _count_db_model_content
from app.services.generation_service import (
    EMPTY_REQUIREMENT_MESSAGE as BLUEPRINT_EMPTY_REQUIREMENT_MESSAGE,
)
from app.services.generation_service import (
    NO_REQUIREMENT_MESSAGE as BLUEPRINT_NO_REQUIREMENT_MESSAGE,
)
from app.services.generation_service import (
    RUN_TYPE as BLUEPRINT_RUN_TYPE,
)
from app.services.generation_service import (
    _count_blueprint_content,
)
from app.services.project_service import ProjectService
from app.services.requirement_service import RequirementService

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

ERROR_EVENTS: dict[type[Exception], tuple[str, int, str]] = {
    LLMConfigurationError: (
        "llm_not_configured",
        status.HTTP_503_SERVICE_UNAVAILABLE,
        CONFIGURATION_ERROR_DETAIL,
    ),
    LLMRequestError: ("llm_request_failed", status.HTTP_502_BAD_GATEWAY, REQUEST_ERROR_DETAIL),
    LLMEmptyResponseError: (
        "llm_empty_response",
        status.HTTP_502_BAD_GATEWAY,
        EMPTY_RESPONSE_DETAIL,
    ),
}

@dataclass
class StreamingGenerationSpec:
    project_id: UUID
    module: str
    run_type: str
    system_prompt: str
    user_payload: dict[str, Any] | str
    input_snapshot: dict[str, Any]
    parse_and_validate: Callable[[dict[str, Any]], Any]
    save: Callable[[GenerationRun, Any], Any]
    serialize_resource: Callable[[Any], dict[str, Any]]
    response_model: type[BaseModel]
    requirement_id: UUID | None = None
    extra_params: dict[str, Any] | None = None


class StreamingGenerationService:
    def __init__(
        self,
        db: Session,
        llm_client_factory: Callable[[], OpenAICompatibleLLMClient] | None = None,
    ) -> None:
        self.db = db
        self.llm_client_factory = llm_client_factory

    def generate(self, spec: StreamingGenerationSpec) -> Any:
        run = GenerationRun(
            project_id=spec.project_id,
            requirement_id=spec.requirement_id,
            run_type=spec.run_type,
            status="running",
            progress=0,
            message=_progress_message(spec.module, 0),
            input_snapshot=spec.input_snapshot,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        _log_stage(spec, run, "created", monotonic())
        return self.execute_existing_run(run, spec)

    def execute_existing_run(self, run: GenerationRun, spec: StreamingGenerationSpec) -> Any:
        started_at = monotonic()
        raw_text_length: int | None = None
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        run.completed_at = None
        run.error_message = None
        run.requirement_id = spec.requirement_id
        run.input_snapshot = spec.input_snapshot
        if run.progress < 0:
            run.progress = 0
        if not run.message:
            run.message = _progress_message(spec.module, 0)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        try:
            _update_run_progress(self.db, run, 10, _progress_message(spec.module, 10))
            _log_stage(spec, run, "llm_start", started_at)
            try:
                parsed = generate_structured_json(
                    spec.system_prompt,
                    spec.user_payload,
                    response_model=spec.response_model,
                    llm_client_factory=self.llm_client_factory,
                    extra_params=spec.extra_params,
                )
            except LLMJsonGenerationError as exc:
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="parse_json_failed",
                    raw_text_length=raw_text_length,
                )
                raise
            except LLMResponseFormatError as exc:
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="schema_validation_failed",
                    raw_text_length=raw_text_length,
                )
                raise
            raw_text_length = len(json.dumps(parsed, ensure_ascii=False))
            if not parsed:
                raise LLMEmptyResponseError("LLM structured content is empty.")

            _update_run_progress(self.db, run, 60, _progress_message(spec.module, 60))
            _log_stage(spec, run, "structured_complete", started_at)
            try:
                resource_input = spec.parse_and_validate(parsed)
            except (
                BlueprintValidationError,
                ApiContractValidationError,
                DbModelValidationError,
                ValueError,
            ) as exc:
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="validate",
                    raw_text_length=raw_text_length,
                )
                raise

            _update_run_progress(self.db, run, 80, _progress_message(spec.module, 80))
            _log_stage(spec, run, "parsed", started_at)
            try:
                resource = spec.save(run, resource_input)
                _merge_run_success_snapshot(
                    run,
                    spec,
                    resource,
                    raw_text_length=raw_text_length,
                )
                _update_run_progress(self.db, run, 95, _progress_message(spec.module, 95))
                _log_stage(spec, run, "saved", started_at)
                _refresh_resource(self.db, resource)
            except Exception as exc:
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="save",
                    raw_text_length=raw_text_length,
                )
                raise

            run.status = "completed"
            run.progress = 100
            run.message = _progress_message(spec.module, 100)
            run.completed_at = datetime.now(UTC)
            self.db.add(run)
            self.db.commit()
            _refresh_resource(self.db, resource)
            _log_stage(spec, run, "done", started_at)
            return resource
        except LLMConfigurationError as exc:
            self._mark_run_failed(
                run,
                exc,
                failure_stage="llm_request",
                raw_text_length=raw_text_length,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=CONFIGURATION_ERROR_DETAIL,
            ) from exc
        except LLMRequestError as exc:
            self._mark_run_failed(
                run,
                exc,
                failure_stage="llm_request",
                raw_text_length=raw_text_length,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=REQUEST_ERROR_DETAIL,
            ) from exc
        except LLMEmptyResponseError as exc:
            self._mark_run_failed(
                run,
                exc,
                failure_stage="llm_request",
                raw_text_length=raw_text_length,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EMPTY_RESPONSE_DETAIL,
            ) from exc
        except (
            LLMJsonGenerationError,
            LLMResponseFormatError,
            BlueprintValidationError,
            ApiContractValidationError,
            DbModelValidationError,
            ValueError,
        ) as exc:
            if run.status != "failed":
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="validate",
                    raw_text_length=raw_text_length,
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=RESPONSE_FORMAT_ERROR_DETAIL,
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            if run.status != "failed":
                self._mark_run_failed(
                    run,
                    exc,
                    failure_stage="save",
                    raw_text_length=raw_text_length,
                )
            logger.exception(
                "streaming_generation.generate.failed module=%s project_id=%s run_id=%s "
                "requirement_id=%s progress=%s elapsed_ms=%s error_type=%s message=%s",
                spec.module,
                spec.project_id,
                run.id,
                spec.requirement_id,
                run.progress,
                _elapsed_ms(started_at),
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成失败，请检查项目数据或稍后重试。",
            ) from exc

    def stream(self, spec: StreamingGenerationSpec) -> Iterator[str]:
        try:
            yield sse_event(
                {
                    "type": "start",
                    "module": spec.module,
                    "progress": 0,
                    "message": _progress_message(spec.module, 0),
                }
            )
            resource = self.generate(spec)
            yield sse_event(
                {
                    "type": "saved",
                    "module": spec.module,
                    "progress": 100,
                    "message": _progress_message(spec.module, 100),
                    "resource": spec.serialize_resource(resource),
                }
            )
            yield sse_event(
                {
                    "type": "done",
                    "module": spec.module,
                    "progress": 100,
                    "message": _progress_message(spec.module, 100),
                }
            )
        except HTTPException as exc:
            code, event_status, message = _error_event_detail(exc)
            yield sse_event(
                {
                    "type": "error",
                    "module": spec.module,
                    "code": code,
                    "status": event_status,
                    "progress": 0,
                    "message": message,
                }
            )

    def _mark_run_failed(
        self,
        run: GenerationRun,
        exc: Exception,
        *,
        failure_stage: str = "save",
        raw_text_length: int | None = None,
    ) -> None:
        if run.status == "failed":
            return
        self.db.rollback()
        run.status = "failed"
        run.message = _failure_message(run)
        run.error_message = _excerpt(str(exc), 1000)
        run.output_snapshot = {
            "failure_stage": failure_stage,
            **({"raw_text_length": raw_text_length} if raw_text_length is not None else {}),
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()

    def build_business_stories_spec(
        self,
        project_id: UUID,
        payload: GenerateBusinessRequirementStoriesRequest,
    ) -> StreamingGenerationSpec:
        project = ProjectService(self.db).get_project(project_id)
        requirement = self._resolve_requirement(project_id, payload.requirement_id)
        if not requirement.raw_text or not requirement.raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=BUSINESS_STORY_EMPTY_REQUIREMENT_MESSAGE,
            )
        if requirement.status == "applied":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=REQUIREMENT_ALREADY_APPLIED_MESSAGE,
            )

        current_business_stories = _current_story_snapshots(self.db, project_id)
        prompt = build_business_story_decomposition_prompt(
            project,
            requirement,
            current_business_stories,
        )
        input_snapshot = build_business_story_input_snapshot(
            project,
            requirement,
            payload.overwrite,
            current_business_stories=current_business_stories,
        )

        def save(
            run: GenerationRun,
            story_payloads: list[dict[str, Any]],
        ) -> list[BusinessRequirementStory]:
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
            run.output_snapshot = {
                "story_count": len(stories),
                "priority_counts": _count_priority_payloads(story_payloads),
            }
            return stories

        return StreamingGenerationSpec(
            project_id=project_id,
            module="business_stories",
            run_type=BUSINESS_STORY_RUN_TYPE,
            requirement_id=requirement.id,
            system_prompt=prompt.system,
            user_payload=prompt.user,
            input_snapshot=input_snapshot,
            parse_and_validate=_validate_story_payloads,
            save=save,
            serialize_resource=lambda stories: {
                "items": [
                    _model_to_dict(BusinessRequirementStoryResponse, story) for story in stories
                ]
            },
            response_model=BusinessStoryDecompositionOutput,
            extra_params=JSON_OBJECT_RESPONSE_FORMAT,
        )

    def build_blueprint_spec(self, project_id: UUID) -> StreamingGenerationSpec:
        project = ProjectService(self.db).get_project(project_id)
        requirement = RequirementService(self.db).get_latest_requirement(project_id)
        if requirement is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=BLUEPRINT_NO_REQUIREMENT_MESSAGE,
            )
        if not requirement.raw_text or not requirement.raw_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=BLUEPRINT_EMPTY_REQUIREMENT_MESSAGE,
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
        input_snapshot = {
            "project_id": str(project_id),
            "requirement_id": str(requirement.id),
            "source": "requirement + business_stories",
            "business_requirement_story_ids": [story["id"] for story in business_story_context],
            "target_frontend_stack": frontend_stack,
            "target_backend_stack": backend_stack,
            "target_frontend_stack_items": tech_stack_items_to_payload(
                getattr(project, "target_frontend_stack_items", [])
            ),
            "target_backend_stack_items": tech_stack_items_to_payload(
                getattr(project, "target_backend_stack_items", [])
            ),
        }

        def validate(parsed: dict[str, Any]) -> dict[str, Any]:
            return validate_blueprint_content(parsed, project, business_story_context)

        def save(run: GenerationRun, content: dict[str, Any]) -> ProjectBlueprint:
            blueprint = ProjectBlueprint(
                project_id=project_id,
                version=BlueprintService(self.db).get_next_version(project_id),
                source_requirement_id=requirement.id,
                generation_run_id=run.id,
                title="项目蓝图",
                summary="基于用户需求生成的第一版项目蓝图草案。",
                content=content,
            )
            self.db.add(blueprint)
            self.db.flush()
            run.output_snapshot = {
                "blueprint_id": str(blueprint.id),
                "version": blueprint.version,
                "summary": blueprint.summary,
                "counts": _count_blueprint_content(content),
            }
            return blueprint

        prompt = build_blueprint_generation_prompt(
            project,
            requirement,
            business_story_context,
        )
        return StreamingGenerationSpec(
            project_id=project_id,
            module="blueprint",
            run_type=BLUEPRINT_RUN_TYPE,
            system_prompt=prompt.system,
            user_payload=prompt.user,
            input_snapshot=input_snapshot,
            parse_and_validate=validate,
            save=save,
            serialize_resource=lambda blueprint: _model_to_dict(ProjectBlueprintRead, blueprint),
            response_model=ProjectBlueprintOutput,
        )

    def build_api_contract_spec(self, project_id: UUID) -> StreamingGenerationSpec:
        project = ProjectService(self.db).get_project(project_id)
        blueprint = BlueprintService(self.db).get_latest_blueprint(project_id)
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=API_CONTRACT_NO_BLUEPRINT_MESSAGE,
            )
        if not isinstance(blueprint.content, dict) or not blueprint.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目蓝图内容为空，无法生成 API 契约。",
            )

        def save(run: GenerationRun, content: dict[str, Any]) -> ApiContractDraft:
            draft = ApiContractDraft(
                project_id=project_id,
                blueprint_id=blueprint.id,
                version=ApiContractService(self.db).get_next_version(project_id),
                generation_run_id=run.id,
                title="API 契约草案",
                summary="基于项目蓝图生成的 API 契约草案。",
                base_path=content.get("api_base_path") or content.get("base_path", "/api/v1"),
                content=content,
            )
            self.db.add(draft)
            self.db.flush()
            run.output_snapshot = {
                "api_contract_id": str(draft.id),
                "version": draft.version,
                "summary": draft.summary,
                "counts": _count_api_contract_content(content),
            }
            return draft

        prompt = build_api_contract_generation_prompt(project, blueprint.content)
        return StreamingGenerationSpec(
            project_id=project_id,
            module="api_contract",
            run_type=API_CONTRACT_RUN_TYPE,
            system_prompt=prompt.system,
            user_payload=prompt.user,
            input_snapshot={
                "project_id": str(project_id),
                "source": "project + latest_blueprint",
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
            },
            parse_and_validate=validate_api_contract_content,
            save=save,
            serialize_resource=lambda draft: _model_to_dict(ApiContractDraftResponse, draft),
            response_model=ApiContractOutput,
        )

    def build_db_model_spec(self, project_id: UUID) -> StreamingGenerationSpec:
        project = ProjectService(self.db).get_project(project_id)
        blueprint = BlueprintService(self.db).get_latest_blueprint(project_id)
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=DB_MODEL_NO_BLUEPRINT_MESSAGE,
            )
        if not isinstance(blueprint.content, dict) or not blueprint.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目蓝图内容为空，无法生成数据库模型。",
            )
        api_contract = ApiContractService(self.db).get_latest_api_contract(project_id)
        api_contract_content = api_contract.content if api_contract is not None else None

        def save(run: GenerationRun, content: dict[str, Any]) -> DbModelDraft:
            draft = DbModelDraft(
                project_id=project_id,
                blueprint_id=blueprint.id,
                version=DbModelService(self.db).get_next_version(project_id),
                generation_run_id=run.id,
                title="数据库模型草案",
                summary="基于项目蓝图生成的数据库模型草案。",
                content=content,
            )
            self.db.add(draft)
            self.db.flush()
            run.output_snapshot = {
                "db_model_id": str(draft.id),
                "version": draft.version,
                "summary": draft.summary,
                "counts": _count_db_model_content(content),
            }
            return draft

        prompt = build_db_model_generation_prompt(
            project,
            blueprint.content,
            api_contract_content,
        )
        return StreamingGenerationSpec(
            project_id=project_id,
            module="db_model",
            run_type=DB_MODEL_RUN_TYPE,
            system_prompt=prompt.system,
            user_payload=prompt.user,
            input_snapshot={
                "project_id": str(project_id),
                "source": "project + latest_blueprint + optional_latest_api_contract",
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
                "api_contract_id": str(api_contract.id) if api_contract is not None else None,
                "api_contract_version": api_contract.version if api_contract is not None else None,
            },
            parse_and_validate=validate_db_model_content,
            save=save,
            serialize_resource=lambda draft: _model_to_dict(DbModelDraftResponse, draft),
            response_model=DbModelOutput,
        )

    def _resolve_requirement(
        self, project_id: UUID, requirement_id: UUID | None
    ) -> Requirement:
        if requirement_id is None:
            requirement = RequirementService(self.db).get_latest_requirement(project_id)
            if requirement is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=BUSINESS_STORY_NO_REQUIREMENT_MESSAGE,
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


def sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _update_run_progress(
    db: Session, run: GenerationRun, progress: int, message: str | None
) -> None:
    if progress <= run.progress:
        return
    run.progress = progress
    run.message = message
    db.add(run)
    db.commit()


def _progress_message(module: str, progress: int) -> str:
    if module == "business_stories":
        if progress >= 100:
            return BUSINESS_STORY_SUCCEEDED_MESSAGE
        if progress >= 95:
            return "业务需求故事已保存。"
        if progress >= 80:
            return "正在保存业务需求故事..."
        if progress >= 60:
            return "正在解析业务需求故事..."
        if progress >= 25:
            return BUSINESS_STORY_RUNNING_MESSAGE
        if progress >= 10:
            return "开始调用大模型更新业务需求故事..."
        return BUSINESS_STORY_RUNNING_MESSAGE
    if progress >= 100:
        return "生成完成"
    if progress >= 95:
        return "生成结果已保存。"
    if progress >= 80:
        return "正在保存生成结果..."
    if progress >= 60:
        return "正在解析结构化结果..."
    if progress >= 25:
        return "正在生成结构化结果..."
    return "开始调用大模型生成..."


def _failure_message(run: GenerationRun) -> str:
    if run.run_type == BUSINESS_STORY_RUN_TYPE:
        return BUSINESS_STORY_FAILED_MESSAGE
    return "生成失败"


def _error_event_detail(exc: Exception) -> tuple[str, int, str]:
    if isinstance(exc, HTTPException):
        detail = str(exc.detail)
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            return "llm_not_configured", exc.status_code, detail
        if detail == REQUEST_ERROR_DETAIL:
            return "llm_request_failed", exc.status_code, detail
        if detail == EMPTY_RESPONSE_DETAIL:
            return "llm_empty_response", exc.status_code, detail
        if detail == RESPONSE_FORMAT_ERROR_DETAIL:
            return "llm_output_format_invalid", exc.status_code, detail
        return "generation_failed", exc.status_code, detail
    for exception_type, detail in ERROR_EVENTS.items():
        if isinstance(exc, exception_type):
            return detail
    if isinstance(
        exc,
        (
            LLMJsonGenerationError,
            LLMResponseFormatError,
            BlueprintValidationError,
            ApiContractValidationError,
            DbModelValidationError,
            ValueError,
        ),
    ):
        return (
            "llm_output_format_invalid",
            status.HTTP_502_BAD_GATEWAY,
            RESPONSE_FORMAT_ERROR_DETAIL,
        )
    return (
        "generation_failed",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "生成失败，请检查项目数据或稍后重试。",
    )


def _model_to_dict(schema: type[BaseModel], value: Any) -> dict[str, Any]:
    return schema.model_validate(value).model_dump(mode="json")


def _refresh_resource(db: Session, resource: Any) -> None:
    if isinstance(resource, list):
        for item in resource:
            db.refresh(item)
        return
    db.refresh(resource)


def _merge_run_success_snapshot(
    run: GenerationRun,
    spec: StreamingGenerationSpec,
    resource: Any,
    *,
    raw_text_length: int,
) -> None:
    snapshot = dict(run.output_snapshot or {})
    snapshot["raw_text_length"] = raw_text_length
    if "counts" not in snapshot:
        counts = _extract_counts(snapshot, spec.module)
        if counts:
            snapshot["counts"] = counts
    if "summary" not in snapshot:
        snapshot["summary"] = _success_summary(spec.module, resource, snapshot)
    if isinstance(resource, list):
        snapshot["resource_ids"] = [str(item.id) for item in resource if hasattr(item, "id")]
    elif hasattr(resource, "id"):
        snapshot["resource_id"] = str(resource.id)
    run.output_snapshot = snapshot


def _extract_counts(snapshot: dict[str, Any], module: str) -> dict[str, Any]:
    if module == "business_stories":
        counts: dict[str, Any] = {}
        if "story_count" in snapshot:
            counts["stories"] = snapshot["story_count"]
        if "priority_counts" in snapshot:
            counts["priority_counts"] = snapshot["priority_counts"]
        return counts
    return {}


def _success_summary(
    module: str,
    resource: Any,
    snapshot: dict[str, Any],
) -> str:
    if module == "business_stories":
        count = snapshot.get("story_count")
        if count is None and isinstance(resource, list):
            count = len(resource)
        return f"已更新 {count} 条业务需求故事。"
    return str(snapshot.get("summary") or _progress_message(module, 100))


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _log_stage(
    spec: StreamingGenerationSpec,
    run: GenerationRun,
    stage: str,
    started_at: float,
) -> None:
    logger.info(
        "streaming_generation.stage module=%s project_id=%s requirement_id=%s "
        "run_id=%s stage=%s progress=%s status=%s elapsed_ms=%s",
        spec.module,
        spec.project_id,
        spec.requirement_id,
        run.id,
        stage,
        run.progress,
        run.status,
        _elapsed_ms(started_at),
    )


def _elapsed_ms(started_at: float) -> int:
    return int((monotonic() - started_at) * 1000)
