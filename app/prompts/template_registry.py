from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

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

TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class PromptTemplateContract:
    name: str
    template_path: Path
    schema_path: Path
    response_model: type[BaseModel]


PROMPT_TEMPLATE_CONTRACTS: tuple[PromptTemplateContract, ...] = (
    PromptTemplateContract(
        name="business_story_decomposer",
        template_path=TEMPLATE_ROOT / "business_story_decomposer" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "business_story_decomposer" / "output_schema.py",
        response_model=BusinessStoryDecompositionOutput,
    ),
    PromptTemplateContract(
        name="blueprint_generator",
        template_path=TEMPLATE_ROOT / "blueprint_generator" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "blueprint_generator" / "output_schema.py",
        response_model=ProjectBlueprintOutput,
    ),
    PromptTemplateContract(
        name="api_contract_generator",
        template_path=TEMPLATE_ROOT / "api_contract_generator" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "api_contract_generator" / "output_schema.py",
        response_model=ApiContractOutput,
    ),
    PromptTemplateContract(
        name="db_model_generator",
        template_path=TEMPLATE_ROOT / "db_model_generator" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "db_model_generator" / "output_schema.py",
        response_model=DbModelOutput,
    ),
    PromptTemplateContract(
        name="change_set",
        template_path=TEMPLATE_ROOT / "change_set" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "change_set" / "output_schema.py",
        response_model=ChangeSetOutput,
    ),
    PromptTemplateContract(
        name="design_asset",
        template_path=TEMPLATE_ROOT / "design_asset" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "design_asset" / "output_schema.py",
        response_model=DesignAssetOutput,
    ),
    PromptTemplateContract(
        name="ux_design",
        template_path=TEMPLATE_ROOT / "ux_design" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "ux_design" / "output_schema.py",
        response_model=UXDesignOutput,
    ),
    PromptTemplateContract(
        name="ui_design",
        template_path=TEMPLATE_ROOT / "ui_design" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "ui_design" / "output_schema.py",
        response_model=UIDesignOutput,
    ),
    PromptTemplateContract(
        name="frontend_pages",
        template_path=TEMPLATE_ROOT / "frontend_pages" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "frontend_pages" / "output_schema.py",
        response_model=FrontendPagesOutput,
    ),
    PromptTemplateContract(
        name="blueprint_summary",
        template_path=TEMPLATE_ROOT / "blueprint_summary" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "blueprint_summary" / "output_schema.py",
        response_model=BlueprintSummaryOutput,
    ),
    PromptTemplateContract(
        name="prompt_pack",
        template_path=TEMPLATE_ROOT / "prompt_pack" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "prompt_pack" / "output_schema.py",
        response_model=PromptPackOutput,
    ),
    PromptTemplateContract(
        name="context_pack",
        template_path=TEMPLATE_ROOT / "context_pack" / "prompt.j2",
        schema_path=TEMPLATE_ROOT / "context_pack" / "output_schema.py",
        response_model=ContextPackOutput,
    ),
)
