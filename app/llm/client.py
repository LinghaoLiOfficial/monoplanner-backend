from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_TEMPERATURE = 0.2
DEFAULT_RESPONSE_FORMAT = {"type": "json_object"}
REQUEST_ERROR_DETAIL = "LLM 请求失败，请检查模型服务地址、模型名称、API Key 或服务商返回信息。"
RESPONSE_FORMAT_ERROR_DETAIL = "LLM 返回的结构化结果格式不正确，请重试或调整模型配置。"
EMPTY_RESPONSE_DETAIL = "LLM 返回内容为空，无法生成结构化结果。"
CONFIGURATION_ERROR_DETAIL = "LLM 服务未配置，请检查 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL。"


class LLMConfigurationError(RuntimeError):
    """Raised when required LLM settings are missing."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM provider request fails."""


class LLMResponseFormatError(RuntimeError):
    """Raised when the LLM provider returns an unusable response."""


class LLMEmptyResponseError(LLMResponseFormatError):
    """Raised when the LLM response content is empty."""


@dataclass(frozen=True)
class LLMRequestMetadata:
    provider: str
    base_url: str
    request_url: str
    model: str
    timeout: float
    use_response_format: bool
    has_api_key: bool


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        provider: str | None = None,
        use_response_format: bool | None = None,
    ) -> None:
        self.provider = (provider if provider is not None else settings.llm_provider).strip()
        configured_base_url = base_url if base_url is not None else settings.llm_base_url
        self.base_url = (configured_base_url or "").strip()
        self.api_key = ((api_key if api_key is not None else settings.llm_api_key) or "").strip()
        self.model = ((model if model is not None else settings.llm_model) or "").strip()
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self.use_response_format = (
            use_response_format
            if use_response_format is not None
            else settings.llm_use_response_format
        )

    @property
    def metadata(self) -> LLMRequestMetadata:
        return LLMRequestMetadata(
            provider=self.provider,
            base_url=self.base_url,
            request_url=build_chat_completions_url(self.base_url),
            model=self.model,
            timeout=self.timeout,
            use_response_format=self.use_response_format,
            has_api_key=bool(self.api_key),
        )

    def invoke(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        self._validate_configuration()
        request_url = build_chat_completions_url(self.base_url)
        request_body = self._build_request_body(system_prompt, user_payload, extra_params)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "llm.request.start provider=%s base_url=%s model=%s timeout=%s use_response_format=%s",
            self.provider,
            self.base_url,
            self.model,
            self.timeout,
            self.use_response_format,
        )
        try:
            response = httpx.post(
                request_url,
                headers=headers,
                json=request_body,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "llm.request.failed status_code=None error_type=%s message=%s",
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise LLMRequestError("LLM API request failed before receiving a response.") from exc

        if response.status_code < 200 or response.status_code >= 300:
            response_excerpt = _excerpt(response.text, 1000)
            if response.status_code == 400 and _mentions_response_format(response.text):
                logger.warning(
                    "llm.request.failed status_code=%s reason=response_format_unsupported "
                    "response_excerpt=%s",
                    response.status_code,
                    response_excerpt,
                )
            else:
                logger.warning(
                    "llm.request.failed status_code=%s response_excerpt=%s",
                    response.status_code,
                    response_excerpt,
                )
            raise LLMRequestError(f"LLM API returned HTTP {response.status_code}.")

        logger.info(
            "llm.request.success status_code=%s content_length=%s",
            response.status_code,
            len(response.text or ""),
        )
        return extract_chat_completion_content(response)

    def stream(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        extra_params: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        self._validate_configuration()
        request_url = build_chat_completions_url(self.base_url)
        request_body = self._build_request_body(system_prompt, user_payload, extra_params)
        request_body["stream"] = True
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "llm.stream.start provider=%s base_url=%s model=%s timeout=%s use_response_format=%s",
            self.provider,
            self.base_url,
            self.model,
            self.timeout,
            self.use_response_format,
        )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    request_url,
                    headers=headers,
                    json=request_body,
                ) as response:
                    if response.status_code < 200 or response.status_code >= 300:
                        response_text = response.read().decode("utf-8", errors="replace")
                        logger.warning(
                            "llm.stream.failed status_code=%s response_excerpt=%s",
                            response.status_code,
                            _excerpt(response_text, 1000),
                        )
                        raise LLMRequestError(
                            f"LLM API returned HTTP {response.status_code}."
                        )

                    for line in response.iter_lines():
                        delta = extract_chat_completion_stream_delta(line)
                        if delta is None:
                            continue
                        yield delta
        except LLMRequestError:
            raise
        except httpx.HTTPError as exc:
            logger.warning(
                "llm.stream.failed status_code=None error_type=%s message=%s",
                type(exc).__name__,
                _excerpt(str(exc), 500),
            )
            raise LLMRequestError("LLM API stream request failed.") from exc
        logger.info("llm.stream.success provider=%s model=%s", self.provider, self.model)

    def _validate_configuration(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("LLM_API_KEY")
        if not self.base_url:
            missing.append("LLM_BASE_URL")
        if not self.model:
            missing.append("LLM_MODEL")
        if missing:
            logger.warning(
                "llm.configuration.missing provider=%s base_url=%s model=%s "
                "has_api_key=%s missing=%s",
                self.provider,
                self.base_url,
                self.model,
                bool(self.api_key),
                ",".join(missing),
            )
            raise LLMConfigurationError(f"Missing LLM configuration: {', '.join(missing)}.")

    def _build_request_body(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        request_body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                },
            ],
            "temperature": DEFAULT_TEMPERATURE,
        }
        if self.use_response_format:
            request_body["response_format"] = DEFAULT_RESPONSE_FORMAT
        if extra_params:
            request_body.update(extra_params)
        return request_body


def build_chat_completions_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return "/chat/completions"
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def extract_chat_completion_content(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning(
            "llm.response.invalid reason=non_json status_code=%s content_excerpt=%s",
            response.status_code,
            _excerpt(response.text, 1000),
        )
        raise LLMResponseFormatError("LLM response body is not JSON.") from exc

    try:
        choices = payload["choices"]
    except (KeyError, TypeError) as exc:
        logger.warning("llm.response.invalid reason=missing_choices")
        raise LLMResponseFormatError("LLM response missing choices.") from exc
    if not isinstance(choices, list) or not choices:
        logger.warning("llm.response.invalid reason=empty_choices")
        raise LLMResponseFormatError("LLM response choices is empty.")

    try:
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, TypeError) as exc:
        logger.warning("llm.response.invalid reason=missing_message_content")
        raise LLMResponseFormatError("LLM response missing message content.") from exc
    if not isinstance(content, str) or not content.strip():
        logger.warning("llm.response.invalid reason=empty_content")
        raise LLMEmptyResponseError("LLM response content is empty.")
    return content


def extract_chat_completion_stream_delta(line: str | bytes) -> str | None:
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if not line.startswith("data:"):
        return None

    data = line.removeprefix("data:").strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        logger.warning(
            "llm.stream.invalid reason=invalid_json line_excerpt=%s",
            _excerpt(data, 1000),
        )
        return None

    if isinstance(payload, dict) and payload.get("error") is not None:
        logger.warning("llm.stream.invalid reason=provider_error")
        raise LLMRequestError("LLM stream returned an error chunk.")
    if not isinstance(payload, dict):
        logger.warning("llm.stream.invalid reason=payload_not_object")
        raise LLMResponseFormatError("LLM stream chunk must be a JSON object.")

    choices = payload.get("choices")
    if choices is None:
        return None
    if not isinstance(choices, list):
        logger.warning("llm.stream.invalid reason=choices_not_list")
        raise LLMResponseFormatError("LLM stream chunk choices must be a list.")
    if not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        logger.warning("llm.stream.invalid reason=choice_not_object")
        raise LLMResponseFormatError("LLM stream choice must be an object.")

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if content is None:
            return None
        if not isinstance(content, str):
            logger.warning("llm.stream.invalid reason=delta_content_not_string")
            raise LLMResponseFormatError("LLM stream delta content must be a string.")
        return content

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if content is None:
            return None
        if not isinstance(content, str):
            logger.warning("llm.stream.invalid reason=message_content_not_string")
            raise LLMResponseFormatError("LLM stream message content must be a string.")
        return content

    text = first_choice.get("text")
    if text is None:
        return None
    if not isinstance(text, str):
        logger.warning("llm.stream.invalid reason=text_not_string")
        raise LLMResponseFormatError("LLM stream text must be a string.")
    return text


def _mentions_response_format(text: str) -> bool:
    lowered = text.lower()
    return "response_format" in lowered or "json_object" in lowered


def _excerpt(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."
