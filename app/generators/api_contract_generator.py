from typing import Any

from app.llm.json_client import generate_json
from app.prompts.api_contract_generator import SYSTEM_PROMPT, build_api_contract_generation_payload

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
    content = generate_json(
        system_prompt=SYSTEM_PROMPT,
        user_payload=build_api_contract_generation_payload(project, blueprint_content),
    )
    return validate_api_contract_content(content)


def validate_api_contract_content(content: dict[str, Any]) -> dict[str, Any]:
    base_path = content.get("base_path")
    if not isinstance(base_path, str) or not base_path.startswith("/"):
        raise ApiContractValidationError("API contract base_path is required.")
    resources = content.get("resources")
    if not isinstance(resources, list):
        raise ApiContractValidationError("API contract resources must be a list.")
    schemas = content.get("schemas")
    if not isinstance(schemas, list):
        raise ApiContractValidationError("API contract schemas must be a list.")

    normalized_resources = []
    for resource in resources:
        if not isinstance(resource, dict):
            raise ApiContractValidationError("API contract resource must be an object.")
        endpoints = resource.get("endpoints")
        if not isinstance(endpoints, list):
            raise ApiContractValidationError("API contract resource endpoints must be a list.")
        normalized_endpoints = [_normalize_endpoint(endpoint) for endpoint in endpoints]
        normalized_resources.append(
            {
                "name": _require_string(resource.get("name"), "resources.name"),
                "description": _string_or_default(resource.get("description"), ""),
                "endpoints": normalized_endpoints,
            }
        )

    normalized_schemas = []
    for schema in schemas:
        if not isinstance(schema, dict):
            raise ApiContractValidationError("API contract schema must be an object.")
        normalized_schemas.append(
            {
                "name": _require_string(schema.get("name"), "schemas.name"),
                "fields": _normalize_schema_fields(schema.get("fields")),
            }
        )

    error_model = content.get("error_model")
    if not isinstance(error_model, dict):
        error_model = {
            "name": "ApiError",
            "fields": [
                {"name": "code", "type": "string", "required": True},
                {"name": "message", "type": "string", "required": True},
                {"name": "details", "type": "object", "required": False},
            ],
        }

    return {
        "base_path": base_path.rstrip("/") if base_path != "/" else base_path,
        "resources": normalized_resources,
        "schemas": normalized_schemas,
        "error_model": error_model,
        "notes": _string_list(content.get("notes")),
    }


def _normalize_endpoint(endpoint: Any) -> dict[str, Any]:
    if not isinstance(endpoint, dict):
        raise ApiContractValidationError("API contract endpoint must be an object.")
    method = _require_string(endpoint.get("method"), "endpoints.method").upper()
    if method not in VALID_METHODS:
        raise ApiContractValidationError("API contract endpoint method is invalid.")
    return {
        "method": method,
        "path": _require_string(endpoint.get("path"), "endpoints.path"),
        "operation_id": _string_or_default(endpoint.get("operation_id"), ""),
        "purpose": _require_string(endpoint.get("purpose"), "endpoints.purpose"),
        "request_body": endpoint.get("request_body"),
        "response_body": endpoint.get("response_body"),
        "auth_required": bool(endpoint.get("auth_required", True)),
        "errors": _string_list(endpoint.get("errors")),
    }


def _normalize_schema_fields(fields: Any) -> list[dict[str, Any]]:
    if not isinstance(fields, list):
        return []
    normalized = []
    for field in fields:
        if not isinstance(field, dict):
            raise ApiContractValidationError("API contract schema field must be an object.")
        normalized.append(
            {
                "name": _require_string(field.get("name"), "schemas.fields.name"),
                "type": _string_or_default(field.get("type"), "string"),
                "required": bool(field.get("required", False)),
                "description": _string_or_default(field.get("description"), ""),
            }
        )
    return normalized


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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
