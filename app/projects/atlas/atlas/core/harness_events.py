from __future__ import annotations

from collections import OrderedDict, deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Iterator


@dataclass(frozen=True, slots=True)
class HarnessContext:
    run_id: str
    document_id: str | None = None
    report_type: str | None = None


_context: ContextVar[HarnessContext | None] = ContextVar(
    "atlas_harness_context", default=None
)


@contextmanager
def harness_context(
    run_id: str,
    *,
    document_id: str | None = None,
    report_type: str | None = None,
) -> Iterator[None]:
    """Attach run/document identity to nested parser and model operations."""
    token = _context.set(HarnessContext(run_id, document_id, report_type))
    try:
        yield
    finally:
        _context.reset(token)


def current_harness_context() -> HarnessContext | None:
    return _context.get()


@dataclass(frozen=True, slots=True)
class HarnessEvent:
    sequence: int
    timestamp: str
    run_id: str
    stage: str
    event_type: str
    level: str
    message: str
    document_id: str | None = None
    report_type: str | None = None
    provider: str | None = None
    parser: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class HarnessEventRegistry:
    """Bounded, process-local event journal for live Harness inspection.

    It is deliberately not a source of truth. PhoenixA owns durable run state;
    this registry only explains what an active/recent in-process run is doing.
    Prompts, extracted document text, model output and credentials must never be
    placed in an event.
    """

    def __init__(self, *, maximum_events_per_run: int = 400, maximum_runs: int = 20):
        self.maximum_events_per_run = max(20, maximum_events_per_run)
        self.maximum_runs = max(1, maximum_runs)
        self._events: OrderedDict[str, deque[HarnessEvent]] = OrderedDict()
        self._latest_sequence: dict[str, int] = {}
        self._lock = Lock()

    def start_run(self, run_id: str) -> None:
        with self._lock:
            if run_id not in self._events:
                self._events[run_id] = deque(maxlen=self.maximum_events_per_run)
            self._events.move_to_end(run_id)
            while len(self._events) > self.maximum_runs:
                removed, _ = self._events.popitem(last=False)
                self._latest_sequence.pop(removed, None)

    def emit(
        self,
        *,
        stage: str,
        event_type: str,
        message: str,
        level: str = "INFO",
        run_id: str | None = None,
        document_id: str | None = None,
        report_type: str | None = None,
        provider: str | None = None,
        parser: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> HarnessEvent | None:
        context = current_harness_context()
        resolved_run_id = run_id or (context.run_id if context else None)
        if not resolved_run_id:
            return None
        resolved_document_id = document_id or (
            context.document_id if context else None
        )
        resolved_report_type = report_type or (
            context.report_type if context else None
        )
        safe_details = _safe_details(details or {})
        with self._lock:
            if resolved_run_id not in self._events:
                self.start_run_unlocked(resolved_run_id)
            sequence = self._latest_sequence.get(resolved_run_id, 0) + 1
            self._latest_sequence[resolved_run_id] = sequence
            event = HarnessEvent(
                sequence=sequence,
                timestamp=datetime.now(UTC).isoformat(),
                run_id=resolved_run_id,
                stage=stage[:80],
                event_type=event_type[:80],
                level=level[:16],
                message=message[:500],
                document_id=resolved_document_id,
                report_type=resolved_report_type,
                provider=provider,
                parser=parser,
                details=safe_details,
            )
            self._events[resolved_run_id].append(event)
            self._events.move_to_end(resolved_run_id)
            return event

    def start_run_unlocked(self, run_id: str) -> None:
        self._events[run_id] = deque(maxlen=self.maximum_events_per_run)
        self._events.move_to_end(run_id)
        while len(self._events) > self.maximum_runs:
            removed, _ = self._events.popitem(last=False)
            self._latest_sequence.pop(removed, None)

    def list_events(
        self,
        run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 200,
    ) -> dict[str, Any]:
        with self._lock:
            events = list(self._events.get(run_id, ()))
            newest = self._latest_sequence.get(run_id, 0)
        filtered = [event for event in events if event.sequence > after_sequence]
        bounded_limit = min(500, max(1, limit))
        filtered = filtered[:bounded_limit]
        latest = filtered[-1].sequence if filtered else min(after_sequence, newest)
        oldest = events[0].sequence if events else 0
        return {
            "run_id": run_id,
            "events": [event.model_dump() for event in filtered],
            "latest_sequence": latest,
            "newest_available_sequence": newest,
            "oldest_available_sequence": oldest,
            "buffer_limit": self.maximum_events_per_run,
            "truncated": bool(events and after_sequence + 1 < oldest),
            "ephemeral": True,
        }


def _safe_details(details: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    forbidden = {"prompt", "content", "text", "api_key", "key", "secret", "password"}
    for raw_name, value in list(details.items())[:30]:
        name = str(raw_name)[:80]
        normalized_name = name.lower().replace("-", "_")
        if any(token in normalized_name for token in forbidden):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[name] = value[:500] if isinstance(value, str) else value
        elif isinstance(value, (list, tuple)):
            safe[name] = [str(item)[:120] for item in value[:20]]
        else:
            safe[name] = str(value)[:500]
    return safe
