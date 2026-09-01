from __future__ import annotations

from dataclasses import dataclass

from app.core.llm_prompt_language import DEFAULT_LLM_PROMPT_LANGUAGE, SUPPORTED_LLM_PROMPT_LANGUAGES
from app.prompts.renderer import split_rendered_prompt
from app.prompts.template_registry import PROMPT_TEMPLATE_CONTRACTS
from app.schemas.llm_prompt_template import (
    LLMPromptTemplateModuleRead,
    LLMPromptTemplateTaskRead,
    LLMPromptTemplateVersionRead,
)


@dataclass(frozen=True)
class LLMPromptTemplateTaskConfig:
    task_key: str
    task_label: str
    run_type: str
    template_name: str


@dataclass(frozen=True)
class LLMPromptTemplateModuleConfig:
    module_key: str
    module_label: str
    tasks: tuple[LLMPromptTemplateTaskConfig, ...]


ADMIN_LLM_PROMPT_TEMPLATE_MODULES: tuple[LLMPromptTemplateModuleConfig, ...] = (
    LLMPromptTemplateModuleConfig(
        module_key="project_configuration",
        module_label="项目配置",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_project_description_options",
                task_label="生成项目描述候选",
                run_type="generate_project_description_options",
                template_name="project_description_options",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="business_stories",
        module_label="敏捷业务需求池",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="decompose_business_stories",
                task_label="拆解敏捷业务需求池",
                run_type="generate_business_stories",
                template_name="business_story_decomposer",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="change_sets",
        module_label="变更集",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_change_set",
                task_label="生成分层变更集",
                run_type="generate_change_set",
                template_name="change_set",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="ux_design",
        module_label="UX 用户体验设计",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_ux_design_asset",
                task_label="生成 UX 用户体验设计资产",
                run_type="generate_design_asset",
                template_name="ux_design",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="ui_design",
        module_label="UI 视觉设计",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_ui_design_asset",
                task_label="生成 UI 视觉设计资产",
                run_type="generate_design_asset",
                template_name="ui_design",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="frontend_implementation",
        module_label="前端工程实现",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_frontend_implementation_asset",
                task_label="生成前端工程实现资产",
                run_type="generate_design_asset",
                template_name="frontend_pages",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="api_contract",
        module_label="API 契约",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_api_contract_asset",
                task_label="生成 API 契约资产",
                run_type="generate_design_asset",
                template_name="api_contract",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="backend_implementation",
        module_label="后端工程实现",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_backend_implementation_asset",
                task_label="生成后端工程实现资产",
                run_type="generate_design_asset",
                template_name="backend_implementation",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="database_models",
        module_label="数据库模型",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_database_model_asset",
                task_label="生成数据库模型资产",
                run_type="generate_design_asset",
                template_name="database_models",
            ),
        ),
    ),
    LLMPromptTemplateModuleConfig(
        module_key="prompt_pack",
        module_label="指令集合",
        tasks=(
            LLMPromptTemplateTaskConfig(
                task_key="generate_prompt_pack",
                task_label="生成指令集合",
                run_type="generate_prompt_pack",
                template_name="prompt_pack",
            ),
        ),
    ),
)


def list_admin_llm_prompt_templates() -> list[LLMPromptTemplateModuleRead]:
    contract_by_name = {contract.name: contract for contract in PROMPT_TEMPLATE_CONTRACTS}
    modules: list[LLMPromptTemplateModuleRead] = []

    for module_config in ADMIN_LLM_PROMPT_TEMPLATE_MODULES:
        tasks: list[LLMPromptTemplateTaskRead] = []
        for task_config in module_config.tasks:
            contract = contract_by_name[task_config.template_name]
            versions: list[LLMPromptTemplateVersionRead] = []
            rendered_by_language = {}
            for language in SUPPORTED_LLM_PROMPT_LANGUAGES:
                rendered = split_rendered_prompt(
                    contract.template_path(language).read_text(encoding="utf-8"),
                    template_name=f"{contract.name}:{language}",
                )
                rendered_by_language[language] = rendered
                versions.append(
                    LLMPromptTemplateVersionRead(
                        language=language,
                        system_prompt=rendered.system,
                        user_prompt_template=rendered.user,
                    )
                )
            default_rendered = rendered_by_language[DEFAULT_LLM_PROMPT_LANGUAGE]
            tasks.append(
                LLMPromptTemplateTaskRead(
                    task_key=task_config.task_key,
                    task_label=task_config.task_label,
                    run_type=task_config.run_type,
                    template_name=task_config.template_name,
                    system_prompt=default_rendered.system,
                    user_prompt_template=default_rendered.user,
                    schema_name=contract.response_model.__name__,
                    versions=versions,
                )
            )
        if tasks:
            modules.append(
                LLMPromptTemplateModuleRead(
                    module_key=module_config.module_key,
                    module_label=module_config.module_label,
                    tasks=tasks,
                )
            )

    return modules
