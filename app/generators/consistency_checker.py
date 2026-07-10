from typing import Any


def _resource_names(api_contract_content: dict[str, Any] | None) -> set[str]:
    resources = (api_contract_content or {}).get("resources")
    if not isinstance(resources, list):
        return set()
    return {
        item["name"]
        for item in resources
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _api_need_resources(blueprint_content: dict[str, Any] | None) -> set[str]:
    api_needs = (blueprint_content or {}).get("api_needs")
    if not isinstance(api_needs, list):
        return set()
    return {
        item["resource"]
        for item in api_needs
        if isinstance(item, dict) and isinstance(item.get("resource"), str)
    }


def _entity_names_from_blueprint(blueprint_content: dict[str, Any] | None) -> set[str]:
    entities = (blueprint_content or {}).get("domain_entities")
    if not isinstance(entities, list):
        return set()
    return {
        item["name"]
        for item in entities
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _entity_names_from_db_model(db_model_content: dict[str, Any] | None) -> set[str]:
    entities = (db_model_content or {}).get("entities")
    if not isinstance(entities, list):
        return set()
    return {
        item["name"]
        for item in entities
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def check_consistency(
    blueprint_content: dict[str, Any] | None,
    api_contract_content: dict[str, Any] | None,
    db_model_content: dict[str, Any] | None,
    context_pack_roles: set[str],
) -> dict[str, Any]:
    items: list[dict[str, str]] = []

    if blueprint_content is None:
        items.append(
            {
                "level": "error",
                "code": "BLUEPRINT_MISSING",
                "message": "Project does not have a blueprint.",
                "source": "blueprint",
            }
        )
    else:
        items.append(
            {
                "level": "info",
                "code": "BLUEPRINT_EXISTS",
                "message": "Blueprint exists.",
                "source": "blueprint",
            }
        )
        for key in ("pages", "domain_entities", "api_needs"):
            if not blueprint_content.get(key):
                items.append(
                    {
                        "level": "warning",
                        "code": f"BLUEPRINT_{key.upper()}_MISSING",
                        "message": f"Blueprint does not contain {key}.",
                        "source": "blueprint",
                    }
                )

    blueprint_resources = _api_need_resources(blueprint_content)
    for resource in sorted(_resource_names(api_contract_content) - blueprint_resources):
        items.append(
            {
                "level": "warning",
                "code": "API_RESOURCE_NOT_IN_BLUEPRINT",
                "message": f"API resource '{resource}' is not present in blueprint.api_needs.",
                "source": "api_contract",
            }
        )

    blueprint_entities = _entity_names_from_blueprint(blueprint_content)
    for entity in sorted(_entity_names_from_db_model(db_model_content) - blueprint_entities):
        items.append(
            {
                "level": "warning",
                "code": "DB_ENTITY_NOT_IN_BLUEPRINT",
                "message": f"DB entity '{entity}' is not present in blueprint.domain_entities.",
                "source": "db_model",
            }
        )

    required_roles = {"frontend_engineer", "backend_engineer"}
    missing_roles = required_roles - context_pack_roles
    for role in sorted(missing_roles):
        items.append(
            {
                "level": "warning",
                "code": "CONTEXT_PACK_ROLE_MISSING",
                "message": f"Context pack role '{role}' has not been generated.",
                "source": "context_pack",
            }
        )

    levels = {item["level"] for item in items}
    status = "failed" if "error" in levels else "warning" if "warning" in levels else "passed"
    return {"status": status, "items": items}
