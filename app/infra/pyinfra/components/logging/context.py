import contextvars
import time
import uuid
from typing import Optional

_TRACE_ID_CTX = contextvars.ContextVar("trace_id", default=str(uuid.uuid4()))
_START_TIME_CTX = contextvars.ContextVar("start_time", default=None)

def set_trace_id(trace_id: str) -> None:
    """Set the trace ID for current context.

    Args:
        trace_id: Unique identifier for the trace.

    Raises:
        ValueError: If trace_id is not a non-empty string.
    """
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise ValueError("trace_id must be a non-empty string")
    _TRACE_ID_CTX.set(trace_id)

def get_trace_id() -> str:
    """Get the trace ID for current context."""
    return _TRACE_ID_CTX.get()

def set_start_time() -> None:
    """Set the start time for current context."""
    _START_TIME_CTX.set(time.time())

def get_execution_time() -> Optional[float]:
    """Get the elapsed time since start time was set.

    Returns:
        Elapsed time in seconds with 2 decimal places,
        or None if start time was not set.
    """
    start = _START_TIME_CTX.get()
    if start is None:
        return None
    return round(time.time() - start, 2)