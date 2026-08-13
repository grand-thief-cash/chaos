from __future__ import annotations

import asyncio
from typing import Any

import httpx


RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


async def post_json_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    *,
    maximum_attempts: int = 4,
    retry_base_seconds: float = 1,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Retry transient model API failures without logging request payloads."""

    if maximum_attempts < 1:
        raise ValueError("maximum_attempts must be positive")
    for attempt in range(1, maximum_attempts + 1):
        delay = retry_base_seconds * (2 ** (attempt - 1))
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.ReadTimeout:
            raise
        except (
            httpx.ConnectTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ):
            if attempt == maximum_attempts:
                raise
        else:
            if (
                response.status_code not in RETRYABLE_STATUS_CODES
                or attempt == maximum_attempts
            ):
                return response
            retry_after = response.headers.get("Retry-After", "")
            try:
                delay = min(60.0, max(0.0, float(retry_after)))
            except ValueError:
                pass
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")
