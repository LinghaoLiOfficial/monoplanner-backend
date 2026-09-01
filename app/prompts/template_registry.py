from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.core.llm_prompt_language import (
    DEFAULT_LLM_PROMPT_LANGUAGE,
    SUPPORTED_LLM_PROMPT_LANGUAGES,
    LLMPromptLanguage,
)
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

TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class PromptTemplateContract:
    name: str
    schema_path: Path
    response_model: type[BaseModel]

    def template_path(self, language: str | None = DEFAULT_LLM_PROMPT_LANGUAGE) -> Path:
        normalized = (
            language
            if language in SUPPORTED_LLM_PROMPT_LANGUAGES
            else DEFAULT_LLM_PROMPT_LANGUAGE
        )
        return TEMPLATE_ROOT / self.name / f"prompt.{normalized}.j2"

    @property
    def template_paths(self) -> dict[LLMPromptLanguage, Path]:
        return {
            language: self.template_path(language)
            for language in SUPPORTED_LLM_PROMPT_LANGUAGES
        }


PROMPT_TEMPLATE_CONTRACTS: tuple[PromptTemplateContract, ...] = (
    PromptTemplateContract(
        name="business_story_decomposer",
        schema_path=TEMPLATE_ROOT / "business_story_decomposer" / "output_schema.py",
        response_model=BusinessStoryDecompositionOutput,
    ),
    PromptTemplateContract(
        name="blueprint_generator",
        schema_path=TEMPLATE_ROOT / "blueprint_generator" / "output_schema.py",
        response_model=ProjectBlueprintOutput,
    ),
    PromptTemplateContract(
        name="project_description_options",
        schema_path=TEMPLATE_ROOT / "project_description_options" / "output_schema.py",
        response_model=ProjectDescriptionOptionsOutput,
    ),
    PromptTemplateContract(
        name="api_contract_generator",
        schema_path=TEMPLATE_ROOT / "api_contract_generator" / "output_schema.py",
        response_model=ApiContractOutput,
    ),
    PromptTemplateContract(
        name="api_contract",
        schema_path=TEMPLATE_ROOT / "api_contract" / "output_schema.py",
        response_model=ApiContractAssetOutput,
    ),
    PromptTemplateContract(
        name="backend_implementation",
        schema_path=TEMPLATE_ROOT / "backend_implementation" / "output_schema.py",
        response_model=BackendImplementationOutput,
    ),
    PromptTemplateContract(
        name="db_model_generator",
        schema_path=TEMPLATE_ROOT / "db_model_generator" / "output_schema.py",
        response_model=DbModelOutput,
    ),
    PromptTemplateContract(
        name="database_models",
        schema_path=TEMPLATE_ROOT / "database_models" / "output_schema.py",
        response_model=DatabaseModelAssetOutput,
    ),
    PromptTemplateContract(
        name="change_set",
        schema_path=TEMPLATE_ROOT / "change_set" / "output_schema.py",
        response_model=ChangeSetOutput,
    ),
    PromptTemplateContract(
        name="design_asset",
        schema_path=TEMPLATE_ROOT / "design_asset" / "output_schema.py",
        response_model=DesignAssetOutput,
    ),
    PromptTemplateContract(
        name="ux_design",
        schema_path=TEMPLATE_ROOT / "ux_design" / "output_schema.py",
        response_model=UXDesignOutput,
    ),
    PromptTemplateContract(
        name="ui_design",
        schema_path=TEMPLATE_ROOT / "ui_design" / "output_schema.py",
        response_model=UIDesignOutput,
    ),
    PromptTemplateContract(
        name="frontend_pages",
        schema_path=TEMPLATE_ROOT / "frontend_pages" / "output_schema.py",
        response_model=FrontendPagesOutput,
    ),
    PromptTemplateContract(
        name="blueprint_summary",
        schema_path=TEMPLATE_ROOT / "blueprint_summary" / "output_schema.py",
        response_model=BlueprintSummaryOutput,
    ),
    PromptTemplateContract(
        name="prompt_pack",
        schema_path=TEMPLATE_ROOT / "prompt_pack" / "output_schema.py",
        response_model=PromptPackOutput,
    ),
    PromptTemplateContract(
        name="context_pack",
        schema_path=TEMPLATE_ROOT / "context_pack" / "output_schema.py",
        response_model=ContextPackOutput,
    ),
)
