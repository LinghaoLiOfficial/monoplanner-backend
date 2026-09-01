from __future__ import annotations

from typing import Literal

LLMPromptLanguage = Literal["zh-CN", "en"]

DEFAULT_LLM_PROMPT_LANGUAGE: LLMPromptLanguage = "zh-CN"
SUPPORTED_LLM_PROMPT_LANGUAGES: tuple[LLMPromptLanguage, ...] = ("zh-CN", "en")


def normalize_llm_prompt_language(value: str | None) -> LLMPromptLanguage:
    if value in SUPPORTED_LLM_PROMPT_LANGUAGES:
        return value
    return DEFAULT_LLM_PROMPT_LANGUAGE


__all__ = [
    "DEFAULT_LLM_PROMPT_LANGUAGE",
    "LLMPromptLanguage",
    "SUPPORTED_LLM_PROMPT_LANGUAGES",
    "normalize_llm_prompt_language",
]
