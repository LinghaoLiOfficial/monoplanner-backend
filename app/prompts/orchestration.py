from __future__ import annotations

from typing import Any

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

SYSTEM_PROMPT = (
    "你是一个资深全栈上下文编排器。你只生成结构化设计资产和 Codex 指令，不生成业务代码。"
    "你必须只输出严格 JSON object，不要 Markdown、解释文字、注释或 JSON 之外的字符。"
)


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
        "output_contract": {
            "title": "string",
            "implementation_scope": "frontend_only | backend_only | fullstack | non_code",
            "affected_layers": [
                *ORDERED_AFFECTED_LAYERS,
            ],
            "impact_summary": "string",
            "module_changes": MODULE_CHANGE_CONTRACT,
            "risks": [],
            "open_questions": [],
            "recommended_prompt_strategy": {},
            "content": {},
            "diff": {"added": [], "modified": [], "removed": []},
        },
        "rules": [
            "affected_layers 必须至少包含一个具体设计资产层",
            "改用户路径、交互流程、状态反馈、空状态、错误状态、权限体验时包含 ux_design",
            "改视觉层级、布局、颜色语义、组件样式、按钮层级、Badge、响应式规则时包含 ui_design",
            "改页面、组件、路由、目录、API client 落点时包含 frontend_pages",
            "frontend_only 不要强制更新后端服务、后端工具或数据库模型",
            "backend_only 不要强制更新前端页面或前端工具",
            "module_changes 必须按 affected_layers 描述 added/modified/removed/unchanged",
        ],
    }


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
        "rules": _design_asset_rules(layer),
    }


def _design_asset_output_contract(layer: str) -> dict[str, Any]:
    base = {
        "title": "string",
        "summary": "string",
        "content": {
            "version_summary": "string",
            "diff": {"added": [], "modified": [], "removed": []},
        },
        "diff_from_previous": {"added": [], "modified": [], "removed": []},
    }
    if layer == "ux_design":
        base["content"] = {
            "version_summary": "string",
            "user_goals": [
                {
                    "goal_id": "string",
                    "description": "string",
                    "related_story_ids": ["uuid"],
                }
            ],
            "user_flows": [
                {
                    "flow_id": "string",
                    "name": "string",
                    "entry_point": "string",
                    "steps": [
                        {
                            "step": 1,
                            "user_action": "string",
                            "system_feedback": "string",
                        }
                    ],
                    "success_outcome": "string",
                    "failure_outcome": "string",
                }
            ],
            "interaction_states": [
                {
                    "state": "idle | loading | success | error | empty | disabled",
                    "description": "string",
                }
            ],
            "empty_states": [{"target": "string", "message": "string"}],
            "error_states": [
                {"target": "string", "message": "string", "recovery_action": "string"}
            ],
            "permission_experience": [{"role": "string", "experience": "string"}],
            "accessibility_requirements": ["string"],
            "diff": {"added": [], "modified": [], "removed": []},
        }
    elif layer == "ui_design":
        base["content"] = {
            "version_summary": "string",
            "visual_hierarchy": [{"target": "string", "rule": "string"}],
            "layout_guidelines": [
                {"target": "string", "desktop": "string", "mobile": "string"}
            ],
            "component_style_rules": [{"component": "string", "rules": ["string"]}],
            "badge_rules": [
                {
                    "type": "string",
                    "items": [
                        {
                            "value": "string",
                            "label": "string",
                            "visual_intent": "string",
                        }
                    ],
                }
            ],
            "button_rules": [
                {
                    "button": "string",
                    "priority": "primary | secondary | ghost | destructive",
                    "states": ["string"],
                }
            ],
            "form_rules": [{"target": "string", "rules": ["string"]}],
            "responsive_rules": ["string"],
            "accessibility_visual_rules": ["string"],
            "diff": {"added": [], "modified": [], "removed": []},
        }
    elif layer == "frontend_pages":
        base["content"] = {
            "version_summary": "string",
            "pages": [],
            "components": [
                {
                    "component_id": "string",
                    "name": "string",
                    "purpose": "string",
                    "used_by_pages": [],
                    "ux_refs": [],
                    "ui_refs": [],
                }
            ],
            "directory_structure": [],
            "data_flow": [],
            "diff": {"added": [], "modified": [], "removed": []},
        }
    return base


def _design_asset_rules(layer: str) -> list[str]:
    rules = [
        "只生成当前 layer 的结构化设计资产",
        "content 必须是 JSON object",
        "diff_from_previous 必须总结相对 previous_version 的变化",
        "不要生成业务代码",
    ]
    if layer == "ux_design":
        rules.extend(
            [
                "UX 设计只描述用户如何完成任务，包括目标、流程、交互状态、反馈、"
                "空状态、错误状态、权限体验和可访问性",
                "不要输出视觉样式、组件外观或代码目录落点",
            ]
        )
    elif layer == "ui_design":
        rules.extend(
            [
                "UI 设计必须基于 related_assets.ux_design，描述界面如何呈现任务",
                "只描述视觉层级、布局、组件样式、按钮、Badge、表单、响应式和视觉可访问性",
                "不要重新发明用户流程或代码目录落点",
            ]
        )
    elif layer == "frontend_pages":
        rules.extend(
            [
                "必须读取 related_assets.ux_design 和 related_assets.ui_design",
                "前端页面结构只负责页面、组件、路由、目录、文件路径、数据依赖和 API client 落点",
                "不要重复大段 UX/UI 自然语言，用 ux_refs 和 ui_refs 建立引用",
            ]
        )
    return rules


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
        "output_contract": {
            "project": {},
            "current_product_scope": {},
            "business_capabilities": [],
            "ux_summary": {
                "core_user_flows": [],
                "key_interaction_principles": [],
            },
            "ui_summary": {
                "design_principles": [],
                "component_language": [],
            },
            "frontend_summary": {},
            "backend_summary": {},
            "architecture_notes": [],
            "risks": [],
            "open_questions": [],
            "version_summary": "string",
        },
        "rules": [
            "返回聚合摘要，不要生成代码",
            "必须体现最新 change_set 的影响",
            "必须基于 design_assets.ux_design 输出 ux_summary",
            "必须基于 design_assets.ui_design 输出 ui_summary",
        ],
    }


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
        "output_contract": {
            "batch_summary": "string",
            "implementation_scope": "frontend_only | backend_only | fullstack | non_code",
            "frontend_prompt": {
                "needed": True,
                "title": "string",
                "prompt": "string",
                "affected_files": [],
                "do_not_modify": [],
                "verification_steps": [],
            },
            "backend_prompt": {
                "needed": True,
                "title": "string",
                "prompt": "string",
                "affected_files": [],
                "do_not_modify": [],
                "verification_steps": [],
            },
            "diff_summary": {},
            "execution_order": [],
            "acceptance_checklist": [],
            "rollback_notes": [],
        },
        "rules": [
            "生成 Codex 可执行指令，不要生成业务代码",
            "前后端 prompt 可按 scope 设置 needed",
            "前端 prompt 必须结合 ux_design、ui_design、frontend_pages、frontend_tools 的差异",
            "当 UX/UI 发生变化时，diff_summary 必须包含 ux_design/ui_design 摘要",
        ],
    }
