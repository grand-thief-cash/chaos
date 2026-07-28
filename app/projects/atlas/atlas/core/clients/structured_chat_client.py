from __future__ import annotations

import os
import json
from typing import TypeVar

import httpx
from pydantic import BaseModel

from atlas.models import ModelEndpointCfg, StructuredOutputMode

T = TypeVar("T", bound=BaseModel)


class StructuredChatClient:
    """Provider-neutral OpenAI-compatible JSON/JSON-Schema chat adapter."""

    def __init__(
        self,
        config: ModelEndpointCfg,
        *,
        client: httpx.AsyncClient | None = None,
        maximum_attempts: int = 3,
    ) -> None:
        self.config = config
        self.maximum_attempts = maximum_attempts
        api_key = os.getenv(config.api_key_env, "") if config.api_key_env else config.api_key
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = client or httpx.AsyncClient(
            timeout=config.timeout_seconds,
            headers=headers,
        )

    async def complete_model(
        self,
        response_model: type[T],
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> T:
        schema = response_model.model_json_schema()
        response_format: dict
        if self.config.structured_output_mode == StructuredOutputMode.JSON_SCHEMA:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            }
        else:
            response_format = {"type": "json_object"}
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
            response = await self._client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                json={
                    "model": self.config.model,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.maximum_output_tokens,
                    "stream": False,
                    "response_format": response_format,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": attempt_prompt},
                    ],
                },
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


def build_structured_chat_client(config: ModelEndpointCfg) -> StructuredChatClient:
    return StructuredChatClient(config)
