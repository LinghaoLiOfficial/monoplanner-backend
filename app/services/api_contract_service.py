import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.generators.api_contract_generator import (
    ApiContractValidationError,
    build_api_contract_content,
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
from app.models.api_contract import ApiContractDraft
from app.models.generation_run import GenerationRun
from app.models.user import User
from app.schemas.api_contract import ApiContractDraftUpdate
from app.services.blueprint_service import BlueprintService
from app.services.design_asset_service import DesignAssetService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
RUN_TYPE = "generate_api_contract"
NO_BLUEPRINT_MESSAGE = "请先生成项目蓝图。"


class ApiContractService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def generate_api_contract(self, project_id: UUID) -> ApiContractDraft:
        project = ProjectService(self.db, self.current_user).get_project(project_id)
        blueprint = BlueprintService(self.db, self.current_user).get_latest_blueprint(project_id)
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=NO_BLUEPRINT_MESSAGE,
            )
        if not isinstance(blueprint.content, dict) or not blueprint.content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目蓝图内容为空，无法生成 API 契约。",
            )

        run = GenerationRun(
            project_id=project_id,
            run_type=RUN_TYPE,
            status="running",
            input_snapshot={
                "project_id": str(project_id),
                "source": "project + latest_blueprint",
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
            },
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "api_contract.generate.start project_id=%s blueprint_id=%s run_id=%s",
            project_id,
            blueprint.id,
            run.id,
        )
        try:
            content = build_api_contract_content(project, blueprint.content)
            draft = ApiContractDraft(
                project_id=project_id,
                blueprint_id=blueprint.id,
                version=self.get_next_version(project_id),
                title="API 契约草案",
                summary="基于项目蓝图生成的 API 契约草案。",
                base_path=content["base_path"],
                content=content,
            )
            self.db.add(draft)
            self.db.flush()
            run.status = "completed"
            run.output_snapshot = {
                "api_contract_id": str(draft.id),
                "version": draft.version,
                "summary": draft.summary,
                "counts": _count_api_contract_content(content),
            }
            run.completed_at = datetime.now(UTC)
            self.db.add(run)
            self.db.commit()
            self.db.refresh(draft)
            logger.info(
                "api_contract.generate.success project_id=%s api_contract_id=%s",
                project_id,
                draft.id,
            )
            return draft
        except LLMConfigurationError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "api_contract.generate.failed project_id=%s error_type=%s message=%s",
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
                "api_contract.generate.failed project_id=%s error_type=%s message=%s",
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
                "api_contract.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EMPTY_RESPONSE_DETAIL,
            ) from exc
        except (LLMResponseFormatError, ApiContractValidationError, ValueError) as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "api_contract.generate.failed project_id=%s error_type=%s message=%s",
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
            logger.exception("Failed to generate API contract for project %s", project_id)
            self._mark_run_failed(run, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成 API 契约草案失败，请检查项目数据或稍后重试。",
            ) from exc

    def list_project_api_contracts(self, project_id: UUID) -> list[ApiContractDraft]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        return list(
            self.db.scalars(
                select(ApiContractDraft)
                .where(ApiContractDraft.project_id == project_id)
                .order_by(ApiContractDraft.created_at.desc())
            )
        )

    def get_api_contract(self, api_contract_id: UUID) -> ApiContractDraft:
        draft = self.db.get(ApiContractDraft, api_contract_id)
        if draft is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API contract draft not found.",
            )
        ProjectService(self.db, self.current_user).get_project(draft.project_id)
        return draft

    def get_latest_api_contract(self, project_id: UUID) -> ApiContractDraft | None:
        return self.db.scalar(
            select(ApiContractDraft)
            .where(ApiContractDraft.project_id == project_id)
            .order_by(ApiContractDraft.created_at.desc())
            .limit(1)
        )

    def update_api_contract(
        self, api_contract_id: UUID, payload: ApiContractDraftUpdate
    ) -> ApiContractDraft:
        return DesignAssetService(self.db, self.current_user).update_asset(
            ApiContractDraft,
            api_contract_id,
            payload,
            not_found_detail="API contract draft not found.",
            extra_fields={"base_path"},
        )

    def get_next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(ApiContractDraft)
            .where(ApiContractDraft.project_id == project_id)
            .order_by(ApiContractDraft.version.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1

    def _mark_run_failed(self, run: GenerationRun, exc: Exception) -> None:
        self.db.rollback()
        run.status = "failed"
        run.output_snapshot = None
        run.error_message = _excerpt(str(exc), 1000)
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()


def _count_api_contract_content(content: dict[str, Any]) -> dict[str, int]:
    return {
        "resources": len(content.get("resources", [])),
        "endpoints": sum(
            len(resource.get("endpoints", []))
            for resource in content.get("resources", [])
            if isinstance(resource, dict)
        ),
        "schemas": len(content.get("schemas", [])),
    }


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
