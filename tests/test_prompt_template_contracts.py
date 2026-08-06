import re
from types import SimpleNamespace

import pytest

from app.prompts.api_contract_generator import build_api_contract_generation_payload
from app.prompts.blueprint_generator import build_blueprint_generation_payload
from app.prompts.business_story_decomposer import build_business_story_decomposition_payload
from app.prompts.db_model_generator import build_db_model_generation_payload
from app.prompts.orchestration import (
    build_blueprint_summary_payload,
    build_change_set_payload,
    build_design_asset_payload,
    build_prompt_pack_payload,
)
from app.prompts.renderer import (
    PromptTemplateRenderError,
    render_prompt_template,
    split_rendered_prompt,
    tojson_pretty,
)
from app.prompts.template_registry import PROMPT_TEMPLATE_CONTRACTS
from app.prompts.templates.api_contract_generator.output_schema import ApiContractOutput
from app.prompts.templates.blueprint_generator.output_schema import ProjectBlueprintOutput
from app.prompts.templates.blueprint_summary.output_schema import BlueprintSummaryOutput
from app.prompts.templates.business_story_decomposer.output_schema import (
    BusinessStoryDecompositionOutput,
)
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.prompts.templates.context_pack.output_schema import ContextPackOutput
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput
from app.prompts.templates.design_asset.output_schema import DesignAssetOutput
from app.prompts.templates.frontend_pages.output_schema import FrontendPagesOutput
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.prompts.templates.ui_design.output_schema import UIDesignOutput
from app.prompts.templates.ux_design.output_schema import UXDesignOutput

REQUIRED_USER_SECTIONS = (
    "Input:",
    "Input Descriptions:",
    "Output Descriptions:",
)

EXPECTED_EXAMPLE_COUNTS = {
    "business_story_decomposer": 2,
    "change_set": 2,
    "prompt_pack": 2,
}


def test_prompt_template_files_exist_and_follow_runtime_structure() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        assert contract.template_path.is_file()
        assert contract.schema_path.is_file()
        template_text = contract.template_path.read_text(encoding="utf-8")
        assert "{{" in template_text
        assert template_text.count("===SYSTEM===") == 1
        assert template_text.count("===USER===") == 1
        assert template_text.find("===SYSTEM===") < template_text.find("===USER===")
        for section in REQUIRED_USER_SECTIONS:
            assert section in template_text
        expected_count = EXPECTED_EXAMPLE_COUNTS.get(contract.name, 1)
        input_examples = re.findall(r"Example Input \[(\d+)\]:", template_text)
        output_examples = re.findall(r"Example Output \[(\d+)\]:", template_text)
        assert len(input_examples) == expected_count
        assert output_examples == input_examples


def test_registered_templates_render_to_non_empty_system_and_user() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        rendered = render_prompt_template(contract.name, _template_variables(contract.name))
        assert rendered.system
        assert rendered.user
        assert "Input:" in rendered.user
        assert "Output Descriptions:" in rendered.user


def test_business_story_payload_uses_schema_model() -> None:
    project = SimpleNamespace(name="Demo", description="Demo project")
    requirement = SimpleNamespace(raw_text="Create tasks")

    payload = build_business_story_decomposition_payload(project, requirement)

    assert payload["target_output_schema"] == BusinessStoryDecompositionOutput.model_json_schema()


def test_core_prompt_payloads_use_their_matching_schema_models() -> None:
    project = SimpleNamespace(
        name="Demo",
        description="Demo project",
        target_frontend_stack="Frontend",
        target_backend_stack="Backend",
    )
    requirement = SimpleNamespace(
        id="req-1",
        raw_text="Create tasks",
        language="zh",
        source_type="manual",
    )
    blueprint_content = {"project": {}, "domain_entities": [], "pages": [], "api_needs": []}
    api_contract_content = {"base_path": "/api/v1", "resources": [], "schemas": []}

    blueprint_payload = build_blueprint_generation_payload(project, requirement, [])
    api_payload = build_api_contract_generation_payload(project, blueprint_content)
    db_payload = build_db_model_generation_payload(project, blueprint_content, api_contract_content)

    assert blueprint_payload["target_output_schema"] == ProjectBlueprintOutput.model_json_schema()
    assert api_payload["target_output_schema"] == ApiContractOutput.model_json_schema()
    assert db_payload["target_output_schema"] == DbModelOutput.model_json_schema()


def test_orchestration_payloads_use_schema_models() -> None:
    project_config = {"prompt_preferences": []}
    selected_story = {"title": "Story"}
    current_assets = {"ux_design": {}}
    design_assets = {"ux_design": {}}
    change_set = {"affected_layers": ["ux_design"]}

    assert build_change_set_payload(
        project_config=project_config,
        selected_story=selected_story,
        current_assets=current_assets,
    )["output_contract"] == ChangeSetOutput.model_json_schema()

    assert build_design_asset_payload(
        layer="ux_design",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )["output_contract"] == UXDesignOutput.model_json_schema()

    assert build_design_asset_payload(
        layer="ui_design",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )["output_contract"] == UIDesignOutput.model_json_schema()

    assert build_design_asset_payload(
        layer="frontend_pages",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )["output_contract"] == FrontendPagesOutput.model_json_schema()

    assert build_design_asset_payload(
        layer="backend_services",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )["output_contract"] == DesignAssetOutput.model_json_schema()

    assert build_blueprint_summary_payload(
        project_config=project_config,
        business_stories=[],
        design_assets=design_assets,
        latest_change_set=change_set,
    )["output_contract"] == BlueprintSummaryOutput.model_json_schema()

    assert build_prompt_pack_payload(
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        old_versions={},
        new_versions={},
        project_blueprint={},
    )["output_contract"] == PromptPackOutput.model_json_schema()


def test_context_pack_schema_shape() -> None:
    assert ContextPackOutput.model_json_schema()["properties"]["packs"]["type"] == "array"


def test_ui_design_output_accepts_new_visual_contract() -> None:
    output = UIDesignOutput.model_validate(
        {
            "title": "任务创建 UI 视觉设计",
            "summary": "定义任务创建页的视觉系统、布局和组件样式。",
            "content": {
                "version_summary": "新增任务创建视觉规则。",
                "visual_system": {
                    "design_style": {
                        "style_description": "清晰、工作台式、主操作突出。",
                        "signature_traits": ["紧凑表单", "错误就近展示"],
                    },
                    "design_principles": ["保持可读性", "状态反馈必须明确"],
                    "theme_configuration": {
                        "theme_types": {
                            "light_mode": "默认浅色主题。",
                            "dark_mode": "低光环境下保持对比度。",
                        },
                        "default_theme": "light_mode",
                    },
                    "color_system": ["primary 用于主操作"],
                    "typography_system": ["标题使用中等字重"],
                    "spacing_system": ["表单项保持紧凑间距"],
                    "shape_system": ["控件使用小圆角"],
                    "elevation_system": ["弹层使用轻量阴影"],
                    "interaction_visual_system": ["loading 状态保持按钮宽度"],
                },
                "layout_rules": [
                    {
                        "target_screen": "任务创建页",
                        "desktop_layout": "表单居中，辅助说明右侧展示。",
                        "mobile_layout": "单栏布局，主按钮全宽。",
                    }
                ],
                "component_style_rules": [
                    {
                        "component_name": "TaskForm",
                        "visual_priority": {
                            "primary_content": ["任务标题"],
                            "secondary_content": ["任务描述"],
                            "tertiary_content": ["帮助文本"],
                            "primary_actions": ["创建任务"],
                            "secondary_actions": ["取消"],
                            "danger_actions": ["清空表单"],
                        },
                        "style_rules": ["错误消息就近展示"],
                    }
                ],
                "diff": {"added": ["任务创建 UI 规则"], "modified": [], "removed": []},
            },
            "diff_from_previous": {"added": ["任务创建 UI 设计"], "modified": [], "removed": []},
        }
    )

    theme_types = output.content.visual_system.theme_configuration.theme_types
    visual_priority = output.content.component_style_rules[0].visual_priority
    assert theme_types.light_mode == "默认浅色主题。"
    assert theme_types.dark_mode == "低光环境下保持对比度。"
    assert visual_priority.primary_content == ["任务标题"]
    assert visual_priority.secondary_content == ["任务描述"]
    assert visual_priority.tertiary_content == ["帮助文本"]
    assert visual_priority.primary_actions == ["创建任务"]
    assert visual_priority.secondary_actions == ["取消"]
    assert visual_priority.danger_actions == ["清空表单"]
    assert output.content.component_style_rules[0].style_rules == ["错误消息就近展示"]


def test_prompt_renderer_rejects_missing_or_duplicate_markers() -> None:
    with pytest.raises(PromptTemplateRenderError):
        split_rendered_prompt("===SYSTEM===\nOnly system")
    with pytest.raises(PromptTemplateRenderError):
        split_rendered_prompt("===SYSTEM===\na\n===USER===\nb\n===USER===\nc")


def test_tojson_pretty_outputs_readable_json() -> None:
    assert tojson_pretty({"name": "测试"}) == '{\n  "name": "测试"\n}'


def _template_variables(name: str) -> dict[str, object]:
    project = SimpleNamespace(
        name="Demo",
        description="Demo project",
        target_frontend_stack="Frontend",
        target_backend_stack="Backend",
    )
    requirement = SimpleNamespace(
        id="req-1",
        raw_text="Create tasks",
        language="zh",
        source_type="manual",
    )
    blueprint_content = {"project": {}, "domain_entities": [], "pages": [], "api_needs": []}
    api_contract_content = {"base_path": "/api/v1", "resources": [], "schemas": []}
    project_config = {"project_name": "Demo", "prompt_preferences": []}
    selected_story = {"title": "Story"}
    change_set = {"title": "Change", "affected_layers": ["ux_design"]}
    design_assets = {"ux_design": {}, "ui_design": {}}

    if name == "business_story_decomposer":
        return build_business_story_decomposition_payload(project, requirement)
    if name == "blueprint_generator":
        return build_blueprint_generation_payload(project, requirement, [])
    if name == "api_contract_generator":
        return build_api_contract_generation_payload(project, blueprint_content)
    if name == "db_model_generator":
        return build_db_model_generation_payload(
            project,
            blueprint_content,
            api_contract_content,
        )
    if name == "change_set":
        return build_change_set_payload(
            project_config=project_config,
            selected_story=selected_story,
            current_assets=design_assets,
        )
    if name in {"design_asset", "ux_design", "ui_design", "frontend_pages"}:
        layer = name if name != "design_asset" else "backend_services"
        return build_design_asset_payload(
            layer=layer,
            project_config=project_config,
            selected_story=selected_story,
            change_set=change_set,
            previous_version=None,
            related_assets=design_assets,
        )
    if name == "blueprint_summary":
        return build_blueprint_summary_payload(
            project_config=project_config,
            business_stories=[selected_story],
            design_assets=design_assets,
            latest_change_set=change_set,
        )
    if name == "prompt_pack":
        return build_prompt_pack_payload(
            project_config=project_config,
            selected_story=selected_story,
            change_set=change_set,
            old_versions={},
            new_versions=design_assets,
            project_blueprint={"title": "Blueprint"},
        )
    if name == "context_pack":
        return {
            "blueprint": blueprint_content,
            "api_contract": api_contract_content,
            "db_model": {"entities": []},
            "frontend_stack": "Frontend",
            "backend_stack": "Backend",
            "target_output_schema": ContextPackOutput.model_json_schema(),
        }
    raise AssertionError(f"Unhandled template: {name}")
