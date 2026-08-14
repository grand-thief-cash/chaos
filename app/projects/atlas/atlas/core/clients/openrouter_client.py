from __future__ import annotations

import asyncio
from contextvars import ContextVar
import re

import httpx

from atlas.core.clients.http_retry import post_json_with_retry
from atlas.core.clients.llm_client import ZhipuTextPDFClient
from atlas.core.errors import (
    ModelRequestError,
    ModelTimeoutError,
)
from atlas.core.llm import KeyPool
from atlas.models import LLMModelCfg, ModelProvider, ThinkingMode
from atlas.knowledge_production.pdf_preprocessor.document_harness import (
    DocumentParserHarness,
)


_MARKDOWN_FENCE_RE = re.compile(
    r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL
)


def _strip_markdown_fence(text: str) -> str:
    """Strip a single ```json ... ``` fence when the model wraps its JSON.

    OpenRouter free models that reject response_format often still wrap output
    in markdown; the chat client contract is raw JSON, so unwrap transparently.
    """
    match = _MARKDOWN_FENCE_RE.match(text)
    return match.group(1).strip() if match else text


class OpenAICompatibleTextPDFClient:
    """OpenAI-compatible chat client that extracts PDF text before calling it.

    Provider extensions live in ``LLMModelCfg.extra_body``. This supports NIM
    chat-template options and future compatible providers without hard-wiring
    each vendor into the extraction workflow.
    """

    input_mode = "TEXT_EXTRACTED"

    def __init__(
        self,
        config: LLMModelCfg,
        key_pool: KeyPool,
        *,
        client: httpx.AsyncClient | None = None,
        request_maximum_attempts: int = 4,
        retry_base_seconds: float = 1,
        document_parser: DocumentParserHarness | None = None,
    ) -> None:
        self.config = config
        self.key_pool = key_pool
        self.model_id = config.model
        self.request_maximum_attempts = request_maximum_attempts
        self.retry_base_seconds = retry_base_seconds
        self._client = client or httpx.AsyncClient(timeout=config.timeout_seconds)
        self.document_parser = document_parser
        self.document_parser_signature = (
            document_parser.signature if document_parser else "legacy-pdfplumber"
        )
        # A client can serve concurrent tasks. ContextVar keeps the routed
        # model provenance attached to the request that received it.
        self._response_model: ContextVar[str | None] = ContextVar(
            f"atlas_response_model_{id(self)}", default=None
        )

    async def complete_pdf(
        self,
        *,
        prompt: str,
        pdf: bytes,
        filename: str,
        temperature: float | None = None,
        thinking_mode: ThinkingMode | None = None,
        max_tokens: int | None = None,
        response_schema: dict | None = None,
    ) -> str:
        if self.document_parser is not None:
            parsed = await self.document_parser.parse(pdf, filename=filename)
            extracted_text = parsed.text
        else:
            extracted_text = await asyncio.to_thread(
                ZhipuTextPDFClient.extract_page_delimited_text, pdf
            )
        return await self.complete_text(
            prompt=prompt,
            extracted_text=extracted_text,
            filename=filename,
            temperature=temperature,
            thinking_mode=thinking_mode,
            max_tokens=max_tokens,
            response_schema=response_schema,
        )

    async def complete_text(
        self,
        *,
        prompt: str,
        extracted_text: str,
        filename: str,
        temperature: float | None = None,
        thinking_mode: ThinkingMode | None = None,
        max_tokens: int | None = None,
        response_schema: dict | None = None,
    ) -> str:
        self._response_model.set(None)
        temp = self.config.temperature if temperature is None else temperature
        tokens = self.config.maximum_output_tokens if max_tokens is None else max_tokens
        thinking = self.config.thinking_mode if thinking_mode is None else thinking_mode
        system_prompt, separator, task_prompt = prompt.partition("\n\n")
        if not separator:
            system_prompt = "You are the Atlas research-report knowledge extractor."
            task_prompt = prompt
        user_content = (
            f"{task_prompt}\n\n"
            f"PDF filename: {filename}\n"
            "PDF text follows. Page markers are authoritative "
            "for page_number.\n"
            f"{extracted_text}\n"
            "PDF text ends. 现在执行任务，不要复述任务配置。"
        )
        # qwen3 enables thinking by default, which is slow and burns tokens on
        # reasoning for a pure extraction task. /no_think disables it.
        if "qwen3" in self.config.model.lower():
            user_content += "\n/no_think"
        request_payload: dict = {
            "model": self.config.model,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if self.config.capabilities.response_format_api:
            if (
                response_schema is not None
                and self.config.structured_output_mode.value == "json_schema"
            ):
                request_payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "atlas_response",
                        "strict": True,
                        "schema": response_schema,
                    },
                }
            else:
                request_payload["response_format"] = {"type": "json_object"}
        if thinking == ThinkingMode.ENABLED:
            if self.config.provider == ModelProvider.OPENROUTER:
                request_payload["reasoning"] = {"enabled": True}
        request_payload.update(self.config.extra_body)
        try:
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
        except httpx.ReadTimeout as exc:
            raise ModelTimeoutError("OpenRouter model response exceeded timeout") from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelRequestError(
                "OpenAI-compatible text model request failed with HTTP "
                f"{exc.response.status_code}"
            ) from exc
        body = response.json()
        routed_model = body.get("model")
        if isinstance(routed_model, str) and routed_model:
            self._response_model.set(routed_model)
        choice = body["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("model output was truncated")
        content = choice["message"].get("content")
        if not content or not content.strip():
            raise ValueError("model returned empty structured output")
        return _strip_markdown_fence(content)

    def consume_response_model(self) -> str | None:
        """Return and clear the actual model selected by a provider router."""
        model = self._response_model.get()
        self._response_model.set(None)
        return model

    async def close(self) -> None:
        await self._client.aclose()


class OpenRouterTextPDFClient(OpenAICompatibleTextPDFClient):
    """Backward-compatible name for the OpenRouter model adapter."""
