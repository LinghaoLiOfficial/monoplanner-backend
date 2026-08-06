from pydantic import BaseModel, Field


class DatabaseInfo(BaseModel):
    engine: str = "PostgreSQL"
    orm: str = "SQLAlchemy 2.x"
    migration_tool: str = "Alembic"


class DbModelField(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    nullable: bool = True
    description: str = ""


class DbModelRelationship(BaseModel):
    field: str
    target: str
    type: str


class DbModelEntity(BaseModel):
    name: str
    table_name: str
    description: str = ""
    fields: list[DbModelField]
    relationships: list[DbModelRelationship] = Field(default_factory=list)


class DbModelIndex(BaseModel):
    table: str
    fields: list[str]
    reason: str


class DbModelOutput(BaseModel):
    database: DatabaseInfo
    entities: list[DbModelEntity]
    relationships: list[DbModelRelationship] = Field(default_factory=list)
    indexes: list[DbModelIndex] = Field(default_factory=list)
    migration_notes: list[str] = Field(default_factory=list)
