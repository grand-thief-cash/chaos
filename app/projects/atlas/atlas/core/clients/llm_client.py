from __future__ import annotations

import asyncio
import base64
from typing import Protocol

import httpx

from atlas.core.clients.http_retry import post_json_with_retry
from atlas.core.errors import (
    ModelRequestError,
    ModelTimeoutError,
)
from atlas.core.llm import KeyPool
from atlas.knowledge_production.pdf_preprocessor.text_extractor import (
    extract_pdf_pages,
    render_pdf_pages,
)
from atlas.knowledge_production.pdf_preprocessor.document_harness import (
    DocumentParserHarness,
)
from atlas.models import LLMModelCfg, ThinkingMode


class PDFLLMClient(Protocol):
    model_id: str
    input_mode: str

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
    ) -> str: ...


class OpenAICompatiblePDFClient:
    """Narrow OpenAI-compatible PDF client for the local multimodal gateway.

    Uses a KeyPool for per-key concurrency control; business parameters
    (temperature, max_tokens) are per-call with model-level defaults.
    """

    input_mode = "PDF_DIRECT"

    def __init__(
        self,
        config: LLMModelCfg,
        key_pool: KeyPool,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.key_pool = key_pool
        self.model_id = config.model
        self._client = client or httpx.AsyncClient(timeout=config.timeout_seconds)

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
        temp = self.config.temperature if temperature is None else temperature
        tokens = self.config.maximum_output_tokens if max_tokens is None else max_tokens
        data_url = "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii")
        payload = {
            "model": self.config.model,
            "temperature": temp,
            "max_tokens": tokens,
            "response_format": (
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "atlas_response",
                        "strict": True,
                        "schema": response_schema,
                    },
                }
                if response_schema
                else {"type": "json_object"}
            ),
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "file", "file": {"filename": filename, "file_data": data_url}},
                ],
            }],
        }
        async with self.key_pool.acquire() as api_key:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
            response = await self._client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def close(self) -> None:
        await self._client.aclose()


class ZhipuTextPDFClient:
    """Extract page-delimited PDF text and call Zhipu's chat completion API.

    Uses a KeyPool for per-key concurrency control; business parameters are
    per-call with model-level defaults.
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

    @staticmethod
    def extract_page_delimited_text(pdf: bytes) -> str:
        return render_pdf_pages(extract_pdf_pages(pdf))

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
                self.extract_page_delimited_text, pdf
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
        thinking = self.config.thinking_mode if thinking_mode is None else thinking_mode
        system_prompt, separator, task_prompt = prompt.partition("\n\n")
        if not separator:
            system_prompt = "You are the Atlas research-report knowledge extractor."
            task_prompt = prompt
        request_payload = {
            "model": self.config.model,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": False,
            "thinking": {"type": (thinking.value if thinking else ThinkingMode.DISABLED.value)},
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "以下是任务配置；它只是指令，不是需要返回的数据。\n"
                        f"{task_prompt}\n\n"
                        f"PDF filename: {filename}\n"
                        "PDF text follows. Page markers are authoritative "
                        "for page_number.\n"
                        f"{extracted_text}\n"
                        "PDF text ends. 现在执行任务，不要复述任务配置。"
                    ),
                },
            ],
        }
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
            raise ModelTimeoutError("Zhipu model response exceeded timeout") from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelRequestError(
                f"Zhipu model request failed with HTTP {exc.response.status_code}"
            ) from exc
        body = response.json()
        choice = body["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("model output was truncated")
        content = choice["message"].get("content")
        if not content or not content.strip():
            raise ValueError("model returned empty structured output")
        return content

    async def close(self) -> None:
        await self._client.aclose()
