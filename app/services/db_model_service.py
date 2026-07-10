from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.generators.db_model_generator import build_db_model_content
from app.models.db_model_draft import DbModelDraft
from app.models.generation_run import GenerationRun
from app.services.blueprint_service import BlueprintService
from app.services.project_service import ProjectService


class DbModelService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_db_model(self, project_id: UUID) -> DbModelDraft:
        ProjectService(self.db).get_project(project_id)
        blueprint = BlueprintService(self.db).get_latest_blueprint(project_id)
        if blueprint is None:
            self._record_failed_run(
                project_id, "Project has no blueprint to generate a DB model from."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no blueprint to generate a DB model from.",
            )

        try:
            content = build_db_model_content(blueprint.content)
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
            self.db.add(
                GenerationRun(
                    project_id=project_id,
                    run_type="generate_db_model",
                    status="completed",
                    input_snapshot={
                        "blueprint_id": str(blueprint.id),
                        "version": blueprint.version,
                    },
                    output_snapshot={"db_model_id": str(draft.id), "version": draft.version},
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

    def list_project_db_models(self, project_id: UUID) -> list[DbModelDraft]:
        ProjectService(self.db).get_project(project_id)
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
        return draft

    def get_latest_db_model(self, project_id: UUID) -> DbModelDraft | None:
        return self.db.scalar(
            select(DbModelDraft)
            .where(DbModelDraft.project_id == project_id)
            .order_by(DbModelDraft.created_at.desc())
            .limit(1)
        )

    def get_next_version(self, project_id: UUID) -> int:
        latest = self.db.scalar(
            select(DbModelDraft)
            .where(DbModelDraft.project_id == project_id)
            .order_by(DbModelDraft.version.desc())
            .limit(1)
        )
        return 1 if latest is None else latest.version + 1

    def _record_failed_run(self, project_id: UUID, error_message: str) -> None:
        self.db.rollback()
        self.db.add(
            GenerationRun(
                project_id=project_id,
                run_type="generate_db_model",
                status="failed",
                input_snapshot={"project_id": str(project_id)},
                output_snapshot=None,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )
        self.db.commit()
