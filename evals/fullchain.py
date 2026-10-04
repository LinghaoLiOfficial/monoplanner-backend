"""Runs real application services in a new schema in an explicit evaluation database."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.generation_run import GenerationRun
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.user import User
from app.prompts.templates.business_story_decomposer.output_schema import (
    BusinessStoryDecompositionOutput,
)
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.schemas.business_requirement_story import GenerateBusinessRequirementStoriesRequest
from app.services.business_story_generation_service import BusinessStoryGenerationService
from app.services.change_set_generation_service import (
    LAYER_GENERATION_ORDER,
    ChangeSetGenerationService,
)
from app.services.design_asset_orchestration_service import (
    DesignAssetOrchestrationService,
    _design_asset_response_model,
    _design_asset_task_key,
)
from app.services.orchestration_context import ASSET_MODELS_BY_LAYER, latest_assets_snapshot
from app.services.prompt_pack_generation_service import PromptPackGenerationService
from evals.dataset import Chain, Step
from evals.storage import write_new
from evals.transport import RecordedGenerator

RESPONSE_MODELS = {
    "business_story_decomposer": BusinessStoryDecompositionOutput,
    "change_set": ChangeSetOutput,
    "prompt_pack": PromptPackOutput,
    **{
        _design_asset_task_key(layer): _design_asset_response_model(layer)
        for layer in LAYER_GENERATION_ORDER
    },
}


def safe_database(url: str) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_eval"):
        raise ValueError(
            "EVAL_DATABASE_URL must explicitly name a PostgreSQL database ending _eval"
        )
    from app.core.config import settings

    configured = make_url(settings.database_url)

    def identity(u):
        return u.host, u.port or 5432, u.database

    if identity(parsed) == identity(configured):
        raise ValueError("Evaluation database must differ from the application database")


class FullChain:
    def __init__(self, database_url: str, chain: Chain, audit_directory: Path):
        safe_database(database_url)
        self.schema = f"monoplanner_eval_{uuid4().hex}"
        parsed = make_url(database_url)
        if parsed.drivername == "postgresql":
            parsed = parsed.set(drivername="postgresql+psycopg")
        self.engine = create_engine(parsed, pool_pre_ping=True)
        self.connection = None
        self.db: Session | None = None
        try:
            self.connection = self.engine.connect()
            self.connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            self.connection.execute(text(f'SET search_path TO "{self.schema}"'))
            self.connection.commit()
            Base.metadata.create_all(self.connection)
            self.connection.commit()
            self.db = Session(self.connection, expire_on_commit=False)
            write_new(
                audit_directory / "database.json",
                {
                    "schema": self.schema,
                    "cleanup": "retained; no automatic DROP",
                    "chain_id": chain.chain_id,
                },
            )
            user = User(
                email=f"{uuid4().hex}@example.invalid",
                username=uuid4().hex,
                password_hash="evaluation-account-login-disabled",
                is_active=False,
                avatar_seed="eval",
                avatar_bg_color="#000000",
            )
            self.db.add(user)
            self.db.flush()
            config = chain.steps[0].pack_input.project_config
            fields = {
                k: config[k]
                for k in (
                    "target_frontend_stack",
                    "target_backend_stack",
                    "global_constraints",
                    "coding_preferences",
                    "prompt_preferences",
                    "llm_prompt_language",
                    "target_frontend_stack_items",
                    "target_backend_stack_items",
                )
                if k in config
            }
            self.project = Project(owner_user_id=user.id, name=f"eval-{uuid4().hex}", **fields)
            self.db.add(self.project)
            self.db.flush()
            for layer, snapshot in chain.initial_assets.items():
                if layer not in ASSET_MODELS_BY_LAYER:
                    raise ValueError(f"Unsupported initial asset layer: {layer}")
                self.db.add(
                    ASSET_MODELS_BY_LAYER[layer](
                        project_id=self.project.id,
                        version=snapshot.get("version", 1),
                        title=snapshot.get("title", layer),
                        summary=snapshot.get("summary", ""),
                        content=snapshot["content"],
                        diff_from_previous=snapshot.get("diff_from_previous", {}),
                    )
                )
            self.db.commit()
        except BaseException:
            self.close()
            raise

    def step(self, step: Step, generator: RecordedGenerator, directory: Path) -> dict[str, Any]:
        assert self.db is not None
        db = self.db
        previous = latest_assets_snapshot(db, self.project.id)
        write_new(directory / "state-before.json", previous)
        requirement = Requirement(project_id=self.project.id, raw_text=step.raw_requirement)
        db.add(requirement)
        db.commit()
        stories = BusinessStoryGenerationService(
            db, json_generator=generator
        ).generate_business_stories(
            self.project.id,
            GenerateBusinessRequirementStoriesRequest(requirement_id=requirement.id),
        )
        active = [story for story in stories if story.priority != "p4_wont"]
        if len(active) != 1:
            raise ValueError(
                "Expected one executable vertical-slice story; no silent story selection"
            )
        story = active[0]
        batch = uuid4()
        changes = []
        for layer in LAYER_GENERATION_ORDER:
            if layer not in story.affected_layers:
                continue
            run = GenerationRun(
                project_id=self.project.id,
                run_type="generate_change_set_asset",
                status="queued",
                asset_layer=layer,
                queue_payload={"story_id": str(story.id), "batch_id": str(batch)},
            )
            db.add(run)
            db.commit()
            changes.append(
                ChangeSetGenerationService(
                    db, llm_client_factory=generator.client_factory("change_set")
                ).execute_asset_run(run)
            )
        if not changes:
            raise ValueError(
                "No executable change sets; recorded as abstention/failure, not a zero"
            )
        for change in changes:
            run = GenerationRun(
                project_id=self.project.id,
                run_type="generate_design_asset",
                status="queued",
                asset_layer=change.layer,
                queue_payload={"change_set_id": str(change.id), "batch_id": str(batch)},
            )
            db.add(run)
            db.commit()
            DesignAssetOrchestrationService(
                db,
                llm_client_factory=generator.client_factory(_design_asset_task_key(change.layer)),
            ).execute_asset_run(run)
        new = latest_assets_snapshot(db, self.project.id)
        write_new(directory / "state-after.json", new)
        run = GenerationRun(
            project_id=self.project.id, run_type="generate_prompt_pack", status="queued"
        )
        db.add(run)
        db.commit()
        packs = PromptPackGenerationService(
            db, llm_client_factory=generator.client_factory("prompt_pack")
        ).generate_for_change_set_batch(
            run,
            changes[0],
            change_sets=changes,
            old_versions=previous,
            new_versions=new,
        )
        for change in changes:
            change.status = "applied"
            change.is_current = False
        story.status = "applied"
        db.commit()
        return packs[0].content

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
        if self.connection is not None:
            self.connection.close()
        self.engine.dispose()
