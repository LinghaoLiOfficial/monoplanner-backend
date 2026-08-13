import re
from typing import Any

from app.llm.json_client import generate_json
from app.prompts.api_contract_generator import build_api_contract_generation_prompt
from app.prompts.templates.api_contract_generator.output_schema import ApiContractOutput

VALID_METHODS = {"GET", "POST", "PATCH", "PUT", "DELETE"}


class ApiContractValidationError(ValueError):
    """Raised when LLM API contract output does not match the expected shape."""

_OPERATION_MAP = {
    "list": ("GET", "/{resource}", "list_{resource}", "List {resource}"),
    "read": ("GET", "/{resource}/{id}", "read_{resource}", "Read one {resource}"),
    "create": ("POST", "/{resource}", "create_{resource}", "Create {resource}"),
    "update": ("PATCH", "/{resource}/{id}", "update_{resource}", "Update {resource}"),
    "delete": ("DELETE", "/{resource}/{id}", "delete_{resource}", "Delete {resource}"),
    "generate": ("POST", "/{resource}/generate", "generate_{resource}", "Generate {resource}"),
}


def _title_from_resource(resource: str) -> str:
    return "".join(part.capitalize() for part in resource.replace("-", "_").split("_"))


def _field_type(field_name: str) -> str:
    lower = field_name.lower()
    if lower == "id" or lower.endswith("_id"):
        return "uuid"
    if lower.startswith("is_") or lower.startswith("has_"):
        return "boolean"
    if lower.endswith("_at"):
        return "datetime"
    if lower in {"count", "version", "order", "priority"}:
        return "integer"
    return "string"


def _normalize_fields(raw_fields: Any) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    if not isinstance(raw_fields, list):
        return fields
    for raw_field in raw_fields:
        if isinstance(raw_field, str):
            fields.append(
                {
                    "name": raw_field,
                    "type": _field_type(raw_field),
                    "required": raw_field in {"id", "name"} or raw_field.endswith("_id"),
                    "description": f"{raw_field.replace('_', ' ').title()} field",
                }
            )
        elif isinstance(raw_field, dict) and isinstance(raw_field.get("name"), str):
            name = raw_field["name"]
            fields.append(
                {
                    "name": name,
                    "type": raw_field.get("type") or _field_type(name),
                    "required": bool(raw_field.get("required", name == "id")),
                    "description": raw_field.get("description")
                    or f"{name.replace('_', ' ').title()} field",
                }
            )
    return fields


def build_api_contract_content(project: Any, blueprint_content: dict[str, Any]) -> dict[str, Any]:
    return build_llm_api_contract_content(project, blueprint_content)


def build_llm_api_contract_content(
    project: Any,
    blueprint_content: dict[str, Any],
) -> dict[str, Any]:
    prompt = build_api_contract_generation_prompt(project, blueprint_content)
    content = generate_json(
        system_prompt=prompt.system,
        user_payload=prompt.user,
        response_model=ApiContractOutput,
    )
    return validate_api_contract_content(content)


def validate_api_contract_content(content: dict[str, Any]) -> dict[str, Any]:
    base_path = content.get("api_base_path") or content.get("base_path")
    if not isinstance(base_path, str) or not base_path.startswith("/"):
        raise ApiContractValidationError("API contract api_base_path is required.")

    resource_groups = content.get("api_resource_groups")
    if resource_groups is None and isinstance(content.get("resources"), list):
        resource_groups = _legacy_resources_to_resource_groups(content["resources"])
    if not isinstance(resource_groups, list):
        raise ApiContractValidationError("API contract api_resource_groups must be a list.")

    normalized_groups = []
    for group in resource_groups:
        if not isinstance(group, dict):
            raise ApiContractValidationError("API contract resource group must be an object.")
        endpoints = group.get("endpoints")
        if not isinstance(endpoints, list):
            raise ApiContractValidationError(
                "API contract resource group endpoints must be a list."
            )
        normalized_endpoints = [_normalize_endpoint(endpoint) for endpoint in endpoints]
        normalized_groups.append(
            {
                "group_name": _require_string(
                    group.get("group_name") or group.get("name"), "api_resource_groups.group_name"
                ),
                "group_purpose": _string_or_default(
                    group.get("group_purpose") or group.get("description"), ""
                ),
                "endpoints": normalized_endpoints,
            }
        )

    return {
        "api_base_path": base_path.rstrip("/") if base_path != "/" else base_path,
        "api_resource_groups": normalized_groups,
        "notes": _string_list(content.get("notes")),
    }


def _normalize_endpoint(endpoint: Any) -> dict[str, Any]:
    if not isinstance(endpoint, dict):
        raise ApiContractValidationError("API contract endpoint must be an object.")
    method = _require_string(
        endpoint.get("http_method") or endpoint.get("method"), "endpoints.http_method"
    ).upper()
    if method not in VALID_METHODS:
        raise ApiContractValidationError("API contract endpoint method is invalid.")
    return {
        "http_method": method,
        "endpoint_path": _require_string(
            endpoint.get("endpoint_path") or endpoint.get("path"), "endpoints.endpoint_path"
        ),
        "endpoint_purpose": _require_string(
            endpoint.get("endpoint_purpose") or endpoint.get("purpose"),
            "endpoints.endpoint_purpose",
        ),
        "requires_auth": bool(endpoint.get("requires_auth", endpoint.get("auth_required", True))),
        "request_schema": _dict_or_empty(
            endpoint.get("request_schema")
            if "request_schema" in endpoint
            else _legacy_schema_ref(endpoint.get("request_body"))
        ),
        "response_schema": _dict_or_empty(
            endpoint.get("response_schema")
            if "response_schema" in endpoint
            else _legacy_schema_ref(endpoint.get("response_body"))
        ),
        "error_model": _normalize_error_model(endpoint.get("error_model"), endpoint.get("errors")),
    }


def _normalize_error_model(value: Any, legacy_errors: Any = None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [_normalize_error_case(item) for item in value]
    errors = _string_list(legacy_errors)
    normalized = []
    for error in errors:
        normalized.append(
            {
                "status_code": _status_code_from_error(error),
                "error_code": error.upper().replace(" ", "_"),
                "error_message": error,
                "recovery_suggestion": "",
            }
        )
    return normalized


def _normalize_error_case(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ApiContractValidationError("API contract error_case must be an object.")
    status_code = value.get("status_code")
    if not isinstance(status_code, int):
        raise ApiContractValidationError("API contract error_case status_code must be an integer.")
    return {
        "status_code": status_code,
        "error_code": _require_string(value.get("error_code"), "error_case.error_code"),
        "error_message": _require_string(value.get("error_message"), "error_case.error_message"),
        "recovery_suggestion": _string_or_default(value.get("recovery_suggestion"), ""),
    }


def _legacy_resources_to_resource_groups(resources: list[Any]) -> list[dict[str, Any]]:
    groups = []
    for resource in resources:
        if isinstance(resource, dict):
            groups.append(
                {
                    "group_name": resource.get("name"),
                    "group_purpose": resource.get("description"),
                    "endpoints": resource.get("endpoints", []),
                }
            )
    return groups


def _legacy_schema_ref(value: Any) -> dict[str, Any]:
    if isinstance(value, str) and value.strip():
        return {"schema_ref": value.strip()}
    return {}


def _status_code_from_error(value: str) -> int:
    match = re.search(r"\b([1-5][0-9]{2})\b", value)
    if match:
        return int(match.group(1))
    return 400


def _build_rule_based_api_contract_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    api_needs = blueprint_content.get("api_needs")
    domain_entities = blueprint_content.get("domain_entities")
    resources: list[dict[str, Any]] = []

    if isinstance(api_needs, list):
        for api_need in api_needs:
            if not isinstance(api_need, dict):
                continue
            resource = api_need.get("resource")
            if not isinstance(resource, str) or not resource:
                continue
            endpoints: list[dict[str, Any]] = []
            operations = (
                api_need.get("operations") if isinstance(api_need.get("operations"), list) else []
            )
            for operation in operations:
                if not isinstance(operation, str):
                    continue
                method, path_template, operation_id_template, purpose_template = _OPERATION_MAP.get(
                    operation,
                    (
                        "POST",
                        "/{resource}/{operation}",
                        "{operation}_{resource}",
                        "Run {operation} for {resource}",
                    ),
                )
                schema_prefix = _title_from_resource(resource.rstrip("s"))
                request_body = None if method in {"GET", "DELETE"} else f"{schema_prefix}Request"
                response_body = (
                    f"{schema_prefix}ListResponse"
                    if operation == "list"
                    else f"{schema_prefix}Response"
                )
                endpoints.append(
                    {
                        "method": method,
                        "path": path_template.replace("{resource}", resource).replace(
                            "{operation}", operation
                        ),
                        "operation_id": operation_id_template.format(
                            resource=resource, operation=operation
                        ),
                        "purpose": purpose_template.format(resource=resource, operation=operation),
                        "request_body": request_body,
                        "response_body": response_body,
                        "auth_required": False,
                        "errors": ["400", "404", "500"],
                    }
                )
            resources.append(
                {
                    "name": resource,
                    "description": api_need.get("description") or f"Manage {resource}",
                    "endpoints": endpoints,
                }
            )

    schemas: list[dict[str, Any]] = []
    if isinstance(domain_entities, list):
        for entity in domain_entities:
            if not isinstance(entity, dict) or not isinstance(entity.get("name"), str):
                continue
            name = entity["name"]
            schemas.append(
                {
                    "name": f"{name}Response",
                    "fields": _normalize_fields(entity.get("fields")),
                }
            )

    return {
        "base_path": "/api/v1",
        "resources": resources,
        "schemas": schemas,
        "error_model": {
            "name": "ApiError",
            "fields": [
                {"name": "code", "type": "string", "required": True},
                {"name": "message", "type": "string", "required": True},
                {"name": "details", "type": "object", "required": False},
            ],
        },
        "notes": ["This is a draft API contract generated from the project blueprint."],
    }


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApiContractValidationError(f"API contract {field_name} is required.")
    return value.strip()


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
