from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from typing import Protocol

import httpx

from atlas.core.clients.http_retry import post_json_with_retry
from atlas.core.errors import (
    ModelPDFUnreadableError,
    ModelRequestError,
    ModelTimeoutError,
    PDFTextExtractionError,
)


class PDFLLMClient(Protocol):
    model_id: str
    input_mode: str

    async def complete_pdf(self, *, prompt: str, pdf: bytes, filename: str) -> str: ...


class OpenAICompatiblePDFClient:
    """Narrow OpenAI-compatible PDF client for the local multimodal gateway."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        api_key: str = "",
        timeout_seconds: float = 900,
        temperature: float = 0,
        maximum_output_tokens: int = 16384,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.input_mode = "PDF_DIRECT"
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.temperature = temperature
        self.maximum_output_tokens = maximum_output_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            headers=headers,
        )

    async def complete_pdf(self, *, prompt: str, pdf: bytes, filename: str) -> str:
        data_url = "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii")
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model_id,
                "temperature": self.temperature,
                "max_tokens": self.maximum_output_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "file", "file": {"filename": filename, "file_data": data_url}},
                    ],
                }],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def close(self) -> None:
        await self._client.aclose()


class ZhipuTextPDFClient:
    """Extract page-delimited PDF text and call Zhipu's chat completion API."""

    input_mode = "TEXT_EXTRACTED"

    def __init__(
        self,
        base_url: str,
        model_id: str,
        *,
        api_key: str,
        timeout_seconds: float = 900,
        temperature: float = 0.1,
        maximum_output_tokens: int = 65536,
        client: httpx.AsyncClient | None = None,
        request_maximum_attempts: int = 4,
        retry_base_seconds: float = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.temperature = temperature
        self.maximum_output_tokens = maximum_output_tokens
        self.request_maximum_attempts = request_maximum_attempts
        self.retry_base_seconds = retry_base_seconds
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @staticmethod
    def extract_page_delimited_text(pdf: bytes) -> str:
        try:
            import pdfplumber

            pages: list[str] = []
            has_text = False
            with pdfplumber.open(BytesIO(pdf)) as document:
                for page_number, page in enumerate(document.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    has_text = has_text or bool(text)
                    pages.append(
                        f'<atlas_pdf_page number="{page_number}">\n'
                        f"{text}\n"
                        "</atlas_pdf_page>"
                    )
        except Exception as exc:
            raise PDFTextExtractionError(str(exc)) from exc
        if not has_text:
            raise ModelPDFUnreadableError(
                "pdfplumber extracted no text; scanned/image-only PDFs require a future fallback"
            )
        return "\n".join(pages)

    async def complete_pdf(self, *, prompt: str, pdf: bytes, filename: str) -> str:
        extracted_text = await asyncio.to_thread(
            self.extract_page_delimited_text, pdf
        )
        system_prompt, separator, task_prompt = prompt.partition("\n\n")
        if not separator:
            system_prompt = "You are the Atlas research-report knowledge extractor."
            task_prompt = prompt
        try:
            response = await post_json_with_retry(
                self._client,
                f"{self.base_url}/chat/completions",
                {
                    "model": self.model_id,
                    "temperature": self.temperature,
                    "max_tokens": self.maximum_output_tokens,
                    "stream": False,
                    "thinking": {"type": "disabled"},
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
                                "PDF text ends. 现在执行抽取，不要复述任务配置。"
                                "返回的 JSON 顶层必须且只能包含：schema_version、"
                                "semantic_version、document_id、document_assessment、"
                                "entity_mentions、relation_claims、quantified_claims、"
                                "analyst_views、unknown_semantic_terms。"
                            ),
                        },
                    ],
                },
                maximum_attempts=self.request_maximum_attempts,
                retry_base_seconds=self.retry_base_seconds,
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
