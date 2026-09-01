from typing import Any

from pydantic import BaseModel, Field, field_validator

VALID_TOKEN_STATUSES = {"validated", "normative", "tbd", "inferred"}


class UIDesignStyle(BaseModel):
    style_description: str
    signature_traits: list[str] = Field(default_factory=list)


class UIThemeTypes(BaseModel):
    light_mode: str
    dark_mode: str


class UIThemeConfiguration(BaseModel):
    theme_types: UIThemeTypes
    default_theme: str

    @field_validator("default_theme")
    @classmethod
    def default_theme_must_be_user_visible(cls, value: str) -> str:
        if value.strip() in {"light_mode", "dark_mode"}:
            raise ValueError(
                "default_theme must be a user-visible theme name or description, "
                "not the technical theme_types field key."
            )
        return value


class UIDesignToken(BaseModel):
    token_name: str = ""
    token_type: str | None = None
    token_value: str | dict[str, Any] = ""
    description: str | None = None
    semantic_role: str | None = None
    usage_context: str | None = None
    anti_usage: list[str] | str | None = Field(default_factory=list)
    css_variable: str | None = None
    tailwind_variable: str | None = None
    validated_status: str | None = None
    source_basis: list[str] | str | None = Field(default_factory=list)
    contrast_notes: str | None = None

    @field_validator("validated_status")
    @classmethod
    def validated_status_must_be_known(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_TOKEN_STATUSES:
            raise ValueError(
                "validated_status must be one of validated, normative, tbd, inferred."
            )
        return value


class UIDesignTokenSystem(BaseModel):
    description: str | None = None
    rules: list[str] = Field(default_factory=list)
    tokens: list[UIDesignToken] = Field(default_factory=list)
    tbd_items: list[str] = Field(default_factory=list)


class UILegacyVisualTokenGroup(BaseModel):
    group_name: str | None = None
    description: str | None = None
    tokens: list[UIDesignToken] = Field(default_factory=list)


class UIInteractionStateRule(BaseModel):
    state_name: str
    visual_cues: list[str] = Field(default_factory=list)
    usage_context: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class UIVisualSystem(BaseModel):
    design_style: UIDesignStyle
    style_tags: list[str] = Field(default_factory=list)
    design_principles: list[str] = Field(default_factory=list)
    theme_configuration: UIThemeConfiguration
    evidence_policy: str | None = None
    source_references: list[str] = Field(default_factory=list)
    tbd_items: list[str] = Field(default_factory=list)
    accessibility_rules: list[str] = Field(default_factory=list)
    responsive_contract: list[str] = Field(default_factory=list)
    color_system: UIDesignTokenSystem | list[str] = Field(default_factory=UIDesignTokenSystem)
    typography_system: UIDesignTokenSystem | list[str] = Field(default_factory=UIDesignTokenSystem)
    spacing_system: UIDesignTokenSystem | list[str] = Field(default_factory=UIDesignTokenSystem)
    shape_system: UIDesignTokenSystem | list[str] = Field(default_factory=UIDesignTokenSystem)
    elevation_system: UIDesignTokenSystem | list[str] = Field(default_factory=UIDesignTokenSystem)
    interaction_visual_system: UIDesignTokenSystem | list[str] = Field(
        default_factory=UIDesignTokenSystem
    )
    tailwind_theme_css: str | None = None
    token_catalog: list[UILegacyVisualTokenGroup] = Field(default_factory=list)
    interaction_state_matrix: list[UIInteractionStateRule] = Field(default_factory=list)


class UILayoutRule(BaseModel):
    target_screen: str
    desktop_layout: str
    mobile_layout: str
    primary_action: str | None = None
    desktop_grid: str | None = None
    mobile_reflow: str | None = None
    container_rules: list[str] = Field(default_factory=list)


class UIVisualPriority(BaseModel):
    primary_content: list[str] = Field(default_factory=list)
    secondary_content: list[str] = Field(default_factory=list)
    tertiary_content: list[str] = Field(default_factory=list)
    primary_actions: list[str] = Field(default_factory=list)
    secondary_actions: list[str] = Field(default_factory=list)
    danger_actions: list[str] = Field(default_factory=list)


class UIComponentStyleRule(BaseModel):
    component_name: str
    visual_priority: UIVisualPriority
    style_rules: list[str] = Field(default_factory=list)
    states: list[UIInteractionStateRule] = Field(default_factory=list)
    responsive_behavior: list[str] = Field(default_factory=list)
    accessibility_notes: list[str] = Field(default_factory=list)
    implementation_hint: str | None = None


class UIDesignContent(BaseModel):
    version_summary: str
    visual_system: UIVisualSystem
    layout_rules: list[UILayoutRule] = Field(default_factory=list)
    component_style_rules: list[UIComponentStyleRule] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class UIDesignOutput(BaseModel):
    title: str
    summary: str
    content: UIDesignContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
