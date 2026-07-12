from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.generators.context_pack_generator import build_context_pack_payloads
from app.models.context_pack import ContextPack
from app.models.generation_run import GenerationRun
from app.models.user import User
from app.schemas.context_pack import ContextPackExportResponse
from app.services.api_contract_service import ApiContractService
from app.services.blueprint_service import BlueprintService
from app.services.db_model_service import DbModelService
from app.services.project_service import ProjectService


class ContextPackService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def generate_context_packs(self, project_id: UUID) -> list[ContextPack]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        blueprint = BlueprintService(self.db, self.current_user).get_latest_blueprint(project_id)
        if blueprint is None:
            self._record_failed_run(
                project_id, "Project has no blueprint to generate context packs from."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no blueprint to generate context packs from.",
            )

        api_contract = ApiContractService(self.db, self.current_user).get_latest_api_contract(
            project_id
        )
        db_model = DbModelService(self.db, self.current_user).get_latest_db_model(project_id)
        try:
            payloads = build_context_pack_payloads(
                blueprint.content,
                api_contract.content if api_contract else None,
                db_model.content if db_model else None,
            )
            packs = [
                ContextPack(
                    project_id=project_id,
                    blueprint_id=blueprint.id,
                    api_contract_id=api_contract.id if api_contract else None,
                    db_model_id=db_model.id if db_model else None,
                    role=payload["role"],
                    title=payload["title"],
                    summary=payload["summary"],
                    content=payload["content"],
                    prompt_text=payload["prompt_text"],
                    format="markdown",
                )
                for payload in payloads
            ]
            self.db.add_all(packs)
            self.db.flush()
            self.db.add(
                GenerationRun(
                    project_id=project_id,
                    run_type="generate_context_packs",
                    status="completed",
                    input_snapshot={
                        "blueprint_id": str(blueprint.id),
                        "api_contract_id": str(api_contract.id) if api_contract else None,
                        "db_model_id": str(db_model.id) if db_model else None,
                    },
                    output_snapshot={
                        "context_pack_ids": [str(pack.id) for pack in packs],
                        "roles": [pack.role for pack in packs],
                    },
                    completed_at=datetime.now(UTC),
                )
            )
            self.db.commit()
            for pack in packs:
                self.db.refresh(pack)
            return packs
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            self._record_failed_run(project_id, str(exc))
            raise

    def execute_context_pack_run(self, run: GenerationRun) -> list[ContextPack]:
        project_id = run.project_id
        ProjectService(self.db, self.current_user).get_project(project_id)
        blueprint = BlueprintService(self.db).get_latest_blueprint(project_id)
        if blueprint is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project has no blueprint to generate context packs from.",
            )

        api_contract = ApiContractService(self.db).get_latest_api_contract(project_id)
        db_model = DbModelService(self.db).get_latest_db_model(project_id)
        run.status = "running"
        run.progress = max(run.progress, 10)
        run.message = "开始生成 Context Pack..."
        run.started_at = run.started_at or datetime.now(UTC)
        run.input_snapshot = {
            "blueprint_id": str(blueprint.id),
            "api_contract_id": str(api_contract.id) if api_contract else None,
            "db_model_id": str(db_model.id) if db_model else None,
        }
        self.db.add(run)
        self.db.commit()

        payloads = build_context_pack_payloads(
            blueprint.content,
            api_contract.content if api_contract else None,
            db_model.content if db_model else None,
        )
        run.progress = 80
        run.message = "正在保存 Context Pack..."
        self.db.add(run)
        self.db.commit()

        packs = [
            ContextPack(
                project_id=project_id,
                blueprint_id=blueprint.id,
                api_contract_id=api_contract.id if api_contract else None,
                db_model_id=db_model.id if db_model else None,
                role=payload["role"],
                title=payload["title"],
                summary=payload["summary"],
                content=payload["content"],
                prompt_text=payload["prompt_text"],
                format="markdown",
            )
            for payload in payloads
        ]
        self.db.add_all(packs)
        self.db.flush()
        run.status = "completed"
        run.progress = 100
        run.message = "生成完成"
        run.output_snapshot = {
            "context_pack_ids": [str(pack.id) for pack in packs],
            "resource_ids": [str(pack.id) for pack in packs],
            "roles": [pack.role for pack in packs],
            "counts": {"context_packs": len(packs)},
            "summary": f"已生成 {len(packs)} 个 Context Pack。",
        }
        run.completed_at = datetime.now(UTC)
        self.db.add(run)
        self.db.commit()
        for pack in packs:
            self.db.refresh(pack)
        return packs

    def list_project_context_packs(
        self, project_id: UUID, role: str | None = None
    ) -> list[ContextPack]:
        ProjectService(self.db, self.current_user).get_project(project_id)
        statement = select(ContextPack).where(ContextPack.project_id == project_id)
        if role is not None:
            statement = statement.where(ContextPack.role == role)
        return list(self.db.scalars(statement.order_by(ContextPack.created_at.desc())))

    def get_context_pack(self, context_pack_id: UUID) -> ContextPack:
        pack = self.db.get(ContextPack, context_pack_id)
        if pack is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Context pack not found.",
            )
        ProjectService(self.db, self.current_user).get_project(pack.project_id)
        return pack

    def export_context_pack(self, context_pack_id: UUID) -> ContextPackExportResponse:
        pack = self.get_context_pack(context_pack_id)
        filename = f"{pack.role}_context_pack.md"
        return ContextPackExportResponse(
            filename=filename,
            content_type="text/markdown",
            content=pack.prompt_text,
        )

    def get_project_roles(self, project_id: UUID) -> set[str]:
        return set(
            self.db.scalars(select(ContextPack.role).where(ContextPack.project_id == project_id))
        )

    def _record_failed_run(self, project_id: UUID, error_message: str) -> None:
        self.db.rollback()
        self.db.add(
            GenerationRun(
                project_id=project_id,
                run_type="generate_context_packs",
                status="failed",
                input_snapshot={"project_id": str(project_id)},
                output_snapshot=None,
                error_message=error_message,
                completed_at=datetime.now(UTC),
            )
        )
        self.db.commit()
