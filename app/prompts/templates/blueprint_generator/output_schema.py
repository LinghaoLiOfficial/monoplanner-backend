from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.tech_stack import TechStackItem


class BlueprintTechStack(BaseModel):
    frontend: list[TechStackItem]
    backend: list[TechStackItem]


class BlueprintProject(BaseModel):
    name: str
    one_liner: str
    target_users: list[str]
    business_goal: str
    tech_stack: BlueprintTechStack


class BlueprintProductGoal(BaseModel):
    goal: str
    priority: Literal["must_have", "should_have", "could_have"] = "must_have"


class BlueprintUserRole(BaseModel):
    name: str
    description: str
    permissions: list[str]


class BlueprintCoreModule(BaseModel):
    name: str
    description: str
    features: list[str]


class BlueprintDomainField(BaseModel):
    name: str
    type: str
    required: bool = False
    description: str = ""


class BlueprintDomainEntity(BaseModel):
    name: str
    description: str
    fields: list[BlueprintDomainField]
    relationships: list[str] = Field(default_factory=list)


class BlueprintPage(BaseModel):
    path: str
    name: str
    purpose: str
    components: list[str] = Field(default_factory=list)
    data_dependencies: list[str] = Field(default_factory=list)


class BlueprintApiNeed(BaseModel):
    resource: str
    operations: list[str]
    consumers: list[str] = Field(default_factory=list)


class BlueprintBusinessRequirementStory(BaseModel):
    title: str
    priority: Literal["p1_must", "p2_should", "p3_could", "p4_wont"] = "p1_must"
    status: str
    user_story: str


class BlueprintNonFunctionalRequirements(BaseModel):
    auth: str
    performance: str
    security: str
    observability: str


class ProjectBlueprintOutput(BaseModel):
    project: BlueprintProject
    tech_stack: BlueprintTechStack
    product_goals: list[BlueprintProductGoal]
    user_roles: list[BlueprintUserRole]
    core_modules: list[BlueprintCoreModule]
    domain_entities: list[BlueprintDomainEntity]
    pages: list[BlueprintPage]
    api_needs: list[BlueprintApiNeed]
    business_requirement_stories: list[BlueprintBusinessRequirementStory] = Field(
        default_factory=list
    )
    non_functional_requirements: BlueprintNonFunctionalRequirements
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
