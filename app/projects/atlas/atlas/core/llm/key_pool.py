from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from atlas.models import LLMAPIKeyCfg


@dataclass(slots=True)
class APIKeySlot:
    """One API key with its own per-key concurrency semaphore."""
    key: str
    max_concurrency: int
    _semaphore: asyncio.Semaphore = field(init=False)
    in_flight: int = 0

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        self.in_flight += 1

    def release(self) -> None:
        self.in_flight -= 1
        self._semaphore.release()


class KeyPool:
    """Round-robin, least-loaded pool of API keys, each with its own concurrency cap.

    A model provider may hand out multiple API keys; each key has a per-key
    ``max_concurrency`` so no single key gets hammered (free endpoints ban
    aggressive single-key callers). The optional ``total_concurrency`` is a
    global circuit breaker across all keys.
    """

    def __init__(
        self,
        keys: list[LLMAPIKeyCfg],
        *,
        total_concurrency: int | None = None,
    ) -> None:
        # Keep all configured keys, including empty ones: local no-auth providers
        # (e.g. Ollama) use an empty key and the clients skip the Authorization
        # header in that case. The pool still enforces per-key concurrency caps.
        self.slots: list[APIKeySlot] = [
            APIKeySlot(key=cfg.resolved_key, max_concurrency=cfg.max_concurrency)
            for cfg in keys
        ]
        if not self.slots:
            raise ValueError("key pool has no api keys configured")
        self._cursor = 0
        self._total_sem: asyncio.Semaphore | None = (
            asyncio.Semaphore(total_concurrency) if total_concurrency else None
        )

    @asynccontextmanager
    async def acquire(self):
        """Yield an API key, bounded by per-key and global concurrency caps."""
        if self._total_sem is not None:
            await self._total_sem.acquire()
        try:
            slot = self._pick_least_loaded()
            await slot.acquire()
            try:
                yield slot.key
            finally:
                slot.release()
        finally:
            if self._total_sem is not None:
                self._total_sem.release()

    def _pick_least_loaded(self) -> APIKeySlot:
        """Pick the slot with the lowest in-flight count; round-robin on ties."""
        # Find minimum in-flight.
        min_in_flight = min(slot.in_flight for slot in self.slots)
        # Among those at the minimum, round-robin starting at the cursor so the
        # choice rotates across equally-loaded slots instead of always picking
        # the first one.
        n = len(self.slots)
        for offset in range(n):
            index = (self._cursor + offset) % n
            slot = self.slots[index]
            if slot.in_flight == min_in_flight:
                self._cursor = (index + 1) % n
                return slot
        return self.slots[0]  # unreachable

    @property
    def max_total_concurrency(self) -> int:
        return sum(slot.max_concurrency for slot in self.slots)
