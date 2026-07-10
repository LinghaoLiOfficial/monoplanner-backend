from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.generators.api_contract_generator import build_api_contract_content
from app.models.api_contract import ApiContractDraft
from app.models.generation_run import GenerationRun
from app.services.blueprint_service import BlueprintService
from app.services.project_service import ProjectService


class ApiContractService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_api_contract(self, project_id: UUID) -> ApiContractDraft:
        ProjectService(self.db).get_project(project_id)
        blueprint = BlueprintService(self.db).get_latest_blueprint(project_id)
        if blueprint is None:
            self._record_failed_run(
                project_id, "Project has no blueprint to generate an API contract from."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no blueprint to generate an API contract from.",
            )

        try:
            content = build_api_contract_content(blueprint.content)
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
            self.db.add(
                GenerationRun(
                    project_id=project_id,
                    run_type="generate_api_contract",
                    status="completed",
                    input_snapshot={
                        "blueprint_id": str(blueprint.id),
                        "version": blueprint.version,
                    },
                    output_snapshot={"api_contract_id": str(draft.id), "version": draft.version},
                    completed_at=datetime.now(UTC),
                )
            )
            self.db.commit()
            self.db.refresh(draft)
            return draft
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            self._record_failed_run(project_id, str(exc))
            raise

    def list_project_api_contracts(self, project_id: UUID) -> list[ApiContractDraft]:
        ProjectService(self.db).get_project(project_id)
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
        return draft

    def get_latest_api_contract(self, project_id: UUID) -> ApiContractDraft | None:
        return self.db.scalar(
            select(ApiContractDraft)
            .where(ApiContractDraft.project_id == project_id)
            .order_by(ApiContractDraft.created_at.desc())
            .limit(1)
        )

    def get_next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(ApiContractDraft)
            .where(ApiContractDraft.project_id == project_id)
            .order_by(ApiContractDraft.version.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1

    def _record_failed_run(self, project_id: UUID, error_message: str) -> None:
        self.db.rollback()
        self.db.add(
            GenerationRun(
                project_id=project_id,
                run_type="generate_api_contract",
                status="failed",
                input_snapshot={"project_id": str(project_id)},
                output_snapshot=None,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )
        self.db.commit()
