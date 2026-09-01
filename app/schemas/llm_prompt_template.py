from pydantic import BaseModel


class LLMPromptTemplateVersionRead(BaseModel):
    language: str
    system_prompt: str
    user_prompt_template: str


class LLMPromptTemplateTaskRead(BaseModel):
    task_key: str
    task_label: str
    run_type: str
    template_name: str
    system_prompt: str
    user_prompt_template: str
    schema_name: str
    versions: list[LLMPromptTemplateVersionRead]


class LLMPromptTemplateModuleRead(BaseModel):
    module_key: str
    module_label: str
    tasks: list[LLMPromptTemplateTaskRead]
