from typing import Any

from app.core.constants import DEFAULT_BACKEND_STACK, DEFAULT_FRONTEND_STACK
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


def build_context_pack_payloads(
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if should_use_real_llm():
        return build_llm_context_pack_payloads(
            blueprint_content,
            api_contract_content,
            db_model_content,
        )
    return _build_rule_based_context_pack_payloads(
        blueprint_content,
        api_contract_content,
        db_model_content,
    )


def build_llm_context_pack_payloads(
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
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
) -> list[dict[str, Any]]:
    api_context = api_contract_content or {
        "missing": "ApiContractDraft has not been generated yet."
    }
    db_context = db_model_content or {"missing": "DbModelDraft has not been generated yet."}

    frontend_content = {
        "role": "frontend_engineer",
        "goal": "Implement frontend features based on the provided blueprint and API contract.",
        "included_context": {
            "project_summary": _project_summary(blueprint_content),
            "relevant_pages": _list_from_blueprint(blueprint_content, "pages"),
            "relevant_api_contract": api_context,
            "relevant_entities": _list_from_blueprint(blueprint_content, "domain_entities"),
        },
        "task_boundaries": ["Only implement frontend code.", "Do not modify backend code."],
        "tech_stack": [_stack_summary(blueprint_content, "frontend", DEFAULT_FRONTEND_STACK)],
        "expected_output": [
            "Next.js pages/components matching ProjectBlueprint.pages.",
            "TypeScript API types derived from ApiContractDraft.",
            "Loading, error, empty, and success states.",
        ],
        "constraints": [
            "Only implement frontend code.",
            "Do not modify backend code.",
            "Do not invent APIs; use ApiContractDraft as the source of truth.",
            "Use TypeScript types.",
            "Do not introduce unnecessary large dependencies.",
        ],
        "do_not_do": [
            "Do not modify backend code.",
            "Do not add real authentication unless specified.",
        ],
    }

    backend_content = {
        "role": "backend_engineer",
        "goal": "Implement backend features based on the blueprint and generated drafts.",
        "included_context": {
            "project_summary": _project_summary(blueprint_content),
            "relevant_pages": _list_from_blueprint(blueprint_content, "pages"),
            "relevant_api_contract": api_context,
            "relevant_db_model": db_context,
            "relevant_entities": _list_from_blueprint(blueprint_content, "domain_entities"),
        },
        "task_boundaries": ["Only implement backend code.", "Do not modify frontend code."],
        "tech_stack": [_stack_summary(blueprint_content, "backend", DEFAULT_BACKEND_STACK)],
        "expected_output": [
            "FastAPI routes matching ApiContractDraft.",
            "Pydantic schemas and SQLAlchemy models matching DbModelDraft.",
            "Service-layer business logic and Alembic migrations.",
        ],
        "constraints": [
            "Only implement backend code.",
            "Do not modify frontend code.",
            "API must follow ApiContractDraft.",
            "Database model must follow DbModelDraft.",
            "Do not put business logic in routes.",
            "Do not change API response structures unexpectedly.",
        ],
        "do_not_do": ["Do not modify frontend code.", "Do not connect real LLM services."],
    }

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
