from typing import Any

from app.llm.json_client import generate_json
from app.prompts.db_model_generator import SYSTEM_PROMPT, build_db_model_generation_payload


class DbModelValidationError(ValueError):
    """Raised when LLM DB model output does not match the expected shape."""


def _to_table_name(entity_name: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(entity_name):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    table = "".join(chars)
    return table if table.endswith("s") else f"{table}s"


def _field_type(field_name: str) -> str:
    lower = field_name.lower()
    if lower == "id" or lower.endswith("_id"):
        return "uuid"
    if lower.endswith("_at"):
        return "datetime"
    if lower in {"status", "language", "source_type", "name", "title"}:
        return "string"
    if lower.startswith("is_") or lower.startswith("has_"):
        return "boolean"
    return "text"


def _normalize_fields(raw_fields: Any) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw_fields, list):
        for raw_field in raw_fields:
            if isinstance(raw_field, str):
                name = raw_field
                field_type = _field_type(name)
                nullable = name not in {"id", "name"} and not name.endswith("_id")
            elif isinstance(raw_field, dict) and isinstance(raw_field.get("name"), str):
                name = raw_field["name"]
                field_type = raw_field.get("type") or _field_type(name)
                nullable = bool(raw_field.get("nullable", name not in {"id", "name"}))
            else:
                continue
            seen.add(name)
            fields.append(
                {
                    "name": name,
                    "type": field_type,
                    "primary_key": name == "id",
                    "nullable": nullable,
                }
            )
    if "id" not in seen:
        fields.insert(0, {"name": "id", "type": "uuid", "primary_key": True, "nullable": False})
    for audit_field in ("created_at", "updated_at"):
        if audit_field not in seen:
            fields.append(
                {
                    "name": audit_field,
                    "type": "datetime",
                    "primary_key": False,
                    "nullable": False,
                }
            )
    return fields


def build_db_model_content(
    project: Any,
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_llm_db_model_content(project, blueprint_content, api_contract_content)


def build_llm_db_model_content(
    project: Any,
    blueprint_content: dict[str, Any],
    api_contract_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = generate_json(
        system_prompt=SYSTEM_PROMPT,
        user_payload=build_db_model_generation_payload(
            project,
            blueprint_content,
            api_contract_content,
        ),
    )
    return validate_db_model_content(content)


def validate_db_model_content(content: dict[str, Any]) -> dict[str, Any]:
    database = content.get("database")
    if not isinstance(database, dict):
        raise DbModelValidationError("DB model database is required.")
    entities = content.get("entities")
    if not isinstance(entities, list):
        raise DbModelValidationError("DB model entities must be a list.")

    normalized_entities = []
    for entity in entities:
        if not isinstance(entity, dict):
            raise DbModelValidationError("DB model entity must be an object.")
        fields = entity.get("fields")
        if not isinstance(fields, list):
            raise DbModelValidationError("DB model entity fields must be a list.")
        normalized_entities.append(
            {
                "name": _require_string(entity.get("name"), "entities.name"),
                "table_name": _string_or_default(
                    entity.get("table_name"),
                    _to_table_name(_require_string(entity.get("name"), "entities.name")),
                ),
                "description": _string_or_default(entity.get("description"), ""),
                "fields": _normalize_model_fields(fields),
                "relationships": entity.get("relationships")
                if isinstance(entity.get("relationships"), list)
                else [],
            }
        )

    return {
        "database": {
            "engine": _string_or_default(database.get("engine"), "PostgreSQL"),
            "orm": _string_or_default(database.get("orm"), "SQLAlchemy 2.x"),
            "migration_tool": _string_or_default(database.get("migration_tool"), "Alembic"),
        },
        "entities": normalized_entities,
        "relationships": content.get("relationships")
        if isinstance(content.get("relationships"), list)
        else [],
        "indexes": _normalize_indexes(content.get("indexes")),
        "migration_notes": _string_list(content.get("migration_notes")),
    }


def _normalize_model_fields(fields: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    seen: set[str] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise DbModelValidationError("DB model field must be an object.")
        name = _require_string(field.get("name"), "entities.fields.name")
        seen.add(name)
        normalized.append(
            {
                "name": name,
                "type": _require_string(field.get("type"), "entities.fields.type"),
                "primary_key": bool(field.get("primary_key", name == "id")),
                "nullable": bool(field.get("nullable", name != "id")),
                "description": _string_or_default(field.get("description"), ""),
            }
        )
    if "id" not in seen:
        normalized.insert(
            0,
            {
                "name": "id",
                "type": "uuid",
                "primary_key": True,
                "nullable": False,
                "description": "Primary key",
            },
        )
    for audit_field in ("created_at", "updated_at"):
        if audit_field not in seen:
            normalized.append(
                {
                    "name": audit_field,
                    "type": "datetime",
                    "primary_key": False,
                    "nullable": False,
                    "description": f"{audit_field} audit timestamp",
                }
            )
    return normalized


def _normalize_indexes(indexes: Any) -> list[dict[str, Any]]:
    if not isinstance(indexes, list):
        return []
    normalized = []
    for index in indexes:
        if not isinstance(index, dict):
            raise DbModelValidationError("DB model index must be an object.")
        normalized.append(
            {
                "table": _require_string(index.get("table"), "indexes.table"),
                "fields": _string_list(index.get("fields")),
                "reason": _require_string(index.get("reason"), "indexes.reason"),
            }
        )
    return normalized


def _build_rule_based_db_model_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    domain_entities = blueprint_content.get("domain_entities")
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    indexes: list[dict[str, Any]] = []

    entity_names: set[str] = set()
    if isinstance(domain_entities, list):
        for entity in domain_entities:
            if isinstance(entity, dict) and isinstance(entity.get("name"), str):
                entity_names.add(entity["name"])

    if isinstance(domain_entities, list):
        for entity in domain_entities:
            if not isinstance(entity, dict) or not isinstance(entity.get("name"), str):
                continue
            name = entity["name"]
            table_name = _to_table_name(name)
            fields = _normalize_fields(entity.get("fields"))
            entity_relationships: list[dict[str, str]] = []
            for field in fields:
                field_name = field["name"]
                if not field_name.endswith("_id") or field_name == "id":
                    continue
                target_name = "".join(
                    part.capitalize() for part in field_name.removesuffix("_id").split("_")
                )
                if target_name in entity_names:
                    relationship = {
                        "from": name,
                        "to": target_name,
                        "type": "many_to_one",
                        "description": f"A {name} belongs to a {target_name}.",
                    }
                    relationships.append(relationship)
                    entity_relationships.append(relationship)
                    indexes.append(
                        {
                            "table": table_name,
                            "fields": [field_name],
                            "reason": f"Speed up lookup by {field_name}.",
                        }
                    )
            entities.append(
                {
                    "name": name,
                    "table_name": table_name,
                    "description": entity.get("description") or f"{name} domain entity",
                    "fields": fields,
                    "relationships": entity_relationships,
                }
            )

    return {
        "database": {
            "engine": "PostgreSQL",
            "orm": "SQLAlchemy 2.x",
            "migration_tool": "Alembic",
        },
        "entities": entities,
        "relationships": relationships,
        "indexes": indexes,
        "migration_notes": [
            "Use Alembic to create migration files.",
            "Use UUID primary keys.",
            "Keep service-layer business logic out of FastAPI routes.",
        ],
    }


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DbModelValidationError(f"DB model {field_name} is required.")
    return value.strip()


def _string_or_default(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
