import re
from types import SimpleNamespace

import pytest

from app.generators.db_model_generator import validate_db_model_content
from app.prompts.api_contract_generator import build_api_contract_generation_payload
from app.prompts.blueprint_generator import build_blueprint_generation_payload
from app.prompts.business_story_decomposer import build_business_story_decomposition_payload
from app.prompts.db_model_generator import build_db_model_generation_payload
from app.prompts.orchestration import (
    build_blueprint_summary_payload,
    build_change_set_payload,
    build_change_set_prompt,
    build_design_asset_payload,
    build_prompt_pack_payload,
    build_prompt_pack_prompt,
)
from app.prompts.renderer import (
    PromptTemplateRenderError,
    render_prompt_template,
    split_rendered_prompt,
    tojson_pretty,
)
from app.prompts.template_registry import PROMPT_TEMPLATE_CONTRACTS
from app.prompts.templates.api_contract.output_schema import ApiContractAssetOutput
from app.prompts.templates.api_contract_generator.output_schema import ApiContractOutput
from app.prompts.templates.backend_implementation.output_schema import (
    BackendImplementationOutput,
)
from app.prompts.templates.blueprint_generator.output_schema import ProjectBlueprintOutput
from app.prompts.templates.blueprint_summary.output_schema import BlueprintSummaryOutput
from app.prompts.templates.business_story_decomposer.output_schema import (
    BusinessStoryDecompositionOutput,
)
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.prompts.templates.context_pack.output_schema import ContextPackOutput
from app.prompts.templates.database_models.output_schema import DatabaseModelAssetOutput
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput
from app.prompts.templates.design_asset.output_schema import DesignAssetOutput
from app.prompts.templates.frontend_pages.output_schema import FrontendPagesOutput
from app.prompts.templates.project_description_options.output_schema import (
    ProjectDescriptionOptionsOutput,
)
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.prompts.templates.ui_design.output_schema import UIDesignOutput
from app.prompts.templates.ux_design.output_schema import UXDesignOutput
from app.services.orchestration_context import project_config_snapshot
from app.services.orchestration_validators import validate_design_asset_payload

REQUIRED_USER_SECTIONS = (
    "Input:",
    "Input Fields:",
    "Output Fields:",
    "Output Rules:",
)

FORBIDDEN_USER_SECTIONS = (
    "Input Descriptions:",
    "Output Descriptions:",
)

EXPECTED_EXAMPLE_COUNTS = {
    "business_story_decomposer": 2,
    "change_set": 2,
    "prompt_pack": 2,
}

EXPECTED_RESPONSE_MODELS = {
    "business_story_decomposer": BusinessStoryDecompositionOutput,
    "blueprint_generator": ProjectBlueprintOutput,
    "project_description_options": ProjectDescriptionOptionsOutput,
    "api_contract_generator": ApiContractOutput,
    "api_contract": ApiContractAssetOutput,
    "backend_implementation": BackendImplementationOutput,
    "db_model_generator": DbModelOutput,
    "database_models": DatabaseModelAssetOutput,
    "change_set": ChangeSetOutput,
    "design_asset": DesignAssetOutput,
    "ux_design": UXDesignOutput,
    "ui_design": UIDesignOutput,
    "frontend_pages": FrontendPagesOutput,
    "blueprint_summary": BlueprintSummaryOutput,
    "prompt_pack": PromptPackOutput,
    "context_pack": ContextPackOutput,
}


def test_prompt_template_files_exist_and_follow_runtime_structure() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        assert contract.schema_path.is_file()
        for language, template_path in contract.template_paths.items():
            assert template_path.is_file()
            template_text = template_path.read_text(encoding="utf-8")
            assert "{{" in template_text
            assert template_text.count("===SYSTEM===") == 1
            assert template_text.count("===USER===") == 1
            assert template_text.find("===SYSTEM===") < template_text.find("===USER===")
            for section in REQUIRED_USER_SECTIONS:
                assert section in template_text
            for section in FORBIDDEN_USER_SECTIONS:
                assert section not in template_text
            expected_count = EXPECTED_EXAMPLE_COUNTS.get(contract.name, 1)
            input_examples = re.findall(r"Example Input \[(\d+)\]:", template_text)
            output_examples = re.findall(r"Example Output \[(\d+)\]:", template_text)
            assert len(input_examples) == expected_count, (contract.name, language)
            assert output_examples == input_examples


def test_registered_templates_render_to_non_empty_system_and_user() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        for language in contract.template_paths:
            rendered = render_prompt_template(
                contract.name,
                _template_variables(contract.name),
                language=language,
            )
            assert rendered.system
            assert rendered.user
            assert "Input:" in rendered.user
            assert "Input Fields:" in rendered.user
            assert "Output Fields:" in rendered.user
            assert "Output Rules:" in rendered.user


def test_registered_templates_keep_runtime_response_models() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        assert contract.response_model is EXPECTED_RESPONSE_MODELS[contract.name]


def test_ux_prompt_requires_readable_chinese_user_visible_names() -> None:
    rendered = render_prompt_template(
        "ux_design",
        _template_variables("ux_design"),
        language="zh-CN",
    )

    assert "面向用户阅读的名称和值必须使用中文自然语言业务表达" in rendered.user
    assert (
        "不要把 screen_name、region_name、flow_name、primary_actor 等用户可见名称写成英文变量名"
        in rendered.user
    )
    assert "paper_upload_flow" in rendered.user
    assert "论文上传流程" in rendered.user


def test_ux_prompt_can_render_readable_english_user_visible_names() -> None:
    rendered = render_prompt_template("ux_design", _template_variables("ux_design"), language="en")

    assert "natural English" in rendered.user
    assert "paper_upload_flow" in rendered.user
    assert "Paper upload flow" in rendered.user


def test_orchestration_prompt_builders_use_project_prompt_language() -> None:
    project_config = {"project_name": "Demo", "prompt_preferences": [], "llm_prompt_language": "en"}
    selected_story = {"title": "Story"}
    change_set = {"title": "Change", "affected_layers": ["ux_design"]}

    rendered_change_set = build_change_set_prompt(
        project_config=project_config,
        selected_story=selected_story,
        current_assets={"ux_design": {}},
    )
    rendered_prompt_pack = build_prompt_pack_prompt(
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        old_versions={},
        new_versions={"ux_design": {}},
        project_blueprint={},
    )

    assert "natural English" in rendered_change_set.user
    assert "Codex-executable instructions" in rendered_prompt_pack.user


def test_change_set_prompt_requires_field_level_layer_specific_changes() -> None:
    rendered_zh = render_prompt_template(
        "change_set",
        _template_variables("change_set"),
        language="zh-CN",
    )
    rendered_en = render_prompt_template(
        "change_set",
        _template_variables("change_set"),
        language="en",
    )

    assert "字段级变更对象" in rendered_zh.user
    assert "current_assets.current_layer_asset.content" in rendered_zh.user
    assert "UX → UI → API 契约 → 数据库模型 → 后端工程实现 → 前端工程实现" in rendered_zh.user
    assert "content.api_resource_groups" in rendered_zh.user
    assert "content.database_tables" in rendered_zh.user
    assert "content.route_definitions" in rendered_zh.user
    assert "field-level objects" in rendered_en.user
    assert "current_assets.current_layer_asset.content" in rendered_en.user
    assert (
        "UX → UI → API contract → database model → backend implementation "
        "→ frontend implementation"
    ) in rendered_en.user


def test_asset_prompts_apply_change_set_without_redefining_scope() -> None:
    for template_name, layer_key in [
        ("ux_design", "ux_design"),
        ("ui_design", "ui_design"),
        ("api_contract", "api_contract"),
        ("database_models", "database_models"),
        ("backend_implementation", "backend_services"),
        ("frontend_pages", "frontend_pages"),
    ]:
        rendered = render_prompt_template(
            template_name,
            _template_variables(template_name),
            language="en",
        )
        assert f"change_set.module_changes.{layer_key}" in rendered.user
        assert "do not redefine" in rendered.user


def test_business_story_payload_does_not_inject_schema() -> None:
    project = SimpleNamespace(name="Demo", description="Demo project")
    requirement = SimpleNamespace(raw_text="Create tasks")

    payload = build_business_story_decomposition_payload(project, requirement)

    assert "target_output_schema" not in payload
    assert "project_description" not in payload


def test_core_prompt_payloads_do_not_inject_schema() -> None:
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

    assert "target_output_schema" not in blueprint_payload
    assert "project_description" not in blueprint_payload
    assert "target_output_schema" not in api_payload
    assert "target_output_schema" not in db_payload


def test_project_config_snapshot_omits_description() -> None:
    project = SimpleNamespace(
        id="project-1",
        name="Demo",
        description="Demo project",
        target_frontend_stack="Frontend",
        target_backend_stack="Backend",
        target_frontend_stack_items=[],
        target_backend_stack_items=[],
        global_constraints=[],
        coding_preferences=[],
        prompt_preferences=[],
    )

    snapshot = project_config_snapshot(project)

    assert "description" not in snapshot


def test_orchestration_payloads_do_not_inject_schema() -> None:
    project_config = {"prompt_preferences": []}
    selected_story = {"title": "Story"}
    current_assets = {"ux_design": {}}
    design_assets = {"ux_design": {}}
    change_set = {"affected_layers": ["ux_design"]}

    assert "output_contract" not in build_change_set_payload(
        project_config=project_config,
        selected_story=selected_story,
        current_assets=current_assets,
    )

    assert "output_contract" not in build_design_asset_payload(
        layer="ux_design",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )

    assert "output_contract" not in build_design_asset_payload(
        layer="ui_design",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )

    assert "output_contract" not in build_design_asset_payload(
        layer="frontend_pages",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )

    assert "output_contract" not in build_design_asset_payload(
        layer="backend_services",
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        previous_version=None,
        related_assets={},
    )

    assert "output_contract" not in build_blueprint_summary_payload(
        project_config=project_config,
        business_stories=[],
        design_assets=design_assets,
        latest_change_set=change_set,
    )

    assert "output_contract" not in build_prompt_pack_payload(
        project_config=project_config,
        selected_story=selected_story,
        change_set=change_set,
        old_versions={},
        new_versions={},
        project_blueprint={},
    )


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
                    "style_tags": ["高密度", "快速录入", "可扫描"],
                    "design_principles": ["保持可读性", "状态反馈必须明确"],
                    "theme_configuration": {
                        "theme_types": {
                            "light_mode": "默认浅色主题。",
                            "dark_mode": "低光环境下保持对比度。",
                        },
                        "default_theme": "默认浅色主题",
                    },
                    "evidence_policy": "区分 validated、normative、tbd 和 inferred。",
                    "source_references": ["UX 设计", "变更集"],
                    "tbd_items": ["深色模式 token 待验证"],
                    "accessibility_rules": ["正常文本满足 WCAG AA"],
                    "responsive_contract": ["移动端单栏堆叠"],
                    "color_system": {
                        "description": "主操作和状态提示颜色。",
                        "rules": ["primary 用于主操作"],
                        "tokens": [
                            {
                                "token_name": "primary",
                                "token_type": "color",
                                "token_value": "#111111",
                                "description": "主操作颜色。",
                                "semantic_role": "主操作",
                                "usage_context": "用于创建按钮和高亮状态",
                                "anti_usage": ["不要用于错误提示"],
                                "css_variable": "--color-primary",
                                "tailwind_variable": "--color-primary",
                                "validated_status": "normative",
                                "source_basis": ["项目配置"],
                                "contrast_notes": "按钮文字需保持可读",
                            }
                        ],
                        "tbd_items": [],
                    },
                    "typography_system": {
                        "description": "标题与正文层级。",
                        "rules": ["标题使用中等字重"],
                        "tokens": [
                            {
                                "token_name": "body-default",
                                "token_type": "typography",
                                "token_value": {
                                    "fontFamily": "system-ui",
                                    "fontSize": "14px",
                                    "fontWeight": 400,
                                    "lineHeight": "20px",
                                    "letterSpacing": "normal",
                                },
                                "description": "默认正文。",
                                "semantic_role": "正文",
                                "usage_context": "用于表单说明文本",
                                "anti_usage": [],
                                "css_variable": "--text-body-default",
                                "tailwind_variable": "--text-body-default",
                                "validated_status": "normative",
                                "source_basis": ["项目配置"],
                            }
                        ],
                        "tbd_items": [],
                    },
                    "spacing_system": {
                        "description": "表单间距。",
                        "rules": ["表单项保持紧凑间距"],
                        "tokens": [],
                        "tbd_items": [],
                    },
                    "shape_system": {
                        "description": "控件圆角。",
                        "rules": ["控件使用小圆角"],
                        "tokens": [],
                        "tbd_items": [],
                    },
                    "elevation_system": {
                        "description": "弹层阴影。",
                        "rules": ["弹层使用轻量阴影"],
                        "tokens": [],
                        "tbd_items": [],
                    },
                    "interaction_visual_system": {
                        "description": "交互状态。",
                        "rules": ["loading 状态保持按钮宽度"],
                        "tokens": [],
                        "tbd_items": [],
                    },
                    "tailwind_theme_css": (
                        "@theme {\n"
                        "  --color-primary: #111111;\n"
                        "  --text-body-default: 14px;\n"
                        "}"
                    ),
                    "interaction_state_matrix": [
                        {
                            "state_name": "loading",
                            "visual_cues": ["按钮宽度保持不变"],
                            "usage_context": ["提交表单"],
                            "constraints": ["不能引发布局跳动"],
                        }
                    ],
                },
                "layout_rules": [
                    {
                        "target_screen": "任务创建页",
                        "desktop_layout": "表单居中，辅助说明右侧展示。",
                        "mobile_layout": "单栏布局，主按钮全宽。",
                        "primary_action": "创建任务",
                        "desktop_grid": "双栏布局",
                        "mobile_reflow": "辅助说明移动到表单下方",
                        "container_rules": ["最大宽度 960px"],
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
                        "states": [
                            {
                                "state_name": "focus-visible",
                                "visual_cues": ["显示 3px focus ring"],
                                "usage_context": ["键盘导航"],
                                "constraints": ["不能只依赖颜色"],
                            }
                        ],
                        "responsive_behavior": ["移动端按钮全宽"],
                        "accessibility_notes": ["错误状态同时显示文本"],
                        "implementation_hint": "映射到现有 Button 和 Input 组件",
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
    assert output.content.visual_system.theme_configuration.default_theme == "默认浅色主题"
    assert visual_priority.primary_content == ["任务标题"]
    assert visual_priority.secondary_content == ["任务描述"]
    assert visual_priority.tertiary_content == ["帮助文本"]
    assert visual_priority.primary_actions == ["创建任务"]
    assert visual_priority.secondary_actions == ["取消"]
    assert visual_priority.danger_actions == ["清空表单"]
    assert output.content.visual_system.style_tags == ["高密度", "快速录入", "可扫描"]
    assert (
        output.content.visual_system.evidence_policy
        == "区分 validated、normative、tbd 和 inferred。"
    )
    assert output.content.visual_system.tbd_items == ["深色模式 token 待验证"]
    color_token = output.content.visual_system.color_system.tokens[0]
    typography_token = output.content.visual_system.typography_system.tokens[0]
    assert color_token.token_value == "#111111"
    assert color_token.css_variable == "--color-primary"
    assert typography_token.token_value["fontSize"] == "14px"
    assert "@theme" in output.content.visual_system.tailwind_theme_css
    assert output.content.visual_system.interaction_state_matrix[0].state_name == "loading"
    assert output.content.layout_rules[0].primary_action == "创建任务"
    assert output.content.component_style_rules[0].style_rules == ["错误消息就近展示"]
    assert output.content.component_style_rules[0].states[0].state_name == "focus-visible"
    assert (
        output.content.component_style_rules[0].implementation_hint
        == "映射到现有 Button 和 Input 组件"
    )


def test_ui_design_prompt_mentions_extended_visual_contract() -> None:
    rendered = render_prompt_template("ui_design", _template_variables("ui_design"))

    assert "brand_anchor" not in rendered.user
    assert "token_catalog" not in rendered.user
    assert "interaction_state_matrix" in rendered.user
    assert "tailwind_theme_css" in rendered.user
    assert (
        "color_system、typography_system、spacing_system、shape_system、"
        "elevation_system、interaction_visual_system"
    ) in rendered.user
    assert "不要输出 light_mode、dark_mode 或其它字段 key" in rendered.user
    assert "validated、normative、tbd、inferred" in rendered.user
    assert "source_references" in rendered.user
    assert "anti_usage" in rendered.user
    assert (
        "组件规则必须覆盖 default、hover、pressed、focus-visible、selected、disabled、"
        "loading、error"
    ) in rendered.user


def test_downstream_prompts_read_visual_system_tokens_without_catalog() -> None:
    frontend_pages = render_prompt_template(
        "frontend_pages",
        _template_variables("frontend_pages"),
        language="zh-CN",
    )
    prompt_pack = render_prompt_template(
        "prompt_pack",
        _template_variables("prompt_pack"),
        language="zh-CN",
    )
    change_set = render_prompt_template(
        "change_set",
        _template_variables("change_set"),
        language="zh-CN",
    )

    for rendered in (frontend_pages, prompt_pack, change_set):
        assert "token_catalog" not in rendered.user
        assert "color_system" in rendered.user
        assert "tailwind_theme_css" in rendered.user


def test_ui_design_output_rejects_default_theme_field_key() -> None:
    with pytest.raises(ValueError, match="default_theme must be a user-visible"):
        UIDesignOutput.model_validate(
            {
                "title": "任务创建 UI 视觉设计",
                "summary": "定义任务创建页的视觉系统、布局和组件样式。",
                "content": {
                    "version_summary": "新增任务创建视觉规则。",
                    "visual_system": {
                        "design_style": {
                            "style_description": "清晰、工作台式、主操作突出。",
                            "signature_traits": ["紧凑表单"],
                        },
                        "style_tags": [],
                        "design_principles": [],
                        "theme_configuration": {
                            "theme_types": {
                                "light_mode": "默认浅色主题。",
                                "dark_mode": "低光环境下保持对比度。",
                            },
                            "default_theme": "light_mode",
                        },
                    },
                    "layout_rules": [],
                    "component_style_rules": [],
                    "diff": {"added": [], "modified": [], "removed": []},
                },
                "diff_from_previous": {"added": [], "modified": [], "removed": []},
            }
        )


def test_ui_design_output_accepts_legacy_token_catalog_before_normalization() -> None:
    output = UIDesignOutput.model_validate(
        {
            "title": "任务创建 UI 视觉设计",
            "summary": "定义任务创建页的视觉系统、布局和组件样式。",
            "content": {
                "version_summary": "新增任务创建视觉规则。",
                "visual_system": {
                    "design_style": {
                        "style_description": "清晰、工作台式、主操作突出。",
                        "signature_traits": [],
                    },
                    "style_tags": [],
                    "design_principles": [],
                    "theme_configuration": {
                        "theme_types": {
                            "light_mode": "默认浅色主题。",
                            "dark_mode": "低光环境下保持对比度。",
                        },
                        "default_theme": "默认浅色主题",
                    },
                    "token_catalog": [
                        {
                            "group_name": "字体系统",
                            "tokens": [
                                {
                                    "token_name": "body-default",
                                    "token_value": {
                                        "fontFamily": "system-ui",
                                        "fontSize": "14px",
                                        "fontWeight": 400,
                                        "lineHeight": "20px",
                                        "letterSpacing": "normal",
                                    },
                                }
                            ],
                        }
                    ],
                },
                "layout_rules": [],
                "component_style_rules": [],
                "diff": {"added": [], "modified": [], "removed": []},
            },
            "diff_from_previous": {"added": [], "modified": [], "removed": []},
        }
    )

    legacy_token = output.content.visual_system.token_catalog[0].tokens[0]
    assert legacy_token.token_value["fontSize"] == "14px"


def test_ui_design_output_rejects_unknown_token_status() -> None:
    with pytest.raises(ValueError, match="validated_status"):
        UIDesignOutput.model_validate(
            {
                "title": "任务创建 UI 视觉设计",
                "summary": "定义任务创建页的视觉系统、布局和组件样式。",
                "content": {
                    "version_summary": "新增任务创建视觉规则。",
                    "visual_system": {
                        "design_style": {
                            "style_description": "清晰、工作台式、主操作突出。",
                            "signature_traits": [],
                        },
                        "style_tags": [],
                        "design_principles": [],
                        "theme_configuration": {
                            "theme_types": {
                                "light_mode": "默认浅色主题。",
                                "dark_mode": "低光环境下保持对比度。",
                            },
                            "default_theme": "默认浅色主题",
                        },
                        "color_system": {
                            "description": "主操作颜色。",
                            "rules": [],
                            "tokens": [
                                {
                                    "token_name": "primary",
                                    "token_type": "color",
                                    "token_value": "#111111",
                                    "description": "主操作颜色。",
                                    "semantic_role": "主操作",
                                    "usage_context": "用于创建按钮",
                                    "anti_usage": [],
                                    "validated_status": "guessed",
                                    "source_basis": [],
                                }
                            ],
                            "tbd_items": [],
                        },
                    },
                    "layout_rules": [],
                    "component_style_rules": [],
                    "diff": {"added": [], "modified": [], "removed": []},
                },
                "diff_from_previous": {"added": [], "modified": [], "removed": []},
            }
        )


def test_ui_design_validator_does_not_add_visual_quality_summary() -> None:
    payload = validate_design_asset_payload(
        {
            "title": "危险操作 UI 视觉设计",
            "summary": "验证 UI 视觉设计规范化。",
            "content": {
                "version_summary": "新增危险操作视觉规则。",
                "visual_system": {
                    "theme_configuration": {
                        "theme_types": {
                            "light_mode": "默认浅色主题",
                            "dark_mode": "已支持暗色主题",
                        }
                    },
                    "color_system": {
                        "tokens": [
                            {
                                "token_name": "brand-danger",
                                "token_type": "color",
                                "token_value": "#ff385c",
                                "description": "危险操作颜色",
                                "semantic_role": "危险操作",
                                "usage_context": "删除按钮",
                            }
                        ]
                    },
                    "token_catalog": [
                        {
                            "group_name": "字体系统",
                            "tokens": [
                                {
                                    "token_name": "body-default",
                                    "token_value": {
                                        "fontFamily": "system-ui",
                                        "fontSize": "14px",
                                        "fontWeight": 400,
                                        "lineHeight": "20px",
                                        "letterSpacing": "normal",
                                    },
                                    "token_type": "typography",
                                    "anti_usage": "不用于页面主标题",
                                    "source_basis": "LLM legacy token_catalog output",
                                }
                            ],
                        }
                    ],
                },
                "layout_rules": [{"target_screen": "删除页"}],
                "component_style_rules": [
                    {
                        "component_name": "DeleteButton",
                        "visual_priority": {"primary_actions": ["删除"]},
                    }
                ],
            },
            "diff_from_previous": {},
        },
        layer="ui_design",
    )

    assert "visual_quality_summary" not in payload["content"]
    assert "token_catalog" not in payload["content"]["visual_system"]
    assert payload["content"]["visual_system"]["color_system"]["tokens"][0]["anti_usage"] == []
    assert (
        payload["content"]["visual_system"]["typography_system"]["tokens"][0][
            "token_value"
        ]["fontSize"]
        == "14px"
    )
    assert payload["content"]["visual_system"]["typography_system"]["tokens"][0][
        "anti_usage"
    ] == ["不用于页面主标题"]
    assert payload["content"]["visual_system"]["typography_system"]["tokens"][0][
        "source_basis"
    ] == ["LLM legacy token_catalog output"]
    assert payload["content"]["layout_rules"] == [{"target_screen": "删除页"}]


def test_frontend_pages_output_accepts_frontend_implementation_contract() -> None:
    output = FrontendPagesOutput.model_validate(
        {
            "title": "任务创建前端工程实现",
            "summary": "定义任务创建页的前端工程实现规划。",
            "content": {
                "version_summary": "新增任务创建前端工程实现。",
                "route_definitions": [
                    {
                        "path": "/tasks/new",
                        "page_name": "任务创建页",
                        "dynamic_params": [],
                        "permission_requirement": "已登录用户",
                    }
                ],
                "directory_structure": [
                    {"path": "app/tasks/new/page.tsx", "purpose": "页面入口"},
                    {"path": "components/tasks/TaskForm.tsx", "purpose": "任务表单"},
                ],
                "code_logic": [
                    {
                        "target": "TaskForm",
                        "state_management": ["保存标题、描述、提交状态和错误信息"],
                        "events": ["提交表单"],
                        "data_flow": ["TaskForm -> POST /tasks"],
                        "error_handling": ["失败时展示错误并允许重试"],
                    }
                ],
                "environment_variables": [
                    {
                        "name": "NEXT_PUBLIC_API_BASE_URL",
                        "purpose": "后端 API 基础地址",
                        "required": True,
                    }
                ],
                "design_theme": ["primary token 用于主按钮"],
                "dependencies": [
                    {
                        "package_name": "lucide-react",
                        "purpose": "表单操作图标",
                        "required": False,
                    }
                ],
                "diff": {"added": ["任务创建前端工程实现"], "modified": [], "removed": []},
            },
            "diff_from_previous": {
                "added": ["任务创建前端工程实现"],
                "modified": [],
                "removed": [],
            },
        }
    )

    content = output.content
    assert content.route_definitions[0].path == "/tasks/new"
    assert content.directory_structure[0].path == "app/tasks/new/page.tsx"
    assert content.code_logic[0].target == "TaskForm"
    assert content.environment_variables[0].name == "NEXT_PUBLIC_API_BASE_URL"
    assert content.design_theme == ["primary token 用于主按钮"]
    assert content.dependencies[0].package_name == "lucide-react"


def test_backend_implementation_output_accepts_backend_implementation_contract() -> None:
    output = BackendImplementationOutput.model_validate(
        {
            "title": "任务创建后端工程实现",
            "summary": "定义任务创建接口、服务、工具、LLM 模板、环境变量和依赖。",
            "content": {
                "version_summary": "新增任务创建后端工程实现。",
                "directory_structure": [
                    {"path": "app/api/v1/endpoints/tasks.py", "purpose": "任务接口路由"},
                    {"path": "app/services/task_service.py", "purpose": "任务创建业务逻辑"},
                ],
                "code_logic": [
                    {
                        "target": "TaskService.create_task",
                        "service_flow": ["读取当前用户", "创建任务", "返回任务详情"],
                        "validation_logic": ["标题必填"],
                        "transaction_handling": ["创建任务和审计记录使用同一事务"],
                        "error_handling": ["校验失败返回 400"],
                    }
                ],
                "utility_classes": [
                    {
                        "name": "TaskTitleNormalizer",
                        "purpose": "规范化任务标题",
                        "usage": ["创建任务前 trim 标题"],
                    }
                ],
                "llm_interaction_templates": [
                    {
                        "template_name": "task_summary",
                        "input_structure": ["任务标题", "任务描述"],
                        "output_structure": ["summary"],
                        "parsing_rules": ["只接受 JSON object"],
                    }
                ],
                "environment_variables": [
                    {
                        "name": "DATABASE_URL",
                        "purpose": "连接 PostgreSQL 数据库",
                        "required": True,
                    }
                ],
                "dependencies": [
                    {
                        "package_name": "SQLAlchemy",
                        "purpose": "ORM 和事务处理",
                        "required": True,
                    }
                ],
                "diff": {"added": ["任务创建后端工程实现"], "modified": [], "removed": []},
            },
            "diff_from_previous": {
                "added": ["任务创建后端工程实现"],
                "modified": [],
                "removed": [],
            },
        }
    )

    content = output.content
    assert content.directory_structure[0].path == "app/api/v1/endpoints/tasks.py"
    assert content.code_logic[0].target == "TaskService.create_task"
    assert content.utility_classes[0].name == "TaskTitleNormalizer"
    assert content.llm_interaction_templates[0].template_name == "task_summary"
    assert content.environment_variables[0].name == "DATABASE_URL"
    assert content.dependencies[0].package_name == "SQLAlchemy"


def test_api_contract_output_accepts_new_contract_shape() -> None:
    output = ApiContractOutput.model_validate(
        {
            "api_base_path": "/api/v1",
            "api_resource_groups": [
                {
                    "group_name": "tasks",
                    "group_purpose": "任务创建与读取",
                    "endpoints": [
                        {
                            "http_method": "POST",
                            "endpoint_path": "/tasks",
                            "endpoint_purpose": "创建任务",
                            "requires_auth": True,
                            "request_schema": {
                                "body": [
                                    {
                                        "name": "title",
                                        "type": "string",
                                        "required": True,
                                    }
                                ]
                            },
                            "response_schema": {"body": "TaskResponse"},
                            "error_model": [
                                {
                                    "status_code": 400,
                                    "error_code": "TASK_TITLE_REQUIRED",
                                    "error_message": "任务标题不能为空",
                                    "recovery_suggestion": "填写任务标题后重试",
                                }
                            ],
                        }
                    ],
                }
            ],
            "notes": ["只覆盖任务创建。"],
        }
    )

    group = output.api_resource_groups[0]
    endpoint = group.endpoints[0]
    assert output.api_base_path == "/api/v1"
    assert group.group_name == "tasks"
    assert endpoint.http_method == "POST"
    assert endpoint.endpoint_path == "/tasks"
    assert endpoint.request_schema["body"][0]["name"] == "title"
    assert endpoint.response_schema["body"] == "TaskResponse"
    assert endpoint.error_model[0].error_code == "TASK_TITLE_REQUIRED"


def test_db_model_output_accepts_database_model_contract() -> None:
    output = DbModelOutput.model_validate(
        {
            "database": {
                "engine": "PostgreSQL",
                "orm": "SQLAlchemy 2.x",
                "migration_tool": "Alembic",
            },
            "database_tables": [
                {
                    "name": "Task",
                    "table_name": "tasks",
                    "description": "任务表",
                    "fields": [
                        {
                            "name": "id",
                            "type": "uuid",
                            "required": True,
                            "primary_key": True,
                            "nullable": False,
                            "description": "主键",
                        },
                        {
                            "name": "title",
                            "type": "string",
                            "required": True,
                            "nullable": False,
                            "description": "任务标题",
                        },
                    ],
                    "relationships": [],
                    "indexes": [
                        {
                            "table": "tasks",
                            "fields": ["title"],
                            "reason": "按标题检索任务",
                        }
                    ],
                    "migration_notes": ["新增 tasks 表。"],
                }
            ],
            "relationships": [],
            "indexes": [],
            "migration_notes": ["使用 Alembic 迁移。"],
        }
    )

    table = output.database_tables[0]
    field = table.fields[0]
    assert table.table_name == "tasks"
    assert field.name == "id"
    assert field.required is True
    assert field.primary_key is True
    assert table.indexes[0].fields == ["title"]


def test_db_model_validator_maps_legacy_entities_to_database_tables() -> None:
    normalized = validate_db_model_content(
        {
            "database": {"engine": "PostgreSQL"},
            "entities": [
                {
                    "name": "Task",
                    "table_name": "tasks",
                    "fields": [{"name": "title", "type": "string", "nullable": False}],
                }
            ],
        }
    )

    table = normalized["database_tables"][0]
    title_field = next(field for field in table["fields"] if field["name"] == "title")
    assert table["name"] == "Task"
    assert table["table_name"] == "tasks"
    assert table["fields"][0]["name"] == "id"
    assert title_field["required"] is True


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
    api_contract_content = {"api_base_path": "/api/v1", "api_resource_groups": []}
    project_config = {"project_name": "Demo", "prompt_preferences": []}
    selected_story = {"title": "Story"}
    change_set = {"title": "Change", "affected_layers": ["ux_design"]}
    design_assets = {"ux_design": {}, "ui_design": {}}

    if name == "business_story_decomposer":
        return build_business_story_decomposition_payload(project, requirement)
    if name == "blueprint_generator":
        return build_blueprint_generation_payload(project, requirement, [])
    if name == "project_description_options":
        return {
            "task": "generate_project_description_options",
            "project_name": "库存运营助手",
        }
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
    if name in {
        "design_asset",
        "ux_design",
        "ui_design",
        "frontend_pages",
        "backend_implementation",
        "api_contract",
        "database_models",
    }:
        layer = (
            "backend_services"
            if name in {"design_asset", "backend_implementation"}
            else "database_models"
            if name == "database_models"
            else name
        )
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
        }
    raise AssertionError(f"Unhandled template: {name}")
