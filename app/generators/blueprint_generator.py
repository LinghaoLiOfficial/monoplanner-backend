from app.models.project import Project
from app.models.requirement import Requirement


def build_mock_blueprint_content(project: Project, requirement: Requirement) -> dict[str, object]:
    one_liner = requirement.raw_text.strip().replace("\n", " ")[:120]
    if not one_liner:
        one_liner = "基于用户需求生成的项目蓝图草案。"

    return {
        "project": {
            "name": project.name,
            "one_liner": one_liner,
            "business_goal": "将自然语言业务需求转化为适合 vibe coding 工具使用的结构化上下文包。",
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
