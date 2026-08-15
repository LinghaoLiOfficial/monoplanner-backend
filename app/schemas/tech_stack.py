from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TechStackType = Literal[
    "framework",
    "language",
    "ui_library",
    "package_manager",
    "database",
    "orm",
    "migration_tool",
    "runtime",
    "build_tool",
]


class TechStackItem(BaseModel):
    name: str
    type: TechStackType
    tags: list[str] = Field(default_factory=list)
    role: str | None = None

    model_config = ConfigDict(extra="ignore")
