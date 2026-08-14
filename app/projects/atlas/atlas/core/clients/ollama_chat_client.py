from __future__ import annotations

import asyncio

import httpx

from atlas.core.clients.http_retry import post_json_with_retry
from atlas.core.clients.llm_client import ZhipuTextPDFClient
from atlas.core.clients.openrouter_client import _strip_markdown_fence
from atlas.core.errors import ModelRequestError, ModelTimeoutError
from atlas.core.llm import KeyPool
from atlas.models import LLMModelCfg, ThinkingMode
from atlas.knowledge_production.pdf_preprocessor.document_harness import (
    DocumentParserHarness,
)


class OllamaChatClient:
    """Ollama native /api/chat client for text-extracted PDF extraction.

    The OpenAI-compatible /v1/chat/completions endpoint ignores both
    ``/no_think`` and ``think:false``, so qwen3 keeps emitting reasoning that
    pollutes the JSON. The native /api/chat endpoint honours ``think:false``
    and ``format:"json"`` reliably, so we use it for ollama extraction.
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

    @property
    def _chat_url(self) -> str:
        # config.base_url is the OpenAI-compatible root (e.g. .../v1); the
        # native chat endpoint is at the host root /api/chat.
        base = self.config.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return base + "/api/chat"

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
        temp = self.config.temperature if temperature is None else temperature
        tokens = self.config.maximum_output_tokens if max_tokens is None else max_tokens
        system_prompt, separator, task_prompt = prompt.partition("\n\n")
        if not separator:
            system_prompt = "You are the Atlas research-report knowledge extractor."
            task_prompt = prompt
        user_content = (
            f"{task_prompt}\n\n"
            f"PDF filename: {filename}\n"
            "PDF text follows. Page markers are authoritative for page_number.\n"
            f"{extracted_text}\n"
            "PDF text ends. 现在执行任务，不要复述任务配置。"
        )
        payload: dict = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "think": False,  # native endpoint: reliably disables qwen3 thinking
            "options": {
                "num_ctx": self.config.context_window_tokens,
                "num_predict": tokens,
                "temperature": temp,
            },
        }
        if self.config.capabilities.response_format_api:
            payload["format"] = response_schema or "json"
        try:
            async with self.key_pool.acquire() as api_key:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
                response = await post_json_with_retry(
                    self._client,
                    self._chat_url,
                    payload,
                    maximum_attempts=self.request_maximum_attempts,
                    retry_base_seconds=self.retry_base_seconds,
                    headers=headers,
                )
        except httpx.ReadTimeout as exc:
            raise ModelTimeoutError("Ollama model response exceeded timeout") from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelRequestError(
                f"Ollama model request failed with HTTP {exc.response.status_code}"
            ) from exc
        body = response.json()
        content = body.get("message", {}).get("content")
        if not content or not content.strip():
            raise ValueError("model returned empty structured output")
        return _strip_markdown_fence(content)

    async def close(self) -> None:
        await self._client.aclose()
