import time
from typing import Any, Dict


class TaskContext:
    """Holds per-task invocation data (business params, stats, timing, logger).
    OpenTelemetry trace/span IDs are NOT stored here; they are obtained directly
    from the active context (trace.get_current_span()). This keeps the context
    focused on business payload only.
    """

    def __init__(self, task_code: str, incoming_params: Dict[str, Any]):
        self.task_code = task_code
        self.incoming_params = incoming_params or {}
        self.params: Dict[str, Any] = {}
        self.start_ts = time.time()
        self.stats: Dict[str, Any] = {}
        self.logger = None  # will be injected
        self.callback = None  # will hold callback client (Noop or HTTP)

    def set_logger(self, logger):
        self.logger = logger

    def duration_ms(self) -> int:
        return int((time.time() - self.start_ts) * 1000)
