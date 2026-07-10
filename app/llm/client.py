from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings


class LLMConfigurationError(RuntimeError):
    """Raised when required LLM settings are missing."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM provider request fails."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM provider returns an unusable response."""


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.llm_base_url) or ""
        self.api_key = (api_key if api_key is not None else settings.llm_api_key) or ""
        self.model = (model if model is not None else settings.llm_model) or ""
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds

    def invoke(self, system_prompt: str, user_payload: dict[str, Any]) -> str:
        if not self.base_url or not self.api_key or not self.model:
            raise LLMConfigurationError("LLM 服务未配置，请检查 LLM_API_KEY 和 LLM_MODEL。")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        request_body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(url, headers=headers, json=request_body, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise LLMRequestError(f"LLM API returned HTTP {status_code}.") from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError("LLM API request failed.") from exc

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError("LLM API response format is invalid.") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM API response content is empty.")
        return content
