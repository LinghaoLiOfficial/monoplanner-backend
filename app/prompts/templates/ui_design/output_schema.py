from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UIDesignStyle(StrictModel):
    style_description: str
    signature_traits: list[str] = Field(default_factory=list)


class UIThemeTypes(StrictModel):
    light_mode: str
    dark_mode: str


class UIThemeConfiguration(StrictModel):
    theme_types: UIThemeTypes
    default_theme: str

    @field_validator("default_theme")
    @classmethod
    def default_theme_must_be_user_visible(cls, value: str) -> str:
        if value.strip() in {"light_mode", "dark_mode"}:
            raise ValueError(
                "default_theme must be a user-visible theme name or description, not the technical field key."
            )
        return value


class UIColorEntry(StrictModel):
    color_name: str
    hex_value: str
    color_description: str


class UIColorConfiguration(StrictModel):
    description: str
    rules: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    colors: list[UIColorEntry] = Field(default_factory=list)


class UIFontEntry(StrictModel):
    font_name: str
    font_family: str
    font_size: str
    font_weight: str
    font_description: str


class UIFontConfiguration(StrictModel):
    description: str
    rules: list[str] = Field(default_factory=list)
    fonts: list[UIFontEntry] = Field(default_factory=list)


class UISpacingEntry(StrictModel):
    spacing_name: str
    spacing_size: str


class UISpacingConfiguration(StrictModel):
    description: str
    rules: list[str] = Field(default_factory=list)
    spacings: list[UISpacingEntry] = Field(default_factory=list)


class UIShapeEntry(StrictModel):
    shape_name: str
    shape_size: str


class UIShapeConfiguration(StrictModel):
    description: str
    rules: list[str] = Field(default_factory=list)
    shapes: list[UIShapeEntry] = Field(default_factory=list)


class UIShadowEntry(StrictModel):
    shadow_name: str
    shadow_size: str


class UIShadowConfiguration(StrictModel):
    description: str
    rules: list[str] = Field(default_factory=list)
    shadows: list[UIShadowEntry] = Field(default_factory=list)


class UIVisualSystem(StrictModel):
    design_style: UIDesignStyle
    theme_configuration: UIThemeConfiguration
    color_configuration: UIColorConfiguration
    font_configuration: UIFontConfiguration
    spacing_configuration: UISpacingConfiguration
    shape_configuration: UIShapeConfiguration
    shadow_configuration: UIShadowConfiguration


class UIDesignContent(StrictModel):
    version_summary: str
    visual_system: UIVisualSystem
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class UIDesignOutput(StrictModel):
    title: str
    summary: str
    content: UIDesignContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
