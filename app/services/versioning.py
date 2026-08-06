from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from sqlalchemy import inspect

VERSIONED_INTERNAL_FIELDS = {"id", "created_at", "updated_at"}
DIFF_KEYS = ("added", "modified", "removed")


def clone_versioned_row(
    instance: Any,
    updates: dict[str, Any],
    *,
    allowed_fields: set[str],
) -> dict[str, Any]:
    state = inspect(instance)
    data: dict[str, Any] = {
        column.key: deepcopy(getattr(instance, column.key))
        for column in state.mapper.columns
        if column.key not in VERSIONED_INTERNAL_FIELDS
    }
    data["version"] = int(getattr(instance, "version", 0)) + 1
    for field, value in updates.items():
        if field in allowed_fields:
            data[field] = value
    if "diff_from_previous" not in updates or updates.get("diff_from_previous") is None:
        data["diff_from_previous"] = build_version_diff(instance, data)
    else:
        data["diff_from_previous"] = normalize_diff(updates["diff_from_previous"])
    return data


def build_version_diff(previous: Any, next_data: dict[str, Any]) -> dict[str, list[str]]:
    previous_data = _versioned_data_map(previous)
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []

    all_keys = sorted((set(previous_data) | set(next_data)) - VERSIONED_INTERNAL_FIELDS)
    for key in all_keys:
        if key in VERSIONED_INTERNAL_FIELDS:
            continue
        if key not in previous_data:
            added.append(key)
            continue
        if key not in next_data:
            removed.append(key)
            continue
        _diff_value(previous_data[key], next_data[key], key, added, modified, removed)

    return {"added": added, "modified": modified, "removed": removed}


def normalize_diff(diff: Any) -> dict[str, list[str]]:
    if not isinstance(diff, dict):
        return {"added": [], "modified": [], "removed": []}
    normalized = {}
    for key in DIFF_KEYS:
        value = diff.get(key, [])
        if isinstance(value, list):
            normalized[key] = [str(item) for item in value]
        elif value is None:
            normalized[key] = []
        elif isinstance(value, (tuple, set)):
            normalized[key] = [str(item) for item in value]
        else:
            normalized[key] = [str(value)]
    return normalized


def _versioned_data_map(instance: Any) -> dict[str, Any]:
    state = inspect(instance)
    return {
        column.key: deepcopy(getattr(instance, column.key))
        for column in state.mapper.columns
        if column.key not in VERSIONED_INTERNAL_FIELDS
    }


def _diff_value(
    previous: Any,
    next_value: Any,
    path: str,
    added: list[str],
    modified: list[str],
    removed: list[str],
) -> None:
    if isinstance(previous, dict) and isinstance(next_value, dict):
        previous_keys = set(previous)
        next_keys = set(next_value)
        for key in sorted(next_keys - previous_keys):
            added.append(f"{path}.{key}")
        for key in sorted(previous_keys - next_keys):
            removed.append(f"{path}.{key}")
        for key in sorted(previous_keys & next_keys):
            _diff_value(previous[key], next_value[key], f"{path}.{key}", added, modified, removed)
        return

    if isinstance(previous, list) and isinstance(next_value, list):
        if previous != next_value:
            modified.append(path)
        return

    if previous != next_value:
        modified.append(path)


def merge_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
