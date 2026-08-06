from typing import Any

from pydantic import BaseModel, Field


class DesignAssetContent(BaseModel):
    version_summary: str
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class DesignAssetOutput(BaseModel):
    title: str
    summary: str
    content: DesignAssetContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )

