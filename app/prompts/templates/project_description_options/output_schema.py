from pydantic import BaseModel, Field, field_validator


class ProjectDescriptionOption(BaseModel):
    description: str = Field(min_length=1)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("description must not be blank")
        return normalized


class ProjectDescriptionOptionsOutput(BaseModel):
    options: list[ProjectDescriptionOption] = Field(min_length=3, max_length=3)

