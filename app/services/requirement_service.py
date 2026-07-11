from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.generation_run import GenerationRun
from app.models.requirement import Requirement
from app.schemas.generation_run import BusinessStoryGenerationStatus
from app.schemas.requirement import RequirementCreate, RequirementRead
from app.services.project_service import ProjectService

BUSINESS_STORY_RUN_TYPE = "generate_business_requirement_stories"


class RequirementService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_requirement(self, project_id: UUID, payload: RequirementCreate) -> RequirementRead:
        ProjectService(self.db).get_project(project_id)
        requirement = Requirement(project_id=project_id, **payload.model_dump())
        self.db.add(requirement)
        self.db.commit()
        self.db.refresh(requirement)
        return self._to_read(requirement, None)

    def list_project_requirements(self, project_id: UUID) -> list[RequirementRead]:
        ProjectService(self.db).get_project(project_id)
        requirements = list(
            self.db.scalars(
                select(Requirement)
                .where(Requirement.project_id == project_id)
                .order_by(Requirement.created_at.desc())
            )
        )
        statuses = self._latest_business_story_statuses([item.id for item in requirements])
        return [self._to_read(item, statuses.get(item.id)) for item in requirements]

    def get_latest_requirement(self, project_id: UUID) -> Requirement | None:
        return self.db.scalar(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.created_at.desc())
            .limit(1)
        )

    def get_business_story_generation_status(
        self, requirement_id: UUID
    ) -> BusinessStoryGenerationStatus | None:
        run = self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.requirement_id == requirement_id,
                GenerationRun.run_type == BUSINESS_STORY_RUN_TYPE,
            )
            .order_by(GenerationRun.created_at.desc())
            .limit(1)
        )
        if run is None:
            return None
        return _run_to_business_story_status(run)

    def _latest_business_story_statuses(
        self, requirement_ids: list[UUID]
    ) -> dict[UUID, BusinessStoryGenerationStatus]:
        if not requirement_ids:
            return {}
        runs = list(
            self.db.scalars(
                select(GenerationRun)
                .where(
                    GenerationRun.requirement_id.in_(requirement_ids),
                    GenerationRun.run_type == BUSINESS_STORY_RUN_TYPE,
                )
                .order_by(GenerationRun.requirement_id, GenerationRun.created_at.desc())
            )
        )
        statuses: dict[UUID, BusinessStoryGenerationStatus] = {}
        for run in runs:
            if run.requirement_id is not None and run.requirement_id not in statuses:
                statuses[run.requirement_id] = _run_to_business_story_status(run)
        return statuses

    def _to_read(
        self,
        requirement: Requirement,
        status: BusinessStoryGenerationStatus | None,
    ) -> RequirementRead:
        return RequirementRead.model_validate(requirement).model_copy(
            update={"business_story_generation": status}
        )


def _run_to_business_story_status(run: GenerationRun) -> BusinessStoryGenerationStatus:
    status = "succeeded" if run.status == "completed" else run.status
    return BusinessStoryGenerationStatus(
        run_id=run.id,
        status=status,
        progress=run.progress,
        message=run.message,
        error_message=run.error_message,
        updated_at=run.updated_at,
    )
