from typing import Any

from pydantic import BaseModel, Field


class DatabaseModelField(BaseModel):
    name: str
    type: str
    required: bool = False
    primary_key: bool = False
    nullable: bool = True
    description: str = ""


class DatabaseModelTable(BaseModel):
    name: str
    table_name: str
    description: str = ""
    fields: list[DatabaseModelField] = Field(default_factory=list)


class DatabaseModelContent(BaseModel):
    version_summary: str
    database_tables: list[DatabaseModelTable] = Field(default_factory=list)
    diff: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )


class DatabaseModelAssetOutput(BaseModel):
    title: str
    summary: str
    content: DatabaseModelContent
    diff_from_previous: dict[str, list[Any]] = Field(
        default_factory=lambda: {"added": [], "modified": [], "removed": []}
    )
