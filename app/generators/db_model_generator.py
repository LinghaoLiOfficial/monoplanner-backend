from typing import Any

from app.llm.json_client import generate_json
from app.prompts.db_model_generator import build_db_model_generation_prompt
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput


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
                    "required": not nullable,
                    "primary_key": name == "id",
                    "nullable": nullable,
                }
            )
    if "id" not in seen:
        fields.insert(
            0,
            {
                "name": "id",
                "type": "uuid",
                "required": True,
                "primary_key": True,
                "nullable": False,
            },
        )
    for audit_field in ("created_at", "updated_at"):
        if audit_field not in seen:
            fields.append(
                {
                    "name": audit_field,
                    "type": "datetime",
                    "required": True,
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
    prompt = build_db_model_generation_prompt(project, blueprint_content, api_contract_content)
    content = generate_json(
        system_prompt=prompt.system,
        user_payload=prompt.user,
        response_model=DbModelOutput,
    )
    return validate_db_model_content(content)


def validate_db_model_content(content: dict[str, Any]) -> dict[str, Any]:
    database = content.get("database")
    if not isinstance(database, dict):
        raise DbModelValidationError("DB model database is required.")
    tables = content.get("database_tables")
    if not isinstance(tables, list):
        legacy_entities = content.get("entities")
        if isinstance(legacy_entities, list):
            tables = legacy_entities
        else:
            raise DbModelValidationError("DB model database_tables must be a list.")

    normalized_tables = []
    for table in tables:
        if not isinstance(table, dict):
            raise DbModelValidationError("DB model database_table must be an object.")
        fields = table.get("fields")
        if not isinstance(fields, list):
            raise DbModelValidationError("DB model database_table fields must be a list.")
        table_name_source = _require_string(
            table.get("name") or table.get("table_name"),
            "database_tables.name",
        )
        normalized_tables.append(
            {
                "name": table_name_source,
                "table_name": _string_or_default(
                    table.get("table_name"),
                    _to_table_name(table_name_source),
                ),
                "description": _string_or_default(table.get("description"), ""),
                "fields": _normalize_model_fields(fields),
                "relationships": table.get("relationships")
                if isinstance(table.get("relationships"), list)
                else [],
                "indexes": _normalize_indexes(table.get("indexes")),
                "migration_notes": _string_list(table.get("migration_notes")),
            }
        )

    return {
        "database": {
            "engine": _string_or_default(database.get("engine"), "PostgreSQL"),
            "orm": _string_or_default(database.get("orm"), "SQLAlchemy 2.x"),
            "migration_tool": _string_or_default(database.get("migration_tool"), "Alembic"),
        },
        "database_tables": normalized_tables,
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
                "required": bool(
                    field.get("required", not bool(field.get("nullable", name != "id")))
                ),
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
                "required": True,
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
                    "required": True,
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
    tables: list[dict[str, Any]] = []
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
            tables.append(
                {
                    "name": name,
                    "table_name": table_name,
                    "description": entity.get("description") or f"{name} domain entity",
                    "fields": fields,
                    "relationships": entity_relationships,
                    "indexes": [
                        index for index in indexes if index.get("table") == table_name
                    ],
                    "migration_notes": [],
                }
            )

    return {
        "database": {
            "engine": "PostgreSQL",
            "orm": "SQLAlchemy 2.x",
            "migration_tool": "Alembic",
        },
        "database_tables": tables,
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
