from __future__ import annotations

from typing import Any

VALID_IMPLEMENTATION_SCOPES = {"frontend_only", "backend_only", "fullstack", "non_code"}
VALID_CHANGE_SET_STATUSES = {"draft", "ready", "applied", "discarded", "failed"}
VALID_UI_TOKEN_STATUSES = {"validated", "normative", "tbd", "inferred"}
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


def validate_change_set_payload(
    parsed: dict[str, Any],
    *,
    expected_layer: str | None = None,
) -> dict[str, Any]:
    title = _normalize_change_set_title(_require_string(parsed.get("title"), "title"))
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
    if expected_layer is not None and layers != [expected_layer]:
        raise OrchestrationValidationError(
            f"ChangeSet affected_layers must equal [{expected_layer!r}]."
        )
    module_changes = parsed.get("module_changes")
    if not isinstance(module_changes, dict):
        raise OrchestrationValidationError("ChangeSet module_changes must be an object.")
    module_changes = _normalize_module_changes(module_changes, layers)
    content = _dict_or_empty(parsed.get("content"))
    if expected_layer is not None:
        content["layer"] = expected_layer
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
        "content": content,
        "diff_from_previous": _dict_or_empty(
            parsed.get("diff_from_previous") or parsed.get("diff")
        ),
        "summary": _string_or_none(parsed.get("summary")),
    }


def validate_design_asset_payload(parsed: dict[str, Any], *, layer: str) -> dict[str, Any]:
    content = parsed.get("content")
    if not isinstance(content, dict):
        raise OrchestrationValidationError(f"{layer} content must be an object.")
    if layer == "ui_design":
        content = _normalize_ui_design_content(content)
    diff = parsed.get("diff_from_previous") or content.get("diff")
    return {
        "title": _string_or_default(parsed.get("title"), _default_asset_title(layer)),
        "summary": _string_or_none(parsed.get("summary"))
        or _string_or_none(content.get("version_summary"))
        or "设计资产已更新。",
        "content": content,
        "diff_from_previous": _dict_or_empty(diff),
    }


def _normalize_ui_design_content(content: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(content)
    normalized["diff"] = _diff_or_default(normalized.get("diff"))
    visual_system = _dict_or_empty(normalized.get("visual_system"))
    state_matrix = _normalize_interaction_state_matrix(
        visual_system.get("interaction_state_matrix")
    )
    legacy_token_catalog = _list_or_empty(visual_system.pop("token_catalog", None))
    visual_system["interaction_state_matrix"] = state_matrix
    for key in (
        "source_references",
        "tbd_items",
        "accessibility_rules",
        "responsive_contract",
        "design_principles",
    ):
        visual_system[key] = _list_or_empty(visual_system.get(key))
    for key in (
        "color_system",
        "typography_system",
        "spacing_system",
        "shape_system",
        "elevation_system",
        "interaction_visual_system",
    ):
        visual_system[key] = _normalize_ui_token_system(visual_system.get(key))
    _migrate_legacy_token_catalog(visual_system, legacy_token_catalog)
    visual_system["tailwind_theme_css"] = _string_or_none(
        visual_system.get("tailwind_theme_css")
    )
    normalized["visual_system"] = visual_system
    normalized["layout_rules"] = _list_or_empty(normalized.get("layout_rules"))
    normalized["component_style_rules"] = _list_or_empty(
        normalized.get("component_style_rules")
    )
    return normalized


def _migrate_legacy_token_catalog(
    visual_system: dict[str, Any],
    legacy_token_catalog: list[Any],
) -> None:
    for group in legacy_token_catalog:
        if not isinstance(group, dict):
            continue
        group_name = _string_or_none(group.get("group_name")) or ""
        for token in _list_or_empty(group.get("tokens")):
            if not isinstance(token, dict):
                continue
            token_type = _string_or_none(token.get("token_type"))
            target_key = _ui_token_system_key(token_type, group_name, token)
            normalized_token = _normalize_ui_token(token)
            visual_system[target_key]["tokens"].append(normalized_token)


def _ui_token_system_key(
    token_type: str | None,
    group_name: str,
    token: dict[str, Any],
) -> str:
    probe = " ".join(
        [
            token_type or "",
            group_name,
            _string_or_none(token.get("token_name")) or "",
            _string_or_none(token.get("semantic_role")) or "",
        ]
    ).lower()
    if any(marker in probe for marker in ("typography", "font", "text", "字体")):
        return "typography_system"
    if any(marker in probe for marker in ("spacing", "space", "gap", "间距")):
        return "spacing_system"
    if any(marker in probe for marker in ("radius", "shape", "border", "圆角", "形状")):
        return "shape_system"
    if any(marker in probe for marker in ("shadow", "elevation", "阴影", "层级")):
        return "elevation_system"
    if any(marker in probe for marker in ("interaction", "motion", "state", "交互", "状态")):
        return "interaction_visual_system"
    return "color_system"


def _normalize_ui_token_system(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        system = dict(value)
        tokens_value = system.get("tokens")
    else:
        system = {"description": None, "rules": _list_or_empty(value), "tbd_items": []}
        tokens_value = []

    normalized_tokens: list[dict[str, Any]] = []
    for token in _list_or_empty(tokens_value):
        if not isinstance(token, dict):
            continue
        normalized_tokens.append(_normalize_ui_token(token))

    system["description"] = _string_or_none(system.get("description"))
    system["rules"] = _list_or_empty(system.get("rules"))
    system["tokens"] = normalized_tokens
    system["tbd_items"] = _list_or_empty(system.get("tbd_items"))
    return system


def _normalize_ui_token(token: dict[str, Any]) -> dict[str, Any]:
    normalized_token = dict(token)
    normalized_token["token_name"] = _string_or_default(
        normalized_token.get("token_name"), "unnamed-token"
    )
    normalized_token["description"] = _string_or_none(
        normalized_token.get("description")
    ) or _string_or_none(normalized_token.get("$description"))
    normalized_token["semantic_role"] = _string_or_none(
        normalized_token.get("semantic_role")
    )
    normalized_token["usage_context"] = _string_or_none(
        normalized_token.get("usage_context")
    )
    normalized_token["anti_usage"] = _ui_token_string_list(
        normalized_token.get("anti_usage")
    )
    normalized_token["source_basis"] = _ui_token_string_list(
        normalized_token.get("source_basis")
    )
    status = normalized_token.get("validated_status")
    if status is not None and status not in VALID_UI_TOKEN_STATUSES:
        raise OrchestrationValidationError(
            "UI token validated_status must be one of "
            "validated, normative, tbd, inferred."
        )
    return normalized_token


def _ui_token_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _string_or_none(item)
        if text:
            normalized.append(text)
    return normalized


def _normalize_interaction_state_matrix(value: Any) -> list[dict[str, Any]]:
    states = _list_or_empty(value)
    normalized_states: list[dict[str, Any]] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        normalized_state = dict(state)
        normalized_state["visual_cues"] = _list_or_empty(
            normalized_state.get("visual_cues")
        )
        normalized_state["usage_context"] = _list_or_empty(
            normalized_state.get("usage_context")
        )
        normalized_state["constraints"] = _list_or_empty(
            normalized_state.get("constraints")
        )
        normalized_states.append(normalized_state)
    return normalized_states


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


def _normalize_change_set_title(value: str) -> str:
    suffix = "变更集"
    normalized = value.strip()
    while normalized.endswith(suffix):
        normalized = normalized.removesuffix(suffix).strip()
    return f"{normalized}{suffix}"


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
        "frontend_pages": "前端工程实现",
        "frontend_tools": "前端工程实现扩展",
        "api_contract": "API 契约",
        "backend_services": "后端工程实现",
        "backend_tools": "后端工程实现扩展",
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
            "added": _normalize_change_items(current.get("added")),
            "modified": _normalize_change_items(current.get("modified")),
            "removed": _normalize_change_items(current.get("removed")),
        }
    return normalized


def _normalize_change_items(value: Any) -> list[Any]:
    items = _list_or_empty(value)
    normalized: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        normalized_item = dict(item)
        normalized_item["selector"] = _dict_or_empty(normalized_item.get("selector"))
        normalized_item["constraints"] = _list_or_empty(normalized_item.get("constraints"))
        normalized_item["dependencies"] = _list_or_empty(normalized_item.get("dependencies"))
        normalized_item["acceptance_criteria"] = _list_or_empty(
            normalized_item.get("acceptance_criteria")
        )
        normalized.append(normalized_item)
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


def _diff_or_default(value: Any) -> dict[str, list[Any]]:
    diff = _dict_or_empty(value)
    return {
        "added": _list_or_empty(diff.get("added")),
        "modified": _list_or_empty(diff.get("modified")),
        "removed": _list_or_empty(diff.get("removed")),
    }
