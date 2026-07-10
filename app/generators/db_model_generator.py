from typing import Any

from app.llm.json_client import generate_json, should_use_real_llm


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


def build_db_model_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    if should_use_real_llm():
        return build_llm_db_model_content(blueprint_content)
    return _build_rule_based_db_model_content(blueprint_content)


def build_llm_db_model_content(blueprint_content: dict[str, Any]) -> dict[str, Any]:
    return generate_json(
        system_prompt=(
            "You are a senior database architect. Generate a PostgreSQL data model draft as "
            "strict JSON from the project blueprint. Return only one JSON object, no markdown. "
            "The object must contain database, entities, relationships, indexes, and "
            "migration_notes."
        ),
        user_payload={
            "blueprint": blueprint_content,
            "output_contract": {
                "database": {
                    "engine": "PostgreSQL",
                    "orm": "SQLAlchemy 2.x",
                    "migration_tool": "Alembic",
                },
                "entities": [
                    {
                        "name": "PascalCase",
                        "table_name": "snake_case_plural",
                        "description": "string",
                        "fields": [
                            {
                                "name": "snake_case",
                                "type": "uuid|string|text|integer|number|boolean|datetime|json",
                                "primary_key": False,
                                "nullable": False,
                            }
                        ],
                        "relationships": [
                            {
                                "from": "EntityName",
                                "to": "EntityName",
                                "type": "one_to_many|many_to_one|many_to_many|one_to_one",
                                "description": "string",
                            }
                        ],
                    }
                ],
                "relationships": [
                    {
                        "from": "EntityName",
                        "to": "EntityName",
                        "type": "many_to_one",
                        "description": "string",
                    }
                ],
                "indexes": [{"table": "table_name", "fields": ["field_name"], "reason": "string"}],
                "migration_notes": ["string"],
            },
        },
    )


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
