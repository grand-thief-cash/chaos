from __future__ import annotations

import base64
from typing import Protocol

import httpx


class PDFLLMClient(Protocol):
    model_id: str

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
