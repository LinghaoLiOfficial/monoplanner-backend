from __future__ import annotations

from typing import Any

from app.prompts.renderer import RenderedPrompt, render_prompt_template

ORDERED_AFFECTED_LAYERS = [
    "ux_design",
    "ui_design",
    "frontend_pages",
    "frontend_tools",
    "api_contract",
    "backend_services",
    "backend_tools",
    "database_models",
    "project_blueprint",
    "prompt_assets",
]

MODULE_CHANGE_CONTRACT = {
    layer: {"added": [], "modified": [], "removed": [], "unchanged": []}
    for layer in ORDERED_AFFECTED_LAYERS
}

SYSTEM_PROMPT = "orchestration"


def build_change_set_payload(
    *,
    layer: str | None = None,
    project_config: dict[str, Any],
    selected_story: dict[str, Any],
    current_assets: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "generate_change_set",
        "layer": layer,
        "project_config": project_config,
        "selected_story": selected_story,
        "current_assets": current_assets,
    }


def build_change_set_prompt(
    *,
    layer: str | None = None,
    project_config: dict[str, Any],
    selected_story: dict[str, Any],
    current_assets: dict[str, Any],
) -> RenderedPrompt:
    return render_prompt_template(
        "change_set",
        build_change_set_payload(
            layer=layer,
            project_config=project_config,
            selected_story=selected_story,
            current_assets=current_assets,
        ),
    )


def build_design_asset_payload(
    *,
    layer: str,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_set: dict[str, Any],
    previous_version: dict[str, Any] | None,
    related_assets: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "generate_design_asset",
        "layer": layer,
        "project_config": project_config,
        "selected_story": selected_story,
        "change_set": change_set,
        "previous_version": previous_version,
        "related_assets": related_assets,
    }


def build_design_asset_prompt(
    *,
    layer: str,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_set: dict[str, Any],
    previous_version: dict[str, Any] | None,
    related_assets: dict[str, Any],
) -> RenderedPrompt:
    template_name = (
        "backend_implementation"
        if layer == "backend_services"
        else layer
        if layer in {"ux_design", "ui_design", "frontend_pages"}
        else "design_asset"
    )
    return render_prompt_template(
        template_name,
        build_design_asset_payload(
            layer=layer,
            project_config=project_config,
            selected_story=selected_story,
            change_set=change_set,
            previous_version=previous_version,
            related_assets=related_assets,
        ),
    )
def build_blueprint_summary_payload(
    *,
    project_config: dict[str, Any],
    business_stories: list[dict[str, Any]],
    design_assets: dict[str, Any],
    latest_change_set: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "summarize_project_blueprint",
        "project_config": project_config,
        "business_stories": business_stories,
        "design_assets": design_assets,
        "latest_change_set": latest_change_set,
    }


def build_blueprint_summary_prompt(
    *,
    project_config: dict[str, Any],
    business_stories: list[dict[str, Any]],
    design_assets: dict[str, Any],
    latest_change_set: dict[str, Any],
) -> RenderedPrompt:
    return render_prompt_template(
        "blueprint_summary",
        build_blueprint_summary_payload(
            project_config=project_config,
            business_stories=business_stories,
            design_assets=design_assets,
            latest_change_set=latest_change_set,
        ),
    )


def build_prompt_pack_payload(
    *,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_set: dict[str, Any] | None = None,
    change_sets: list[dict[str, Any]] | None = None,
    old_versions: dict[str, Any],
    new_versions: dict[str, Any],
    project_blueprint: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "generate_prompt_pack",
        "project_config": project_config,
        "selected_story": selected_story,
        "change_set": change_set or {},
        "change_sets": change_sets or ([] if change_set is None else [change_set]),
        "old_versions": old_versions,
        "new_versions": new_versions,
        "project_blueprint": project_blueprint,
        "prompt_preferences": project_config.get("prompt_preferences", []),
    }


def build_prompt_pack_prompt(
    *,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_set: dict[str, Any] | None = None,
    change_sets: list[dict[str, Any]] | None = None,
    old_versions: dict[str, Any],
    new_versions: dict[str, Any],
    project_blueprint: dict[str, Any],
) -> RenderedPrompt:
    return render_prompt_template(
        "prompt_pack",
        build_prompt_pack_payload(
            project_config=project_config,
            selected_story=selected_story,
            change_set=change_set,
            change_sets=change_sets,
            old_versions=old_versions,
            new_versions=new_versions,
            project_blueprint=project_blueprint,
        ),
    )
