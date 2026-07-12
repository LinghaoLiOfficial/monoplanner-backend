from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack
from app.llm.json_client import generate_json
from app.models.project import Project
from app.models.requirement import Requirement
from app.prompts.blueprint_generator import SYSTEM_PROMPT, build_blueprint_generation_payload


class BlueprintValidationError(ValueError):
    """Raised when LLM blueprint output does not match the expected shape."""


def build_project_blueprint_content(
    project: Project,
    requirement: Requirement,
    business_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = build_blueprint_generation_payload(project, requirement, business_stories)
    content = generate_json(SYSTEM_PROMPT, payload)
    return validate_blueprint_content(content, project, business_stories)


def validate_blueprint_content(
    content: dict[str, Any],
    project: Project,
    business_stories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    required_lists = (
        "product_goals",
        "user_roles",
        "core_modules",
        "domain_entities",
        "pages",
        "api_needs",
    )
    project_content = content.get("project")
    if not isinstance(project_content, dict):
        raise BlueprintValidationError("Blueprint content must contain project object.")
    for field in required_lists:
        if not isinstance(content.get(field), list):
            raise BlueprintValidationError(f"Blueprint content must contain {field} list.")

    tech_stack = project_content.get("tech_stack")
    if not isinstance(tech_stack, dict):
        legacy_stack = content.get("tech_stack")
        tech_stack = legacy_stack if isinstance(legacy_stack, dict) else {}
    project_content["name"] = _string_or_default(project_content.get("name"), project.name)
    project_content["one_liner"] = _string_or_default(
        project_content.get("one_liner"),
        project.description or "项目蓝图",
    )
    project_content["target_users"] = _string_list(project_content.get("target_users"))
    project_content["business_goal"] = _string_or_default(
        project_content.get("business_goal"),
        "基于用户需求交付可执行的全栈产品方案。",
    )
    frontend_stack = normalize_stack(
        getattr(project, "target_frontend_stack", None),
        DEFAULT_FRONTEND_STACK,
    )
    backend_stack = normalize_stack(
        getattr(project, "target_backend_stack", None),
        DEFAULT_BACKEND_STACK,
    )
    project_content["tech_stack"] = {
        "frontend": frontend_stack,
        "backend": backend_stack,
    }
    content["project"] = project_content
    content["tech_stack"] = project_content["tech_stack"]

    content["product_goals"] = [
        _normalize_product_goal(item) for item in content["product_goals"] if isinstance(item, dict)
    ]
    content["user_roles"] = [
        _normalize_user_role(item) for item in content["user_roles"] if isinstance(item, dict)
    ]
    content["core_modules"] = [
        _normalize_core_module(item) for item in content["core_modules"] if isinstance(item, dict)
    ]
    content["domain_entities"] = [
        _normalize_domain_entity(item)
        for item in content["domain_entities"]
        if isinstance(item, dict)
    ]
    content["pages"] = [
        _normalize_page(item) for item in content["pages"] if isinstance(item, dict)
    ]
    content["api_needs"] = [
        _normalize_api_need(item) for item in content["api_needs"] if isinstance(item, dict)
    ]
    if not content["pages"]:
        raise BlueprintValidationError("Blueprint pages must not be empty.")
    if not content["api_needs"]:
        raise BlueprintValidationError("Blueprint api_needs must not be empty.")
    if not content["domain_entities"]:
        raise BlueprintValidationError("Blueprint domain_entities must not be empty.")

    story_context = business_stories or []
    content["business_requirement_stories"] = _normalize_story_refs(
        content.get("business_requirement_stories"),
        story_context,
    )
    nfr = content.get("non_functional_requirements")
    content["non_functional_requirements"] = nfr if isinstance(nfr, dict) else {}
    content["assumptions"] = _string_list(content.get("assumptions"))
    content["open_questions"] = _string_list(content.get("open_questions"))
    return content


def build_mock_blueprint_content(project: Project, requirement: Requirement) -> dict[str, Any]:
    return build_deterministic_blueprint_content(project, requirement)


def build_deterministic_blueprint_content(
    project: Project, requirement: Requirement
) -> dict[str, Any]:
    raw_requirement = getattr(requirement, "raw_text", "") or ""
    frontend_stack = normalize_stack(
        getattr(project, "target_frontend_stack", None),
        DEFAULT_FRONTEND_STACK,
    )
    backend_stack = normalize_stack(
        getattr(project, "target_backend_stack", None),
        DEFAULT_BACKEND_STACK,
    )

    one_liner = raw_requirement.strip().replace("\n", " ")[:120]
    if not one_liner:
        one_liner = "基于用户需求生成的项目蓝图草案。"

    return {
        "project": {
            "name": project.name,
            "one_liner": one_liner,
            "business_goal": "将自然语言业务需求转化为适合 vibe coding 工具使用的结构化上下文包。",
        },
        "tech_stack": {
            "frontend": frontend_stack,
            "backend": backend_stack,
        },
        "product_goals": [{"goal": "输入业务需求并生成结构化项目蓝图", "priority": "must_have"}],
        "user_roles": [
            {
                "name": "产品型开发者",
                "description": "输入需求并审查生成结果",
                "permissions": ["create_project", "submit_requirement", "review_blueprint"],
            }
        ],
        "core_modules": [
            {
                "name": "需求输入",
                "description": "接收用户自然语言业务需求",
                "features": ["创建项目", "提交需求", "查看需求历史"],
            },
            {
                "name": "项目蓝图",
                "description": "生成中间结构化项目蓝图",
                "features": ["生成蓝图草案", "查看蓝图 JSON"],
            },
        ],
        "domain_entities": [
            {
                "name": "Project",
                "description": "用户创建的全栈项目",
                "fields": ["id", "name", "description", "status"],
            },
            {
                "name": "Requirement",
                "description": "用户输入的原始业务需求",
                "fields": ["id", "project_id", "raw_text", "language"],
            },
        ],
        "pages": [
            {"path": "/projects", "name": "项目列表", "purpose": "查看和进入项目"},
            {
                "path": "/projects/[projectId]",
                "name": "项目工作台",
                "purpose": "查看项目状态和进入各个生成模块",
            },
        ],
        "api_needs": [
            {"resource": "projects", "operations": ["create", "read", "update", "delete", "list"]},
            {"resource": "requirements", "operations": ["create", "list"]},
            {"resource": "blueprints", "operations": ["generate", "read", "list"]},
        ],
        "assumptions": ["第一批版本不接入真实 LLM", "第一批版本不包含用户认证"],
        "open_questions": ["后续是否需要多用户协作？", "后续生成器使用哪个 LLM provider？"],
    }


def _normalize_product_goal(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal": _require_string(item.get("goal"), "product_goals.goal"),
        "priority": _string_or_default(item.get("priority"), "must_have"),
    }


def _normalize_user_role(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _require_string(item.get("name"), "user_roles.name"),
        "description": _string_or_default(item.get("description"), ""),
        "permissions": _string_list(item.get("permissions")),
    }


def _normalize_core_module(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _require_string(item.get("name"), "core_modules.name"),
        "description": _string_or_default(item.get("description"), ""),
        "features": _string_list(item.get("features")),
    }


def _normalize_domain_entity(item: dict[str, Any]) -> dict[str, Any]:
    fields = item.get("fields")
    normalized_fields: list[dict[str, Any]] = []
    if isinstance(fields, list):
        for field in fields:
            if isinstance(field, str):
                normalized_fields.append(
                    {
                        "name": field.strip(),
                        "type": "string",
                        "required": False,
                        "description": "",
                    }
                )
            elif isinstance(field, dict):
                normalized_fields.append(
                    {
                        "name": _require_string(field.get("name"), "domain_entities.fields.name"),
                        "type": _string_or_default(field.get("type"), "string"),
                        "required": bool(field.get("required", False)),
                        "description": _string_or_default(field.get("description"), ""),
                    }
                )
    return {
        "name": _require_string(item.get("name"), "domain_entities.name"),
        "description": _string_or_default(item.get("description"), ""),
        "fields": normalized_fields,
        "relationships": _string_list(item.get("relationships")),
    }


def _normalize_page(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _require_string(item.get("path"), "pages.path"),
        "name": _require_string(item.get("name"), "pages.name"),
        "purpose": _require_string(item.get("purpose"), "pages.purpose"),
        "components": _string_list(item.get("components")),
        "data_dependencies": _string_list(item.get("data_dependencies")),
    }


def _normalize_api_need(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource": _require_string(item.get("resource"), "api_needs.resource"),
        "operations": _string_list(item.get("operations")),
        "consumers": _string_list(item.get("consumers")),
    }


def _normalize_story_refs(
    raw_value: Any,
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source = raw_value if isinstance(raw_value, list) and raw_value else fallback
    normalized = []
    for item in source:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        user_story = item.get("user_story")
        if not isinstance(title, str) or not isinstance(user_story, str):
            continue
        normalized.append(
            {
                "title": title.strip(),
                "priority": _string_or_default(item.get("priority"), "p3_could"),
                "status": _string_or_default(item.get("status"), "draft"),
                "user_story": user_story.strip(),
            }
        )
    return normalized


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BlueprintValidationError(f"Blueprint {field_name} is required.")
    return value.strip()


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
