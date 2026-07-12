from __future__ import annotations

from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK, normalize_stack

SYSTEM_PROMPT = (
    "你是一个资深产品架构师、全栈架构师和敏捷需求分析师。你的任务是将用户需求和业务需求故事"
    "整理成结构化项目蓝图。蓝图不是代码，而是后续 API 契约、数据库模型、前端指令集合、"
    "后端指令集合的上游依据。"
)


def build_blueprint_generation_payload(
    project: Any,
    requirement: Any,
    business_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    frontend_stack = normalize_stack(
        getattr(project, "target_frontend_stack", None),
        DEFAULT_FRONTEND_STACK,
    )
    backend_stack = normalize_stack(
        getattr(project, "target_backend_stack", None),
        DEFAULT_BACKEND_STACK,
    )
    return {
        "项目名称": project.name,
        "项目描述": project.description or "",
        "目标前端技术栈": frontend_stack,
        "目标后端技术栈": backend_stack,
        "最新用户需求": {
            "id": str(requirement.id),
            "raw_text": requirement.raw_text,
            "language": requirement.language,
            "source_type": requirement.source_type,
        },
        "业务需求故事列表": business_stories,
        "目标 JSON schema": {
            "project": {
                "name": "string",
                "one_liner": "string",
                "target_users": ["string"],
                "business_goal": "string",
                "tech_stack": {"frontend": "string", "backend": "string"},
            },
            "product_goals": [{"goal": "string", "priority": "must_have"}],
            "user_roles": [
                {"name": "string", "description": "string", "permissions": ["string"]}
            ],
            "core_modules": [
                {"name": "string", "description": "string", "features": ["string"]}
            ],
            "domain_entities": [
                {
                    "name": "string",
                    "description": "string",
                    "fields": [
                        {
                            "name": "string",
                            "type": "string",
                            "required": True,
                            "description": "string",
                        }
                    ],
                    "relationships": ["string"],
                }
            ],
            "pages": [
                {
                    "path": "string",
                    "name": "string",
                    "purpose": "string",
                    "components": ["string"],
                    "data_dependencies": ["string"],
                }
            ],
            "api_needs": [
                {
                    "resource": "string",
                    "operations": ["create", "read", "update", "delete", "list"],
                    "consumers": ["string"],
                }
            ],
            "business_requirement_stories": [
                {
                    "title": "string",
                    "priority": "p1_must",
                    "status": "string",
                    "user_story": "string",
                }
            ],
            "non_functional_requirements": {
                "auth": "string",
                "performance": "string",
                "security": "string",
                "observability": "string",
            },
            "assumptions": ["string"],
            "open_questions": ["string"],
        },
        "生成规则": [
            "必须返回严格 JSON",
            "不要返回 Markdown",
            "不要返回解释文字",
            "pages 必须来自真实业务流程",
            "api_needs 必须能支撑 pages",
            "domain_entities 必须能支撑业务需求故事",
            "不要生成过度复杂的模块",
            "P4 Won't 的故事可以进入 open_questions 或 assumptions，不要作为 MVP 必做功能",
        ],
        "禁止事项": [
            "不要生成代码",
            "不要生成 OpenAPI 文档",
            "不要编造与需求无关的模块",
            "不要输出 JSON 之外的任何字符",
        ],
    }
