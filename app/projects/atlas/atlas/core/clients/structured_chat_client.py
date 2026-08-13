from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from atlas.core.clients.http_retry import post_json_with_retry
from atlas.core.llm import KeyPool
from atlas.models import (
    LLMModelCfg,
    ModelProvider,
    REASONING_PROVIDERS,
    StructuredOutputMode,
    ThinkingMode,
)

T = TypeVar("T", bound=BaseModel)


class StructuredChatClient:
    """Provider-neutral OpenAI-compatible JSON/JSON-Schema chat adapter.

    Uses a KeyPool so concurrent calls spread across multiple API keys, each
    capped at its own max_concurrency. Business parameters (temperature,
    thinking_mode, max_tokens) are per-call, falling back to model defaults.
    """

    def __init__(
        self,
        config: LLMModelCfg,
        key_pool: KeyPool,
        *,
        client: httpx.AsyncClient | None = None,
        maximum_attempts: int = 3,
        request_maximum_attempts: int = 4,
        retry_base_seconds: float = 1,
    ) -> None:
        self.config = config
        self.key_pool = key_pool
        self.maximum_attempts = maximum_attempts
        self.request_maximum_attempts = request_maximum_attempts
        self.retry_base_seconds = retry_base_seconds
        self._client = client or httpx.AsyncClient(timeout=config.timeout_seconds)

    @property
    def model_id(self) -> str:
        return self.config.model

    def _apply_reasoning(
        self, payload: dict, thinking: ThinkingMode
    ) -> None:
        """Attach the provider-correct reasoning/thinking parameter.

        OpenRouter uses ``reasoning: {enabled: true}``; Zhipu-style providers
        use ``thinking: {type: enabled|disabled}``. Only an explicitly enabled
        mode is sent to OpenRouter (it has no "disabled" shape).
        """
        if self.config.provider in REASONING_PROVIDERS:
            if thinking == ThinkingMode.ENABLED:
                payload["reasoning"] = {"enabled": True}
        else:
            payload["thinking"] = {"type": thinking.value}

    async def complete_model(
        self,
        response_model: type[T],
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        thinking_mode: ThinkingMode | None = None,
        max_tokens: int | None = None,
    ) -> T:
        temp = self.config.temperature if temperature is None else temperature
        thinking = self.config.thinking_mode if thinking_mode is None else thinking_mode
        tokens = self.config.maximum_output_tokens if max_tokens is None else max_tokens

        schema = response_model.model_json_schema()
        supports_response_format = self.config.capabilities.response_format_api
        response_format: dict | None
        if self.config.structured_output_mode == StructuredOutputMode.JSON_SCHEMA:
            if supports_response_format:
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    },
                }
            else:
                response_format = None
                user_prompt += (
                    "\n必须只输出 JSON，并严格满足以下 JSON Schema：\n"
                    + json.dumps(schema, ensure_ascii=False)
                )
        else:
            response_format = {"type": "json_object"} if supports_response_format else None
            user_prompt += (
                "\n必须只输出 JSON，并严格满足以下 JSON Schema：\n"
                + json.dumps(schema, ensure_ascii=False)
            )
        rejected_errors: list[str] = []
        for _ in range(self.maximum_attempts):
            attempt_prompt = user_prompt
            if rejected_errors:
                attempt_prompt += (
                    "\nPrevious output was rejected. Return a complete new JSON "
                    "object; do not patch the old output. Errors: "
                    + json.dumps(rejected_errors[-1:], ensure_ascii=False)
                )
            request_payload: dict = {
                "model": self.config.model,
                "temperature": temp,
                "max_tokens": tokens,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": attempt_prompt},
                ],
            }
            # qwen3 enables thinking by default; disable it for structured
            # agent calls that just need a JSON answer.
            if "qwen3" in self.config.model.lower():
                request_payload["messages"][-1]["content"] += "\n/no_think"
            if response_format is not None:
                request_payload["response_format"] = response_format
            if thinking is not None:
                self._apply_reasoning(request_payload, thinking)
            async with self.key_pool.acquire() as api_key:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
                response = await post_json_with_retry(
                    self._client,
                    f"{self.config.base_url.rstrip('/')}/chat/completions",
                    request_payload,
                    maximum_attempts=self.request_maximum_attempts,
                    retry_base_seconds=self.retry_base_seconds,
                    headers=headers,
                )
            response.raise_for_status()
            try:
                body = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise ValueError("model output was truncated")
                content = choice["message"].get("content")
                if not content or not content.strip():
                    raise ValueError("model returned empty structured output")
                return response_model.model_validate_json(content)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                rejected_errors.append(str(exc))
        raise ValueError(
            "model structured output remained invalid after "
            f"{self.maximum_attempts} attempts: {rejected_errors[-1]}"
        )

    async def close(self) -> None:
        await self._client.aclose()


def build_structured_chat_client(
    config: LLMModelCfg,
    key_pool: KeyPool,
    *,
    client: httpx.AsyncClient | None = None,
) -> StructuredChatClient:
    return StructuredChatClient(config, key_pool, client=client)
