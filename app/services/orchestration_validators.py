from __future__ import annotations

from typing import Any

VALID_IMPLEMENTATION_SCOPES = {"frontend_only", "backend_only", "fullstack", "non_code"}
VALID_CHANGE_SET_STATUSES = {"draft", "ready", "applied", "discarded", "failed"}
VALID_AFFECTED_LAYERS = {
    "ux_design",
    "ui_design",
    "frontend_pages",
    "api_contract",
    "backend_services",
    "database_models",
}


class OrchestrationValidationError(ValueError):
    """Raised when an orchestration LLM output cannot be used safely."""


def validate_change_set_payload(parsed: dict[str, Any], *, expected_layer: str | None = None) -> dict[str, Any]:
    layers = _string_list(parsed.get("affected_layers"), "affected_layers")
    if not layers:
        raise OrchestrationValidationError("ChangeSet affected_layers must not be empty.")
    invalid_layers = sorted(set(layers) - VALID_AFFECTED_LAYERS)
    if invalid_layers:
        raise OrchestrationValidationError(
            f"ChangeSet affected_layers contains invalid layers: {invalid_layers}."
        )
    if expected_layer is not None and layers != [expected_layer]:
        raise OrchestrationValidationError(f"ChangeSet affected_layers must equal [{expected_layer!r}].")
    module_changes = parsed.get("module_changes")
    if not isinstance(module_changes, dict):
        raise OrchestrationValidationError("ChangeSet module_changes must be an object.")
    return {
        "title": _normalize_change_set_title(_string_or_default(parsed.get("title"), "变更集")),
        "status": _normalize_status(parsed.get("status")),
        "implementation_scope": _require_enum(parsed.get("implementation_scope"), VALID_IMPLEMENTATION_SCOPES, "implementation_scope"),
        "affected_layers": layers,
        "impact_summary": _string_or_none(parsed.get("impact_summary")),
        "module_changes": {layer: _normalize_module_changes(module_changes.get(layer), layer) for layer in layers},
        "risks": _list_or_empty(parsed.get("risks")),
        "open_questions": _list_or_empty(parsed.get("open_questions")),
        "recommended_prompt_strategy": _dict_or_empty(parsed.get("recommended_prompt_strategy")),
        "content": _dict_or_empty(parsed.get("content")),
        "diff": _dict_or_empty(parsed.get("diff") or parsed.get("diff_from_previous")),
    }


def validate_design_asset_payload(parsed: dict[str, Any], *, layer: str) -> dict[str, Any]:
    content = parsed.get("content")
    if not isinstance(content, dict):
        raise OrchestrationValidationError(f"{layer} content must be an object.")
    normalized = dict(content)
    normalized["diff"] = _diff_or_default(normalized.get("diff"))
    if layer == "ux_design":
        normalized = {
            key: normalized[key]
            for key in ("version_summary", "low_fidelity_screen_structure", "business_flows", "diff")
            if key in normalized
        }
        normalized["low_fidelity_screen_structure"] = _list_or_empty(normalized.get("low_fidelity_screen_structure"))
        normalized["business_flows"] = _list_or_empty(normalized.get("business_flows"))
    elif layer == "ui_design":
        normalized = {
            key: normalized[key]
            for key in ("version_summary", "visual_system", "diff")
            if key in normalized
        }
        visual_system = _dict_or_empty(normalized.get("visual_system"))
        visual_system["design_style"] = _dict_or_empty(visual_system.get("design_style"))
        visual_system["theme_configuration"] = _dict_or_empty(visual_system.get("theme_configuration"))
        for key in ("color_configuration", "font_configuration", "spacing_configuration", "shape_configuration", "shadow_configuration"):
            visual_system[key] = _dict_or_empty(visual_system.get(key))
            visual_system[key]["colors" if key == "color_configuration" else "fonts" if key == "font_configuration" else "spacings" if key == "spacing_configuration" else "shapes" if key == "shape_configuration" else "shadows"] = _list_or_empty(visual_system[key].get("colors" if key == "color_configuration" else "fonts" if key == "font_configuration" else "spacings" if key == "spacing_configuration" else "shapes" if key == "shape_configuration" else "shadows"))
        normalized["visual_system"] = visual_system
    elif layer == "frontend_pages":
        normalized = {
            key: normalized[key]
            for key in (
                "version_summary",
                "environment_variables",
                "route_definitions",
                "directory_structure",
                "layout_library",
                "component_library",
                "dependency_package_management",
                "page_code_logic",
                "frontend_interfaces",
                "diff",
            )
            if key in normalized
        }
        normalized["environment_variables"] = _list_or_empty(normalized.get("environment_variables"))
        normalized["route_definitions"] = _list_or_empty(normalized.get("route_definitions"))
        normalized["directory_structure"] = _list_or_empty(normalized.get("directory_structure"))
        normalized["dependency_package_management"] = _list_or_empty(normalized.get("dependency_package_management"))
        normalized["page_code_logic"] = _list_or_empty(normalized.get("page_code_logic"))
        normalized["frontend_interfaces"] = _list_or_empty(normalized.get("frontend_interfaces"))
    return {
        "title": _string_or_default(parsed.get("title"), _default_asset_title(layer)),
        "summary": _string_or_none(parsed.get("summary")) or _string_or_none(normalized.get("version_summary")) or "设计资产已更新。",
        "content": normalized,
        "diff_from_previous": _dict_or_empty(parsed.get("diff_from_previous") or normalized.get("diff")),
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
        "version_summary": _string_or_default(parsed.get("version_summary"), "项目蓝图已根据最新设计资产更新。"),
    }


def validate_prompt_pack_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    frontend_prompt = parsed.get("frontend_prompt")
    backend_prompt = parsed.get("backend_prompt")
    if not isinstance(frontend_prompt, dict):
        raise OrchestrationValidationError("Prompt pack frontend_prompt must be an object.")
    if not isinstance(backend_prompt, dict):
        raise OrchestrationValidationError("Prompt pack backend_prompt must be an object.")
    return {
        "batch_summary": _string_or_default(parsed.get("batch_summary"), "实现指令集合"),
        "implementation_scope": _require_enum(parsed.get("implementation_scope"), VALID_IMPLEMENTATION_SCOPES, "implementation_scope"),
        "frontend_prompt": _normalize_prompt(frontend_prompt),
        "backend_prompt": _normalize_prompt(backend_prompt),
        "diff_summary": _dict_or_empty(parsed.get("diff_summary")),
        "execution_order": _list_or_empty(parsed.get("execution_order")),
        "acceptance_checklist": _list_or_empty(parsed.get("acceptance_checklist")),
        "rollback_notes": _list_or_empty(parsed.get("rollback_notes")),
    }


def _normalize_module_changes(value: Any, layer: str) -> dict[str, Any]:
    current = value if isinstance(value, dict) else {}
    return {
        "added": _change_items(current.get("added")),
        "modified": _change_items(current.get("modified")),
        "removed": _change_items(current.get("removed")),
    }


def _change_items(value: Any) -> list[Any]:
    return _list_or_empty(value)


def _normalize_prompt(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "needed": bool(value.get("needed", False)),
        "title": _string_or_default(value.get("title"), "Codex 指令"),
        "prompt": _string_or_default(value.get("prompt"), ""),
        "affected_files": _list_or_empty(value.get("affected_files")),
        "do_not_modify": _list_or_empty(value.get("do_not_modify")),
        "verification_steps": _list_or_empty(value.get("verification_steps")),
    }


def _normalize_change_set_title(value: str) -> str:
    suffix = "变更集"
    normalized = value.strip()
    while normalized.endswith(suffix):
        normalized = normalized.removesuffix(suffix).strip()
    return f"{normalized}{suffix}"


def _normalize_status(value: Any) -> str:
    if value is None:
        return "ready"
    return _require_enum(value, VALID_CHANGE_SET_STATUSES, "status")


def _default_asset_title(layer: str) -> str:
    return {
        "ux_design": "UX 设计",
        "ui_design": "UI 设计",
        "frontend_pages": "前端工程实现",
        "api_contract": "API 契约",
        "backend_services": "后端工程实现",
        "database_models": "数据库模型",
    }.get(layer, "设计资产")


def _require_enum(value: Any, allowed: set[str], field: str) -> str:
    text = _string_or_none(value)
    if text not in allowed:
        raise OrchestrationValidationError(f"{field} must be one of {sorted(allowed)}.")
    return text


def _string_list(value: Any, field: str) -> list[str]:
    items = _list_or_empty(value)
    result = [item for item in (_string_or_none(item) for item in items) if item]
    if value is not None and not result:
        raise OrchestrationValidationError(f"{field} must contain at least one string.")
    return result


def _list_or_empty(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_or_default(value: Any, default: str) -> str:
    return _string_or_none(value) or default


def _diff_or_default(value: Any) -> dict[str, list[Any]]:
    if isinstance(value, dict):
        return {
            "added": _list_or_empty(value.get("added")),
            "modified": _list_or_empty(value.get("modified")),
            "removed": _list_or_empty(value.get("removed")),
        }
    return {"added": [], "modified": [], "removed": []}
