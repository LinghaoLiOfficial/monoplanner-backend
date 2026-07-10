from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.business_requirement_story import BusinessRequirementStory
from app.schemas.business_requirement_story import BusinessRequirementStoryUpdate
from app.services.project_service import ProjectService

PRIORITY_ORDER = {
    "p1_must": 1,
    "p2_should": 2,
    "p3_could": 3,
    "p4_wont": 4,
}


class BusinessRequirementStoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_project_stories(
        self,
        project_id: UUID,
        priority: str | None = None,
        status_filter: str | None = None,
        q: str | None = None,
    ) -> list[BusinessRequirementStory]:
        ProjectService(self.db).get_project(project_id)
        statement = select(BusinessRequirementStory).where(
            BusinessRequirementStory.project_id == project_id
        )
        if priority:
            statement = statement.where(BusinessRequirementStory.priority == priority)
        if status_filter:
            statement = statement.where(BusinessRequirementStory.status == status_filter)
        keyword = q.strip() if q is not None else ""
        if keyword:
            statement = statement.where(
                or_(
                    BusinessRequirementStory.title.ilike(f"%{keyword}%"),
                    BusinessRequirementStory.user_story.ilike(f"%{keyword}%"),
                )
            )
        stories = list(
            self.db.scalars(
                statement.order_by(
                    BusinessRequirementStory.sort_order.asc(),
                    BusinessRequirementStory.created_at.asc(),
                )
            )
        )
        return sorted(stories, key=lambda story: PRIORITY_ORDER.get(story.priority, 99))

    def get_story(self, story_id: UUID) -> BusinessRequirementStory:
        story = self.db.get(BusinessRequirementStory, story_id)
        if story is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business requirement story not found.",
            )
        return story

    def update_story(
        self, story_id: UUID, payload: BusinessRequirementStoryUpdate
    ) -> BusinessRequirementStory:
        story = self.get_story(story_id)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(story, field, value)
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return story

    def delete_existing_for_requirement(
        self, project_id: UUID, requirement_id: UUID | None
    ) -> None:
        statement = select(BusinessRequirementStory).where(
            BusinessRequirementStory.project_id == project_id,
            BusinessRequirementStory.requirement_id == requirement_id,
        )
        for story in self.db.scalars(statement):
            self.db.delete(story)

    def list_for_blueprint_context(self, project_id: UUID) -> list[BusinessRequirementStory]:
        return self.list_project_stories(project_id)
