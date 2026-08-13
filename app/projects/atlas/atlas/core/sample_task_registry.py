from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SampleTaskHandle:
    run_id: str
    cronjob_run_id: int | None
    identity_key: str
    task: asyncio.Task = field(repr=False)


def sample_identity_key(
    sample_size: int,
    report_types: list[str],
    published_from: str | None,
    published_to: str | None,
    sample_seed: int = 0,
) -> str:
    """Logical identity of a sample request; identical keys are treated as duplicates."""
    types = ",".join(sorted(report_types))
    return (
        f"n={sample_size};types={types};from={published_from or ''};"
        f"to={published_to or ''};seed={sample_seed}"
    )


class SampleTaskRegistry:
    """In-memory registry of running sample tasks.

    Provides idempotency: a second submission with the same logical identity
    while one is already running is rejected (returns the existing run_id)
    rather than spawning a duplicate. Survives only within the process -- the
    durable record lives in phoenixA (sample_run status). A ``force`` flag at
    the caller may bypass this check.
    """

    def __init__(self) -> None:
        self._active: dict[str, SampleTaskHandle] = {}
        self._lock = asyncio.Lock()

    async def try_register(
        self,
        identity_key: str,
        run_id: str,
        cronjob_run_id: int | None,
        coro_factory: Callable[[], Awaitable[None]],
    ) -> tuple[bool, str | None]:
        """Register and start a background task. Returns (ok, existing_run_id).

        On conflict (same identity_key already active) the task is NOT started
        and (False, existing_run_id) is returned.
        """
        async with self._lock:
            existing = self._active.get(identity_key)
            if existing is not None and not existing.task.done():
                return False, existing.run_id
            task = asyncio.create_task(coro_factory(), name=f"sample-run-{run_id}")
            handle = SampleTaskHandle(
                run_id=run_id,
                cronjob_run_id=cronjob_run_id,
                identity_key=identity_key,
                task=task,
            )
            self._active[identity_key] = handle
            task.add_done_callback(lambda _: self._schedule_release(identity_key))
            logger.info("registered sample task run_id=%s key=%s", run_id, identity_key)
            return True, None

    def _schedule_release(self, identity_key: str) -> None:
        handle = self._active.get(identity_key)
        if handle is None:
            return
        if handle.task.done() and not handle.task.cancelled():
            exc = handle.task.exception()
            if exc:
                logger.warning("sample task run_id=%s failed: %s", handle.run_id, exc)
        # Remove synchronously; this callback fires after the task completes.
        self._active.pop(identity_key, None)

    def is_active(self, identity_key: str) -> bool:
        handle = self._active.get(identity_key)
        return handle is not None and not handle.task.done()

    def active_handles(self) -> list[SampleTaskHandle]:
        return [h for h in self._active.values() if not h.task.done()]

    async def cancel(self, identity_key: str) -> bool:
        handle = self._active.get(identity_key)
        if handle is None or handle.task.done():
            return False
        handle.task.cancel()
        return True
