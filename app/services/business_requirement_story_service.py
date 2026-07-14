from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.business_requirement_story import BusinessRequirementStory
from app.models.user import User
from app.schemas.business_requirement_story import BusinessRequirementStoryUpdate
from app.services.project_service import ProjectService

PRIORITY_ORDER = {
    "p1_must": 1,
    "p2_should": 2,
    "p3_could": 3,
    "p4_wont": 4,
}


class BusinessRequirementStoryService:
    def __init__(self, db: Session, current_user: User | None = None) -> None:
        self.db = db
        self.current_user = current_user

    def list_project_stories(
        self,
        project_id: UUID,
        priority: str | None = None,
        status_filter: str | None = None,
        q: str | None = None,
    ) -> list[BusinessRequirementStory]:
        ProjectService(self.db, self.current_user).get_project(project_id)
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
        ProjectService(self.db, self.current_user).get_project(story.project_id)
        return story

    def update_story(
        self, story_id: UUID, payload: BusinessRequirementStoryUpdate
    ) -> BusinessRequirementStory:
        story = self.get_story(story_id)
        updates = payload.model_dump(exclude_unset=True)
        if "user_story" in updates:
            updates["user_story"] = _normalize_user_story(updates["user_story"])
        if "business_scope" in updates:
            updates["business_scope"] = _normalize_business_scope(updates["business_scope"])
        if "data_rules" in updates:
            updates["data_rules"] = _normalize_data_rules(updates["data_rules"])
        if "acceptance_criteria" in updates:
            updates["acceptance_criteria"] = _normalize_acceptance_criteria(
                updates["acceptance_criteria"]
            )
        if "affected_layers" in updates:
            updates["affected_layers"] = _normalize_string_list_or_empty(updates["affected_layers"])
        if "depends_on" in updates:
            updates["depends_on"] = _normalize_json_list(updates["depends_on"], "依赖格式不正确。")
        if "source_requirement_ids" in updates:
            updates["source_requirement_ids"] = _normalize_string_list_or_empty(
                updates["source_requirement_ids"]
            )
        for field, value in updates.items():
            setattr(story, field, value)
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return story

    def select_story(self, story_id: UUID) -> BusinessRequirementStory:
        story = self.get_story(story_id)
        story.status = "selected"
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return story

    def delete_story(self, story_id: UUID) -> None:
        story = self.get_story(story_id)
        try:
            self.db.delete(story)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

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


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _normalize_user_story(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _bad_request("用户故事不能为空。")
    return value.strip()


def _normalize_business_scope(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        raise _bad_request("业务范围格式不正确。")
    try:
        return {
            "included": _normalize_string_list(value.get("included", [])),
            "excluded": _normalize_string_list(value.get("excluded", [])),
        }
    except ValueError as exc:
        raise _bad_request("业务范围格式不正确。") from exc


def _normalize_data_rules(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise _bad_request("数据规则格式不正确。")

    normalized_rules: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise _bad_request("数据规则格式不正确。")

        rule = item.get("rule")
        if not isinstance(rule, str):
            raise _bad_request("数据规则格式不正确。")
        rule_text = rule.strip()
        if not rule_text:
            continue

        normalized_item = {"rule": rule_text}
        if "field" in item and item["field"] is not None:
            field = item["field"]
            if not isinstance(field, str):
                raise _bad_request("数据规则格式不正确。")
            field_text = field.strip()
            if field_text:
                normalized_item["field"] = field_text
        normalized_rules.append(normalized_item)

    return normalized_rules


def _normalize_acceptance_criteria(value: Any) -> list[str]:
    try:
        return _normalize_string_list(value)
    except ValueError as exc:
        raise _bad_request("验收标准格式不正确。") from exc


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("value must be a list")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("items must be strings")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_string_list_or_empty(value: Any) -> list[str]:
    try:
        return _normalize_string_list(value)
    except ValueError as exc:
        raise _bad_request("列表格式不正确。") from exc


def _normalize_json_list(value: Any, detail: str) -> list[Any]:
    if not isinstance(value, list):
        raise _bad_request(detail)
    return value
