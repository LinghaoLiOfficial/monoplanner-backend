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
from app.prompts.renderer import render_prompt_template
from app.prompts.template_registry import PROMPT_TEMPLATE_CONTRACTS
from app.prompts.templates.api_contract.output_schema import ApiContractAssetOutput
from app.prompts.templates.api_contract_generator.output_schema import ApiContractOutput
from app.prompts.templates.backend_implementation.output_schema import BackendImplementationOutput
from app.prompts.templates.blueprint_generator.output_schema import ProjectBlueprintOutput
from app.prompts.templates.blueprint_summary.output_schema import BlueprintSummaryOutput
from app.prompts.templates.business_story_decomposer.output_schema import BusinessStoryDecompositionOutput
from app.prompts.templates.change_set.output_schema import ChangeSetOutput
from app.prompts.templates.context_pack.output_schema import ContextPackOutput
from app.prompts.templates.database_models.output_schema import DatabaseModelAssetOutput
from app.prompts.templates.db_model_generator.output_schema import DbModelOutput
from app.prompts.templates.design_asset.output_schema import DesignAssetOutput
from app.prompts.templates.frontend_pages.output_schema import FrontendPagesOutput
from app.prompts.templates.project_description_options.output_schema import ProjectDescriptionOptionsOutput
from app.prompts.templates.prompt_pack.output_schema import PromptPackOutput
from app.prompts.templates.ui_design.output_schema import UIDesignOutput
from app.prompts.templates.ux_design.output_schema import UXDesignOutput
from app.services.orchestration_context import project_config_snapshot
from app.services.orchestration_validators import validate_design_asset_payload

REQUIRED_USER_SECTIONS = ("Input:", "Input Fields:", "Output Fields:", "Output Rules:")
FORBIDDEN_USER_SECTIONS = ("Input Descriptions:", "Output Descriptions:")
EXPECTED_EXAMPLE_COUNTS = {"business_story_decomposer": 2, "change_set": 2, "prompt_pack": 2}
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
            text = template_path.read_text(encoding="utf-8")
            assert "{{" in text
            assert text.count("===SYSTEM===") == 1
            assert text.count("===USER===") == 1
            assert text.find("===SYSTEM===") < text.find("===USER===")
            for section in REQUIRED_USER_SECTIONS:
                assert section in text
            for section in FORBIDDEN_USER_SECTIONS:
                assert section not in text
            expected_count = EXPECTED_EXAMPLE_COUNTS.get(contract.name, 1)
            input_examples = re.findall(r"Example Input \[(\d+)\]:", text)
            output_examples = re.findall(r"Example Output \[(\d+)\]:", text)
            assert len(input_examples) == expected_count, (contract.name, language)
            assert output_examples == input_examples


def test_registered_templates_render_to_non_empty_system_and_user() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        for language in contract.template_paths:
            rendered = render_prompt_template(contract.name, _template_variables(contract.name), language=language)
            assert rendered.system
            assert rendered.user


def test_registered_templates_keep_runtime_response_models() -> None:
    for contract in PROMPT_TEMPLATE_CONTRACTS:
        assert contract.response_model is EXPECTED_RESPONSE_MODELS[contract.name]


def test_ui_design_output_accepts_new_visual_contract() -> None:
    output = UIDesignOutput.model_validate(
        {
            "title": "任务创建 UI 视觉设计",
            "summary": "定义任务创建页的视觉系统。",
            "content": {
                "version_summary": "新增任务创建视觉规则。",
                "visual_system": {
                    "design_style": {
                        "style_description": "清晰、工作台式、主操作突出。",
                        "signature_traits": ["紧凑表单", "错误就近展示"],
                    },
                    "theme_configuration": {
                        "theme_types": {"light_mode": "默认浅色主题。", "dark_mode": "低光环境下保持对比度。"},
                        "default_theme": "默认浅色主题",
                    },
                    "color_configuration": {
                        "description": "主操作和状态提示颜色。",
                        "rules": ["warning 用于低库存风险"],
                        "colors": [{"color_name": "warning", "hex_value": "#f59e0b", "color_description": "低库存风险色"}],
                    },
                    "font_configuration": {"description": "标题与正文层级。", "rules": ["标题使用中等字重"], "fonts": []},
                    "spacing_configuration": {"description": "表单间距。", "rules": ["表单项保持紧凑间距"], "spacings": []},
                    "shape_configuration": {"description": "控件圆角。", "rules": ["控件使用小圆角"], "shapes": []},
                    "shadow_configuration": {"description": "弹层阴影。", "rules": ["弹层使用轻量阴影"], "shadows": []},
                },
                "diff": {"added": ["任务创建视觉规则"], "modified": [], "removed": []},
            },
            "diff_from_previous": {"added": ["任务创建 UI 设计"], "modified": [], "removed": []},
        }
    )

    assert output.content.visual_system.theme_configuration.default_theme == "默认浅色主题"
    assert output.content.visual_system.color_configuration.colors[0].color_name == "warning"
    assert output.content.visual_system.color_configuration.description == "主操作和状态提示颜色。"


def test_ui_design_prompt_mentions_extended_visual_contract() -> None:
    rendered = render_prompt_template("ui_design", _template_variables("ui_design"))
    assert "token_catalog" not in rendered.user
    assert "color_configuration / font_configuration / spacing_configuration / shape_configuration / shadow_configuration" in rendered.user
    assert "layout_rules" not in rendered.user
    assert "component_style_rules" not in rendered.user


def test_ui_design_validator_does_not_add_visual_quality_summary() -> None:
    payload = validate_design_asset_payload(
        {
            "title": "危险操作 UI 视觉设计",
            "summary": "验证 UI 视觉设计规范化。",
            "content": {
                "version_summary": "新增危险操作视觉规则。",
                "visual_system": {
                    "theme_configuration": {"theme_types": {"light_mode": "默认浅色主题", "dark_mode": "已支持暗色主题"}, "default_theme": "默认浅色主题"},
                    "color_configuration": {"description": "主操作颜色。", "rules": [], "colors": []},
                    "font_configuration": {"description": "标题与正文层级。", "rules": [], "fonts": []},
                    "spacing_configuration": {"description": "表单间距。", "rules": [], "spacings": []},
                    "shape_configuration": {"description": "控件圆角。", "rules": [], "shapes": []},
                    "shadow_configuration": {"description": "弹层阴影。", "rules": [], "shadows": []},
                },
                "diff": {"added": [], "modified": [], "removed": []},
            },
            "diff_from_previous": {},
        },
        layer="ui_design",
    )

    assert "visual_quality_summary" not in payload["content"]
    assert "token_catalog" not in payload["content"]["visual_system"]
    assert payload["content"]["visual_system"]["color_configuration"]["colors"] == []


def test_frontend_pages_output_accepts_frontend_implementation_contract() -> None:
    output = FrontendPagesOutput.model_validate(
        {
            "title": "任务创建前端工程实现",
            "summary": "定义任务创建页的前端工程实现规划。",
            "content": {
                "version_summary": "新增任务创建前端工程实现。",
                "environment_variables": [{"variable_name": "NEXT_PUBLIC_API_BASE_URL", "variable_description": "后端 API 基础地址", "default_value": ""}],
                "route_definitions": [{"route_name": "任务创建页", "route_path": "/tasks/new", "route_params": [], "route_target_component": "TaskPage"}],
                "directory_structure": [{"path": "app/tasks/new/page.tsx", "purpose": "页面入口"}, {"path": "components/tasks/TaskForm.tsx", "purpose": "任务表单"}],
                "layout_library": "表单和摘要并列布局。",
                "component_library": "表单、按钮和提示组件组合。",
                "dependency_package_management": [{"package_name": "lucide-react", "package_description": "表单操作图标"}],
                "page_code_logic": [{"target": "TaskForm", "logic_description": "提交表单并处理加载与错误状态。"}],
                "frontend_interfaces": [{"interface_name": "TaskFormProps", "interface_description": "表单输入契约。"}],
                "diff": {"added": ["任务创建前端工程实现"], "modified": [], "removed": []},
            },
            "diff_from_previous": {"added": ["任务创建前端工程实现"], "modified": [], "removed": []},
        }
    )

    assert output.content.route_definitions[0].route_path == "/tasks/new"
    assert output.content.directory_structure[0].path == "app/tasks/new/page.tsx"
    assert output.content.page_code_logic[0].target == "TaskForm"
    assert output.content.environment_variables[0].variable_name == "NEXT_PUBLIC_API_BASE_URL"
    assert output.content.layout_library == "表单和摘要并列布局。"
    assert output.content.component_library == "表单、按钮和提示组件组合。"
    assert output.content.dependency_package_management[0].package_name == "lucide-react"


def test_backend_implementation_output_accepts_backend_implementation_contract() -> None:
    output = BackendImplementationOutput.model_validate(
        {
            "title": "任务创建后端工程实现",
            "summary": "定义任务创建接口、服务、工具、LLM 模板、环境变量和依赖。",
            "content": {
                "version_summary": "新增任务创建后端工程实现。",
                "directory_structure": [{"path": "app/api/v1/endpoints/tasks.py", "purpose": "任务接口路由"}, {"path": "app/services/task_service.py", "purpose": "任务创建业务逻辑"}],
                "code_logic": [{"target": "TaskService.create_task", "service_flow": ["读取当前用户", "创建任务", "返回任务详情"], "validation_logic": ["标题必填"], "transaction_handling": ["创建任务和审计记录使用同一事务"], "error_handling": ["校验失败返回 400"]}],
                "utility_classes": [{"name": "TaskTitleNormalizer", "purpose": "规范化任务标题", "usage": ["创建任务前 trim 标题"]}],
                "llm_interaction_templates": [{"template_name": "task_summary", "input_structure": ["任务标题", "任务描述"], "output_structure": ["summary"], "parsing_rules": ["只接受 JSON object"]}],
                "environment_variables": [{"name": "DATABASE_URL", "purpose": "连接 PostgreSQL 数据库", "required": True}],
                "dependencies": [{"package_name": "SQLAlchemy", "purpose": "ORM 和事务处理", "required": True}],
                "diff": {"added": ["任务创建后端工程实现"], "modified": [], "removed": []},
            },
            "diff_from_previous": {"added": ["任务创建后端工程实现"], "modified": [], "removed": []},
        }
    )

    assert output.content.directory_structure[0].path == "app/api/v1/endpoints/tasks.py"
    assert output.content.code_logic[0].target == "TaskService.create_task"
    assert output.content.utility_classes[0].name == "TaskTitleNormalizer"
    assert output.content.llm_interaction_templates[0].template_name == "task_summary"
    assert output.content.environment_variables[0].name == "DATABASE_URL"
    assert output.content.dependencies[0].package_name == "SQLAlchemy"


def test_blueprint_and_prompt_payloads_do_not_inject_schema() -> None:
    project = SimpleNamespace(name="Demo", description="Demo project", target_frontend_stack="Frontend", target_backend_stack="Backend")
    requirement = SimpleNamespace(id="req-1", raw_text="Create tasks", language="zh", source_type="manual")
    blueprint_content = {"project": {}, "domain_entities": [], "pages": [], "api_needs": []}
    api_contract_content = {"base_path": "/api/v1", "resources": [], "schemas": []}
    project_config = {"prompt_preferences": []}
    selected_story = {"title": "Story"}
    current_assets = {"ux_design": {}}
    change_set = {"affected_layers": ["ux_design"]}

    assert "target_output_schema" not in build_business_story_decomposition_payload(project, requirement)
    assert "project_description" not in build_blueprint_generation_payload(project, requirement, [])
    assert "target_output_schema" not in build_api_contract_generation_payload(project, blueprint_content)
    assert "target_output_schema" not in build_db_model_generation_payload(project, blueprint_content, api_contract_content)
    assert "output_contract" not in build_change_set_payload(project_config=project_config, selected_story=selected_story, current_assets=current_assets)
    assert "output_contract" not in build_design_asset_payload(layer="ux_design", project_config=project_config, selected_story=selected_story, change_set=change_set, previous_version=None, related_assets={})
    assert "output_contract" not in build_blueprint_summary_payload(project_config=project_config, business_stories=[], design_assets={"ux_design": {}}, latest_change_set=change_set)
    assert "output_contract" not in build_prompt_pack_payload(project_config=project_config, selected_story=selected_story, change_set=change_set, old_versions={}, new_versions={}, project_blueprint={})


def test_project_config_snapshot_omits_description() -> None:
    project = SimpleNamespace(id="project-1", name="Demo", description="Demo project", target_frontend_stack="Frontend", target_backend_stack="Backend", target_frontend_stack_items=[], target_backend_stack_items=[], global_constraints=[], coding_preferences=[], prompt_preferences=[])
    assert "description" not in project_config_snapshot(project)


def test_change_set_prompt_mentions_new_field_paths() -> None:
    rendered_zh = render_prompt_template("change_set", _template_variables("change_set"), language="zh-CN")
    rendered_en = render_prompt_template("change_set", _template_variables("change_set"), language="en")
    assert "content.low_fidelity_screen_structure" in rendered_zh.user
    assert "content.visual_system.theme_configuration" in rendered_zh.user
    assert "content.route_definitions" in rendered_zh.user
    assert "content.low_fidelity_screen_structure" in rendered_en.user
    assert "content.visual_system.theme_configuration" in rendered_en.user
    assert "content.route_definitions" in rendered_en.user
