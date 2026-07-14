import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.generators.db_model_generator import DbModelValidationError, build_db_model_content
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
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.models.user import User
from app.schemas.db_model_draft import DbModelDraftUpdate
from app.services.api_contract_service import ApiContractService
from app.services.blueprint_service import BlueprintService
from app.services.design_asset_service import DesignAssetService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)
RUN_TYPE = "generate_db_model"
NO_BLUEPRINT_MESSAGE = "请先生成项目蓝图。"


class DbModelService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def generate_db_model(self, project_id: UUID) -> DbModelDraft:
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
                detail="项目蓝图内容为空，无法生成数据库模型。",
            )
        api_contract = ApiContractService(self.db, self.current_user).get_latest_api_contract(
            project_id
        )
        api_contract_content = api_contract.content if api_contract is not None else None

        run = GenerationRun(
            project_id=project_id,
            run_type=RUN_TYPE,
            status="running",
            input_snapshot={
                "project_id": str(project_id),
                "source": "project + latest_blueprint + optional_latest_api_contract",
                "blueprint_id": str(blueprint.id),
                "blueprint_version": blueprint.version,
                "api_contract_id": str(api_contract.id) if api_contract is not None else None,
                "api_contract_version": api_contract.version if api_contract is not None else None,
            },
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "db_model.generate.start project_id=%s blueprint_id=%s run_id=%s",
            project_id,
            blueprint.id,
            run.id,
        )
        try:
            content = build_db_model_content(project, blueprint.content, api_contract_content)
            draft = DbModelDraft(
                project_id=project_id,
                blueprint_id=blueprint.id,
                version=self.get_next_version(project_id),
                title="数据库模型草案",
                summary="基于项目蓝图生成的数据库模型草案。",
                content=content,
            )
            self.db.add(draft)
            self.db.flush()
            run.status = "completed"
            run.output_snapshot = {
                "db_model_id": str(draft.id),
                "version": draft.version,
                "summary": draft.summary,
                "counts": _count_db_model_content(content),
            }
            run.completed_at = datetime.now(UTC)
            self.db.add(run)
            self.db.commit()
            self.db.refresh(draft)
            logger.info(
                "db_model.generate.success project_id=%s db_model_id=%s",
                project_id,
                draft.id,
            )
            return draft
        except LLMConfigurationError as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "db_model.generate.failed project_id=%s error_type=%s message=%s",
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
                "db_model.generate.failed project_id=%s error_type=%s message=%s",
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
                "db_model.generate.failed project_id=%s error_type=%s message=%s",
                project_id,
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=EMPTY_RESPONSE_DETAIL,
            ) from exc
        except (LLMResponseFormatError, DbModelValidationError, ValueError) as exc:
            self._mark_run_failed(run, exc)
            logger.warning(
                "db_model.generate.failed project_id=%s error_type=%s message=%s",
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
            logger.exception("Failed to generate DB model for project %s", project_id)
            self._mark_run_failed(run, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成数据库模型草案失败，请检查项目数据或稍后重试。",
            ) from exc

    def list_project_db_models(self, project_id: UUID) -> list[DbModelDraft]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        return list(
            self.db.scalars(
                select(DbModelDraft)
                .where(DbModelDraft.project_id == project_id)
                .order_by(DbModelDraft.created_at.desc())
            )
        )

    def get_db_model(self, db_model_id: UUID) -> DbModelDraft:
        draft = self.db.get(DbModelDraft, db_model_id)
        if draft is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DB model draft not found.",
            )
        ProjectService(self.db, self.current_user).get_project(draft.project_id)
        return draft

    def get_latest_db_model(self, project_id: UUID) -> DbModelDraft | None:
        return self.db.scalar(
            select(DbModelDraft)
            .where(DbModelDraft.project_id == project_id)
            .order_by(DbModelDraft.created_at.desc())
            .limit(1)
        )

    def update_db_model(self, db_model_id: UUID, payload: DbModelDraftUpdate) -> DbModelDraft:
        return DesignAssetService(self.db, self.current_user).update_asset(
            DbModelDraft,
            db_model_id,
            payload,
            not_found_detail="DB model draft not found.",
        )

    def get_next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(DbModelDraft)
            .where(DbModelDraft.project_id == project_id)
            .order_by(DbModelDraft.version.desc())
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


def _count_db_model_content(content: dict[str, Any]) -> dict[str, int]:
    return {
        "entities": len(content.get("entities", [])),
        "relationships": len(content.get("relationships", [])),
        "indexes": len(content.get("indexes", [])),
    }


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
