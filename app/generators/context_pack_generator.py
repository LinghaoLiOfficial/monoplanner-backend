from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
from app.core.llm_prompt_language import DEFAULT_LLM_PROMPT_LANGUAGE, normalize_llm_prompt_language
from app.core.tech_stack import normalize_tech_stack_items, tech_stack_items_to_text
from app.llm.json_client import LLMJsonGenerationError, generate_json, should_use_real_llm
from app.prompts.renderer import render_prompt_template
from app.prompts.templates.context_pack.output_schema import ContextPackOutput


def _project_summary(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    project = blueprint_content.get("project")
    return project if isinstance(project, dict) else {}


def _stack_summary(blueprint_content: dict[str, Any], side: str, default: str) -> str:
    project = _project_summary(blueprint_content)
    tech_stack = project.get("tech_stack")
    if isinstance(tech_stack, dict):
        items = tech_stack.get(side)
        if isinstance(items, list):
            summary = tech_stack_items_to_text(
                normalize_tech_stack_items(items, infer_missing_type=True)
            )
            if summary:
                return summary
    return default


def _list_from_blueprint(blueprint_content: dict[str, Any], key: str) -> list[Any]:
    value = blueprint_content.get(key)
    return value if isinstance(value, list) else []


def _markdown_section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}\n"


def _format_json_like(value: Any) -> str:
    if value in (None, {}, []):
        return "Missing or not generated yet."
    return f"```json\n{value}\n```"


def _frontend_prompt(content: dict[str, Any]) -> str:
    api_contract = content["included_context"].get("relevant_api_contract")
    pages = content["included_context"].get("relevant_pages") or []
    return "\n".join(
        [
            "# Frontend Engineer Context Pack",
            _markdown_section("Role", "You are a senior frontend engineer."),
            _markdown_section(
                "Goal",
                "Implement frontend features based on the provided blueprint and API contract.",
            ),
            _markdown_section("Given Context", _format_json_like(content["included_context"])),
            _markdown_section("Pages to Implement", _format_json_like(pages)),
            _markdown_section("API Contract Subset", _format_json_like(api_contract)),
            _markdown_section(
                "UI Requirements",
                "Use typed React components, cover loading, error, empty, and success states.",
            ),
            _markdown_section(
                "State Handling", "Keep state local unless a clear shared state need exists."
            ),
            _markdown_section(
                "Expected Output", "\n".join(f"- {item}" for item in content["expected_output"])
            ),
            _markdown_section(
                "Constraints", "\n".join(f"- {item}" for item in content["constraints"])
            ),
            _markdown_section("Do Not Do", "\n".join(f"- {item}" for item in content["do_not_do"])),
        ]
    )


def _frontend_prompt_zh(content: dict[str, Any]) -> str:
    api_contract = content["included_context"].get("relevant_api_contract")
    pages = content["included_context"].get("relevant_pages") or []
    return "\n".join(
        [
            "# 前端工程师 Context Pack",
            _markdown_section("角色", "你是一名资深前端工程师。"),
            _markdown_section("目标", "基于提供的项目蓝图和 API 契约实现前端功能。"),
            _markdown_section("上下文", _format_json_like(content["included_context"])),
            _markdown_section("待实现页面", _format_json_like(pages)),
            _markdown_section("API 契约子集", _format_json_like(api_contract)),
            _markdown_section(
                "UI 要求",
                "使用类型化 React 组件，覆盖加载、错误、空状态和成功状态。",
            ),
            _markdown_section("状态处理", "优先使用局部状态，只有明确共享需求时才引入共享状态。"),
            _markdown_section(
                "期望输出",
                "\n".join(f"- {item}" for item in content["expected_output"]),
            ),
            _markdown_section("约束", "\n".join(f"- {item}" for item in content["constraints"])),
            _markdown_section("不要做", "\n".join(f"- {item}" for item in content["do_not_do"])),
        ]
    )


def _backend_prompt(content: dict[str, Any]) -> str:
    api_contract = content["included_context"].get("relevant_api_contract")
    db_model = content["included_context"].get("relevant_db_model")
    entities = content["included_context"].get("relevant_entities") or []
    return "\n".join(
        [
            "# Backend Engineer Context Pack",
            _markdown_section("Role", "You are a senior Python backend engineer."),
            _markdown_section(
                "Goal",
                "Implement backend features based on the blueprint, API contract, "
                "and DB model draft.",
            ),
            _markdown_section("Given Context", _format_json_like(content["included_context"])),
            _markdown_section("Domain Entities", _format_json_like(entities)),
            _markdown_section("API Endpoints", _format_json_like(api_contract)),
            _markdown_section("Database Model Draft", _format_json_like(db_model)),
            _markdown_section(
                "Service Layer Requirements",
                "Use FastAPI routes, Pydantic schemas, SQLAlchemy models, service classes, "
                "and Alembic migrations. Do not put business logic in routes.",
            ),
            _markdown_section(
                "Expected Output", "\n".join(f"- {item}" for item in content["expected_output"])
            ),
            _markdown_section(
                "Constraints", "\n".join(f"- {item}" for item in content["constraints"])
            ),
            _markdown_section("Do Not Do", "\n".join(f"- {item}" for item in content["do_not_do"])),
        ]
    )


def _backend_prompt_zh(content: dict[str, Any]) -> str:
    api_contract = content["included_context"].get("relevant_api_contract")
    db_model = content["included_context"].get("relevant_db_model")
    entities = content["included_context"].get("relevant_entities") or []
    return "\n".join(
        [
            "# 后端工程师 Context Pack",
            _markdown_section("角色", "你是一名资深 Python 后端工程师。"),
            _markdown_section(
                "目标",
                "基于项目蓝图、API 契约和数据库模型草案实现后端功能。",
            ),
            _markdown_section("上下文", _format_json_like(content["included_context"])),
            _markdown_section("领域实体", _format_json_like(entities)),
            _markdown_section("API 端点", _format_json_like(api_contract)),
            _markdown_section("数据库模型草案", _format_json_like(db_model)),
            _markdown_section(
                "服务层要求",
                "使用 FastAPI 路由、Pydantic schema、SQLAlchemy model、service class "
                "和 Alembic migration。不要把业务逻辑放在路由中。",
            ),
            _markdown_section(
                "期望输出",
                "\n".join(f"- {item}" for item in content["expected_output"]),
            ),
            _markdown_section("约束", "\n".join(f"- {item}" for item in content["constraints"])),
            _markdown_section("不要做", "\n".join(f"- {item}" for item in content["do_not_do"])),
        ]
    )


def build_context_pack_payloads(
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
    *,
    language: str | None = DEFAULT_LLM_PROMPT_LANGUAGE,
) -> list[dict[str, Any]]:
    normalized_language = normalize_llm_prompt_language(language)
    if should_use_real_llm():
        return build_llm_context_pack_payloads(
            blueprint_content,
            api_contract_content,
            db_model_content,
            language=normalized_language,
        )
    return _build_rule_based_context_pack_payloads(
        blueprint_content,
        api_contract_content,
        db_model_content,
        language=normalized_language,
    )


def build_llm_context_pack_payloads(
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
    *,
    language: str | None = DEFAULT_LLM_PROMPT_LANGUAGE,
) -> list[dict[str, Any]]:
    prompt = render_prompt_template(
        "context_pack",
        {
            "blueprint": blueprint_content,
            "api_contract": api_contract_content,
            "db_model": db_model_content,
            "frontend_stack": _stack_summary(blueprint_content, "frontend", DEFAULT_FRONTEND_STACK),
            "backend_stack": _stack_summary(blueprint_content, "backend", DEFAULT_BACKEND_STACK),
        },
        language=language,
    )
    response = generate_json(
        system_prompt=prompt.system,
        user_payload=prompt.user,
        response_model=ContextPackOutput,
    )
    packs = response.get("packs")
    if not isinstance(packs, list) or not packs:
        raise LLMJsonGenerationError(
            "LLM context pack output must contain a non-empty packs array."
        )
    normalized: list[dict[str, Any]] = []
    for pack in packs:
        if not isinstance(pack, dict):
            raise LLMJsonGenerationError("Each context pack must be a JSON object.")
        for key in ("role", "title", "summary", "content", "prompt_text"):
            if key not in pack:
                raise LLMJsonGenerationError(f"Context pack is missing required key: {key}.")
        normalized.append(pack)
    return normalized


def _build_rule_based_context_pack_payloads(
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
    *,
    language: str | None = DEFAULT_LLM_PROMPT_LANGUAGE,
) -> list[dict[str, Any]]:
    normalized_language = normalize_llm_prompt_language(language)
    api_context = api_contract_content or {
        "missing": (
            "ApiContractDraft 尚未生成。"
            if normalized_language == "zh-CN"
            else "ApiContractDraft has not been generated yet."
        )
    }
    db_context = db_model_content or {
        "missing": (
            "DbModelDraft 尚未生成。"
            if normalized_language == "zh-CN"
            else "DbModelDraft has not been generated yet."
        )
    }

    if normalized_language == "zh-CN":
        frontend_goal = "基于提供的项目蓝图和 API 契约实现前端功能。"
        backend_goal = "基于项目蓝图和生成的草案实现后端功能。"
        frontend_expected = [
            "匹配 ProjectBlueprint.pages 的 Next.js 页面/组件。",
            "从 ApiContractDraft 派生 TypeScript API 类型。",
            "加载、错误、空状态和成功状态。",
        ]
        backend_expected = [
            "匹配 ApiContractDraft 的 FastAPI 路由。",
            "匹配 DbModelDraft 的 Pydantic schema 和 SQLAlchemy model。",
            "Service 层业务逻辑和 Alembic migration。",
        ]
        frontend_constraints = [
            "只实现前端代码。",
            "不要修改后端代码。",
            "不要编造 API；以 ApiContractDraft 为事实来源。",
            "使用 TypeScript 类型。",
            "不要引入不必要的大型依赖。",
        ]
        backend_constraints = [
            "只实现后端代码。",
            "不要修改前端代码。",
            "API 必须遵循 ApiContractDraft。",
            "数据库模型必须遵循 DbModelDraft。",
            "不要把业务逻辑放在路由中。",
            "不要意外改变 API 响应结构。",
        ]
        frontend_do_not = ["不要修改后端代码。", "除非明确要求，不要新增真实认证。"]
        backend_do_not = ["不要修改前端代码。", "不要连接真实 LLM 服务。"]
    else:
        frontend_goal = (
            "Implement frontend features based on the provided blueprint and API contract."
        )
        backend_goal = "Implement backend features based on the blueprint and generated drafts."
        frontend_expected = [
            "Next.js pages/components matching ProjectBlueprint.pages.",
            "TypeScript API types derived from ApiContractDraft.",
            "Loading, error, empty, and success states.",
        ]
        backend_expected = [
            "FastAPI routes matching ApiContractDraft.",
            "Pydantic schemas and SQLAlchemy models matching DbModelDraft.",
            "Service-layer business logic and Alembic migrations.",
        ]
        frontend_constraints = [
            "Only implement frontend code.",
            "Do not modify backend code.",
            "Do not invent APIs; use ApiContractDraft as the source of truth.",
            "Use TypeScript types.",
            "Do not introduce unnecessary large dependencies.",
        ]
        backend_constraints = [
            "Only implement backend code.",
            "Do not modify frontend code.",
            "API must follow ApiContractDraft.",
            "Database model must follow DbModelDraft.",
            "Do not put business logic in routes.",
            "Do not change API response structures unexpectedly.",
        ]
        frontend_do_not = [
            "Do not modify backend code.",
            "Do not add real authentication unless specified.",
        ]
        backend_do_not = ["Do not modify frontend code.", "Do not connect real LLM services."]

    frontend_content = {
        "role": "frontend_engineer",
        "goal": frontend_goal,
        "included_context": {
            "project_summary": _project_summary(blueprint_content),
            "relevant_pages": _list_from_blueprint(blueprint_content, "pages"),
            "relevant_api_contract": api_context,
            "relevant_entities": _list_from_blueprint(blueprint_content, "domain_entities"),
        },
        "task_boundaries": frontend_constraints[:2],
        "tech_stack": [_stack_summary(blueprint_content, "frontend", DEFAULT_FRONTEND_STACK)],
        "expected_output": frontend_expected,
        "constraints": frontend_constraints,
        "do_not_do": frontend_do_not,
    }

    backend_content = {
        "role": "backend_engineer",
        "goal": backend_goal,
        "included_context": {
            "project_summary": _project_summary(blueprint_content),
            "relevant_pages": _list_from_blueprint(blueprint_content, "pages"),
            "relevant_api_contract": api_context,
            "relevant_db_model": db_context,
            "relevant_entities": _list_from_blueprint(blueprint_content, "domain_entities"),
        },
        "task_boundaries": backend_constraints[:2],
        "tech_stack": [_stack_summary(blueprint_content, "backend", DEFAULT_BACKEND_STACK)],
        "expected_output": backend_expected,
        "constraints": backend_constraints,
        "do_not_do": backend_do_not,
    }

    if normalized_language == "zh-CN":
        return [
            {
                "role": "frontend_engineer",
                "title": "前端工程师 Context Pack",
                "summary": "用于基于蓝图和 API 草案实现前端功能的 Codex 指令集合。",
                "content": frontend_content,
                "prompt_text": _frontend_prompt_zh(frontend_content),
            },
            {
                "role": "backend_engineer",
                "title": "后端工程师 Context Pack",
                "summary": "用于基于蓝图和生成草案实现后端功能的 Codex 指令集合。",
                "content": backend_content,
                "prompt_text": _backend_prompt_zh(backend_content),
            },
        ]

    return [
        {
            "role": "frontend_engineer",
            "title": "Frontend Engineer Context Pack",
            "summary": "Codex prompt pack for implementing frontend features from blueprint "
            "and API draft.",
            "content": frontend_content,
            "prompt_text": _frontend_prompt(frontend_content),
        },
        {
            "role": "backend_engineer",
            "title": "Backend Engineer Context Pack",
            "summary": "Codex prompt pack for implementing backend features from blueprint "
            "and generated drafts.",
            "content": backend_content,
            "prompt_text": _backend_prompt(backend_content),
        },
    ]
