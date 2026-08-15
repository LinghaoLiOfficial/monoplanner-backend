from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.schemas.tech_stack import TechStackItem, TechStackType

STACK_TYPES: set[str] = {
    "framework",
    "language",
    "ui_library",
    "package_manager",
    "database",
    "orm",
    "migration_tool",
    "runtime",
    "build_tool",
}

_STACK_SPLIT_RE = re.compile(r"\s+\+\s+|[,，、；;\n]")
_TYPE_PATTERNS: list[tuple[TechStackType, tuple[str, ...]]] = [
    (
        "orm",
        (
            r"\bprisma\b",
            r"\bsqlalchemy\b",
            r"\bsqlmodel\b",
            r"\btypeorm\b",
            r"\bdrizzle\b",
            r"\bsequelize\b",
            r"\bpeewee\b",
            r"\belm\b",
        ),
    ),
    ("migration_tool", (r"\balembic\b", r"\bflyway\b", r"\bliquibase\b", r"\bdrizzle kit\b")),
    ("package_manager", (r"\bpnpm\b", r"\bnpm\b", r"\byarn\b", r"\bbun\b")),
    (
        "runtime",
        (r"\bnode\.?js\b", r"\bpython\b", r"\bdeno\b", r"\bbun\b", r"\buvicorn\b"),
    ),
    ("build_tool", (r"\bvite\b", r"\bwebpack\b", r"\bturbopack\b", r"\besbuild\b", r"\brollup\b")),
    (
        "database",
        (r"\bpostgres(?:ql)?\b", r"\bmysql\b", r"\bsqlite\b", r"\bmongodb\b", r"\bredis\b"),
    ),
    (
        "language",
        (
            r"\btypescript\b",
            r"\bjavascript\b",
            r"\bpython\b",
            r"\bgo\b",
            r"\bjava\b",
            r"\bkotlin\b",
            r"\bruby\b",
            r"\bphp\b",
            r"\brust\b",
        ),
    ),
    (
        "ui_library",
        (
            r"\breact\b",
            r"\bvue\b",
            r"\bsvelte\b",
            r"\bshadcn/?ui\b",
            r"\btailwind(?: css)?\b",
            r"\bmui\b",
            r"\bchakra\b",
            r"\bantd\b",
            r"\bradix\b",
            r"\blucide\b",
        ),
    ),
    (
        "framework",
        (
            r"\bnext\.?js\b",
            r"\bnuxt\b",
            r"\bremix\b",
            r"\bsveltekit\b",
            r"\bangular\b",
            r"\bastro\b",
            r"\blitestar\b",
            r"\bdjango\b",
            r"\bfastapi\b",
            r"\bflask\b",
            r"\bgin\b",
            r"\becho\b",
            r"\brails\b",
            r"\blaravel\b",
        ),
    ),
]


def normalize_stack_text(value: str | None, default: str) -> str:
    if value is None:
        return default
    normalized = value.strip()
    return normalized or default


def split_legacy_stack_text(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in _STACK_SPLIT_RE.split(value) if item.strip()]


def infer_tech_stack_type(name: str) -> TechStackType:
    lowered = name.strip().lower()
    for type_name, patterns in _TYPE_PATTERNS:
        if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns):
            return type_name
    return "framework"


def _coerce_tags(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_tech_stack_item(value: Any, *, infer_missing_type: bool = False) -> TechStackItem | None:
    if isinstance(value, TechStackItem):
        return value
    if isinstance(value, str):
        name = value.strip()
        if not name:
            return None
        return TechStackItem(name=name, type=infer_tech_stack_type(name))
    if not isinstance(value, dict):
        return None
    raw_name = value.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    name = raw_name.strip()
    raw_type = value.get("type")
    if isinstance(raw_type, str) and raw_type.strip() in STACK_TYPES:
        stack_type = raw_type.strip()
    elif infer_missing_type:
        stack_type = infer_tech_stack_type(name)
    else:
        raise ValueError(f"Missing tech stack type for {name}.")
    return TechStackItem(
        name=name,
        type=stack_type,
        tags=_coerce_tags(value.get("tags")),
        role=value.get("role") if isinstance(value.get("role"), str) else None,
    )


def normalize_tech_stack_items(
    value: Any,
    *,
    infer_missing_type: bool = False,
) -> list[TechStackItem]:
    raw_items: list[Any]
    if value is None:
        raw_items = []
    elif isinstance(value, str):
        raw_items = split_legacy_stack_text(value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]

    normalized: list[TechStackItem] = []
    seen: set[tuple[str, str, tuple[str, ...], str | None]] = set()
    for raw_item in raw_items:
        item = normalize_tech_stack_item(raw_item, infer_missing_type=infer_missing_type)
        if item is None:
            continue
        signature = (item.name.lower(), item.type, tuple(item.tags), item.role)
        if signature in seen:
            continue
        seen.add(signature)
        normalized.append(item)
    return normalized


def tech_stack_items_to_text(items: Iterable[TechStackItem]) -> str:
    names = []
    for item in items:
        if isinstance(item, TechStackItem):
            name = item.name.strip()
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            name = item["name"].strip()
        else:
            continue
        if name:
            names.append(name)
    return " + ".join(names)


def tech_stack_items_to_payload(items: Iterable[TechStackItem]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, TechStackItem):
            payload.append(item.model_dump())
        elif isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("type"), str):
            payload.append(
                {
                    "name": item["name"].strip(),
                    "type": item["type"],
                    "tags": _coerce_tags(item.get("tags")),
                    "role": item.get("role") if isinstance(item.get("role"), str) else None,
                }
            )
    return payload
