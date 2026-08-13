from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CronjobCallbackClient:
    """Best-effort async callback client for the cronjob service.

    Atlas is the source of truth for sample-run progress; it pushes progress
    and final results to cronjob so cronjob's UI/API can mirror them. Failures
    are logged and swallowed -- progress reporting must never break the run.

    Mirrors Artemis's CronjobClient contract:
        POST /api/v1/runs/{id}/progress   {"current", "total", "message"}
        POST /api/v1/runs/{id}/callback   {"result", "code", "body", "error_message"}
    """

    MAX_FINALIZE_ATTEMPTS = 3

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._finalized: set[int] = set()

    async def report_progress(
        self,
        run_id: int | None,
        current: int,
        total: int,
        message: str | None = None,
    ) -> bool:
        if run_id is None:
            return False
        path = f"/api/v1/runs/{run_id}/progress"
        payload: dict[str, Any] = {
            "current": current,
            "total": total,
            "message": message or "",
        }
        return await self._post(path, payload, run_id, "progress")

    async def finalize_success(
        self,
        run_id: int | None,
        code: int = 200,
        body: str | None = None,
    ) -> bool:
        if run_id is None:
            return False
        payload = {"result": "success", "code": code, "body": body or "success"}
        return await self._finalize(run_id, payload)

    async def finalize_failed(
        self,
        run_id: int | None,
        error_message: str,
    ) -> bool:
        if run_id is None:
            return False
        payload = {"result": "failed", "error_message": error_message or "failed"}
        return await self._finalize(run_id, payload)

    @property
    def finalized_run_ids(self) -> set[int]:
        return set(self._finalized)

    async def _finalize(self, run_id: int, payload: dict[str, Any]) -> bool:
        path = f"/api/v1/runs/{run_id}/callback"
        wait = 0.5
        for attempt in range(1, self.MAX_FINALIZE_ATTEMPTS + 1):
            if await self._post(path, payload, run_id, "finalize"):
                self._finalized.add(run_id)
                return True
            if attempt < self.MAX_FINALIZE_ATTEMPTS:
                await asyncio.sleep(wait)
                wait *= 2
        logger.error("cronjob finalize gave up for run_id=%s", run_id)
        return False

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        run_id: int,
        event: str,
    ) -> bool:
        try:
            resp = await self._client.post(f"{self.base_url}{path}", json=payload)
        except Exception as exc:  # best-effort: never raise to caller
            logger.warning("cronjob %s exception run_id=%s: %s", event, run_id, exc)
            return False
        ok = 200 <= resp.status_code < 300
        if not ok:
            logger.warning(
                "cronjob %s http failure run_id=%s status=%s body=%s",
                event, run_id, resp.status_code, resp.text[:120],
            )
        return ok

    async def close(self) -> None:
        await self._client.aclose()
