from typing import Any

from pydantic import BaseModel, Field


class UIDesignStyle(BaseModel):
    style_description: str
    signature_traits: list[str] = Field(default_factory=list)


class UIThemeTypes(BaseModel):
    light_mode: str
    dark_mode: str


class UIThemeConfiguration(BaseModel):
    theme_types: UIThemeTypes
    default_theme: str


class UIVisualSystem(BaseModel):
    design_style: UIDesignStyle
    design_principles: list[str] = Field(default_factory=list)
    theme_configuration: UIThemeConfiguration
    color_system: list[str] = Field(default_factory=list)
    typography_system: list[str] = Field(default_factory=list)
    spacing_system: list[str] = Field(default_factory=list)
    shape_system: list[str] = Field(default_factory=list)
    elevation_system: list[str] = Field(default_factory=list)
    interaction_visual_system: list[str] = Field(default_factory=list)


class UILayoutRule(BaseModel):
    target_screen: str
    desktop_layout: str
    mobile_layout: str


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
