from typing import Any

from app.llm.json_client import generate_json, should_use_real_llm

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


def build_api_contract_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    if should_use_real_llm():
        return build_llm_api_contract_content(blueprint_content)
    return _build_rule_based_api_contract_content(blueprint_content)


def build_llm_api_contract_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    content = generate_json(
        system_prompt=(
            "You are a senior backend API architect. Generate a REST API contract as strict "
            "JSON from the project blueprint. Return only one JSON object, no markdown. The "
            "object must contain base_path, resources, schemas, error_model, and notes."
        ),
        user_payload={
            "blueprint": blueprint_content,
            "output_contract": {
                "base_path": "/api/v1",
                "resources": [
                    {
                        "name": "plural resource name",
                        "description": "string",
                        "endpoints": [
                            {
                                "method": "GET|POST|PATCH|DELETE",
                                "path": "/resource/{id}",
                                "operation_id": "snake_case",
                                "purpose": "string",
                                "request_body": "SchemaName|null",
                                "response_body": "SchemaName",
                                "auth_required": False,
                                "errors": ["400", "404", "500"],
                            }
                        ],
                    }
                ],
                "schemas": [
                    {
                        "name": "SchemaName",
                        "fields": [
                            {
                                "name": "snake_case",
                                "type": "string|uuid|integer|number|boolean|datetime|object|array",
                                "required": True,
                                "description": "string",
                            }
                        ],
                    }
                ],
                "error_model": {
                    "name": "ApiError",
                    "fields": [
                        {"name": "code", "type": "string", "required": True},
                        {"name": "message", "type": "string", "required": True},
                    ],
                },
                "notes": ["string"],
            },
        },
    )
    content.setdefault("base_path", "/api/v1")
    return content


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
