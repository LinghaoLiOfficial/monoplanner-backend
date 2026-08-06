from __future__ import annotations

from typing import Any

from app.prompts.renderer import RenderedPrompt, render_prompt_template
from app.prompts.templates.blueprint_summary.output_schema import BlueprintSummaryOutput
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.prompts.templates.design_asset.output_schema import DesignAssetOutput
from app.prompts.templates.frontend_pages.output_schema import FrontendPagesOutput
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.prompts.templates.ui_design.output_schema import UIDesignOutput
from app.prompts.templates.ux_design.output_schema import UXDesignOutput

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
    project_config: dict[str, Any],
    selected_story: dict[str, Any],
    current_assets: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "generate_change_set",
        "project_config": project_config,
        "selected_story": selected_story,
        "current_assets": current_assets,
        "output_contract": ChangeSetOutput.model_json_schema(),
    }


def build_change_set_prompt(
    *,
    project_config: dict[str, Any],
    selected_story: dict[str, Any],
    current_assets: dict[str, Any],
) -> RenderedPrompt:
    return render_prompt_template(
        "change_set",
        build_change_set_payload(
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
        "output_contract": _design_asset_output_contract(layer),
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
        layer if layer in {"ux_design", "ui_design", "frontend_pages"} else "design_asset"
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


def _design_asset_output_contract(layer: str) -> dict[str, Any]:
    if layer == "ux_design":
        return UXDesignOutput.model_json_schema()
    if layer == "ui_design":
        return UIDesignOutput.model_json_schema()
    if layer == "frontend_pages":
        return FrontendPagesOutput.model_json_schema()
    return DesignAssetOutput.model_json_schema()


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
        "output_contract": BlueprintSummaryOutput.model_json_schema(),
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
    change_set: dict[str, Any],
    old_versions: dict[str, Any],
    new_versions: dict[str, Any],
    project_blueprint: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": "generate_prompt_pack",
        "project_config": project_config,
        "selected_story": selected_story,
        "change_set": change_set,
        "old_versions": old_versions,
        "new_versions": new_versions,
        "project_blueprint": project_blueprint,
        "prompt_preferences": project_config.get("prompt_preferences", []),
        "output_contract": PromptPackOutput.model_json_schema(),
    }


def build_prompt_pack_prompt(
    *,
    project_config: dict[str, Any],
    selected_story: dict[str, Any] | None,
    change_set: dict[str, Any],
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
            old_versions=old_versions,
            new_versions=new_versions,
            project_blueprint=project_blueprint,
        ),
    )
