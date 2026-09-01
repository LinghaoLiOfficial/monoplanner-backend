from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.user import User
from app.schemas.llm_prompt_template import LLMPromptTemplateModuleRead
from app.services.llm_prompt_template_service import list_admin_llm_prompt_templates

router = APIRouter(prefix="/admin/llm-prompt-templates")
AdminUser = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[LLMPromptTemplateModuleRead])
def get_admin_llm_prompt_templates(_: AdminUser) -> list[LLMPromptTemplateModuleRead]:
    return list_admin_llm_prompt_templates()
