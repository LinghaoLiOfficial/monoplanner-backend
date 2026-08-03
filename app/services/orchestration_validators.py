from __future__ import annotations

from typing import Any

VALID_IMPLEMENTATION_SCOPES = {"frontend_only", "backend_only", "fullstack", "non_code"}
VALID_CHANGE_SET_STATUSES = {"draft", "ready", "applied", "discarded", "failed"}
VALID_AFFECTED_LAYERS = {
    "ux_design",
    "ui_design",
    "frontend_pages",
    "frontend_tools",
    "api_contract",
    "backend_services",
    "backend_tools",
    "database_models",
    "project_blueprint",
    "prompt_assets",
}


class OrchestrationValidationError(ValueError):
    """Raised when an orchestration LLM output cannot be used safely."""


def validate_change_set_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    title = _require_string(parsed.get("title"), "title")
    scope = _require_enum(
        parsed.get("implementation_scope"),
        VALID_IMPLEMENTATION_SCOPES,
        "implementation_scope",
    )
    layers = _string_list(parsed.get("affected_layers"), "affected_layers")
    if not layers:
        raise OrchestrationValidationError("ChangeSet affected_layers must not be empty.")
    invalid_layers = sorted(set(layers) - VALID_AFFECTED_LAYERS)
    if invalid_layers:
        raise OrchestrationValidationError(
            f"ChangeSet affected_layers contains invalid layers: {invalid_layers}."
        )
    module_changes = parsed.get("module_changes")
    if not isinstance(module_changes, dict):
        raise OrchestrationValidationError("ChangeSet module_changes must be an object.")
    module_changes = _normalize_module_changes(module_changes, layers)
    return {
        "title": title,
        "status": _normalize_status(parsed.get("status")),
        "implementation_scope": scope,
        "affected_layers": layers,
        "impact_summary": _string_or_none(parsed.get("impact_summary")),
        "module_changes": module_changes,
        "risks": _list_or_empty(parsed.get("risks")),
        "open_questions": _list_or_empty(parsed.get("open_questions")),
        "recommended_prompt_strategy": _dict_or_empty(
            parsed.get("recommended_prompt_strategy")
        ),
        "content": _dict_or_empty(parsed.get("content")),
        "diff_from_previous": _dict_or_empty(
            parsed.get("diff_from_previous") or parsed.get("diff")
        ),
        "summary": _string_or_none(parsed.get("summary")),
    }


def validate_design_asset_payload(parsed: dict[str, Any], *, layer: str) -> dict[str, Any]:
    content = parsed.get("content")
    if not isinstance(content, dict):
        raise OrchestrationValidationError(f"{layer} content must be an object.")
    diff = parsed.get("diff_from_previous") or content.get("diff")
    return {
        "title": _string_or_default(parsed.get("title"), _default_asset_title(layer)),
        "summary": _string_or_none(parsed.get("summary"))
        or _string_or_none(content.get("version_summary"))
        or "设计资产已更新。",
        "content": content,
        "diff_from_previous": _dict_or_empty(diff),
    }


def validate_blueprint_summary_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    required_objects = ("project", "current_product_scope", "frontend_summary", "backend_summary")
    for field in required_objects:
        if not isinstance(parsed.get(field), dict):
            raise OrchestrationValidationError(f"Blueprint summary {field} must be an object.")
    return {
        "project": parsed["project"],
        "current_product_scope": parsed["current_product_scope"],
        "business_capabilities": _list_or_empty(parsed.get("business_capabilities")),
        "ux_summary": _dict_or_empty(parsed.get("ux_summary")),
        "ui_summary": _dict_or_empty(parsed.get("ui_summary")),
        "frontend_summary": parsed["frontend_summary"],
        "backend_summary": parsed["backend_summary"],
        "architecture_notes": _list_or_empty(parsed.get("architecture_notes")),
        "risks": _list_or_empty(parsed.get("risks")),
        "open_questions": _list_or_empty(parsed.get("open_questions")),
        "version_summary": _string_or_default(
            parsed.get("version_summary"), "项目蓝图已根据最新设计资产更新。"
        ),
    }


def validate_prompt_pack_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    frontend_prompt = parsed.get("frontend_prompt")
    backend_prompt = parsed.get("backend_prompt")
    if not isinstance(frontend_prompt, dict):
        raise OrchestrationValidationError("Prompt pack frontend_prompt must be an object.")
    if not isinstance(backend_prompt, dict):
        raise OrchestrationValidationError("Prompt pack backend_prompt must be an object.")
    scope = _require_enum(
        parsed.get("implementation_scope"),
        VALID_IMPLEMENTATION_SCOPES,
        "implementation_scope",
    )
    return {
        "batch_summary": _string_or_default(parsed.get("batch_summary"), "实现指令集合"),
        "implementation_scope": scope,
        "frontend_prompt": _normalize_prompt(frontend_prompt),
        "backend_prompt": _normalize_prompt(backend_prompt),
        "diff_summary": _dict_or_empty(parsed.get("diff_summary")),
        "execution_order": _list_or_empty(parsed.get("execution_order")),
        "acceptance_checklist": _list_or_empty(parsed.get("acceptance_checklist")),
        "rollback_notes": _list_or_empty(parsed.get("rollback_notes")),
    }


def _normalize_status(value: Any) -> str:
    if value is None:
        return "ready"
    return _require_enum(value, VALID_CHANGE_SET_STATUSES, "status")


def _normalize_prompt(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "needed": bool(value.get("needed", False)),
        "title": _string_or_default(value.get("title"), "Codex 指令"),
        "prompt": _string_or_default(value.get("prompt"), ""),
        "affected_files": _list_or_empty(value.get("affected_files")),
        "do_not_modify": _list_or_empty(value.get("do_not_modify")),
        "verification_steps": _list_or_empty(value.get("verification_steps")),
    }


def _default_asset_title(layer: str) -> str:
    return {
        "ux_design": "UX 设计",
        "ui_design": "UI 设计",
        "frontend_pages": "前端页面结构",
        "frontend_tools": "前端依赖与工具",
        "api_contract": "API 契约",
        "backend_services": "后端服务设计",
        "backend_tools": "后端依赖与工具",
        "database_models": "数据库模型",
    }.get(layer, "设计资产")


def _normalize_module_changes(
    value: dict[str, Any], affected_layers: list[str]
) -> dict[str, Any]:
    normalized = dict(value)
    for layer in affected_layers:
        current = normalized.get(layer)
        if not isinstance(current, dict):
            current = {}
        normalized[layer] = {
            "added": _list_or_empty(current.get("added")),
            "modified": _list_or_empty(current.get("modified")),
            "removed": _list_or_empty(current.get("removed")),
            "unchanged": _list_or_empty(current.get("unchanged")),
        }
    return normalized


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationValidationError(f"{field} must be a non-empty string.")
    return value.strip()


def _require_enum(value: Any, allowed: set[str], field: str) -> str:
    if not isinstance(value, str):
        raise OrchestrationValidationError(f"{field} must be a string.")
    normalized = value.strip()
    if normalized not in allowed:
        raise OrchestrationValidationError(f"{field} is invalid: {normalized}.")
    return normalized


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _string_or_none(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise OrchestrationValidationError(f"{field} must be a list.")
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise OrchestrationValidationError(f"{field} must contain strings.")
        normalized.append(item.strip())
    return normalized


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
