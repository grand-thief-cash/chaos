import time
from typing import Any, Dict, Optional

from .task_status import TaskStatus, ALLOWED_TASK_STATUSES


class TaskContext:
    """Unified execution context carrying params, status, counters, and logger.
    """

    def __init__(self, task_code: str, incoming_params: Dict[str, Any]):
        self.task_code = task_code
        self.incoming_params = incoming_params or {}
        self.params: Dict[str, Any] = {}
        self.start_ts = time.time()
        self.end_ts: Optional[float] = None
        self.status: str = TaskStatus.PENDING.value
        self.error: Optional[str] = None
        meta = (self.incoming_params.get('meta') or {})
        self.run_id: Optional[int] = meta.get('run_id')
        self.task_id: Optional[int] = meta.get('task_id')
        self.exec_type: Optional[str] = meta.get('exec_type')
        self.callback_endpoints: Dict[str, Any] = meta.get('callback_endpoints') or {}
        self.children_total: int = 0
        self.children_completed: int = 0
        self.stats: Dict[str, Any] = {}
        self.logger = None  # will be injected
        self.callback = None  # will hold callback client (Noop or HTTP)

    def set_logger(self, logger):
        self.logger = logger

    def set_status(self, status: str):
        # validate against known statuses
        if status not in ALLOWED_TASK_STATUSES:
            raise ValueError(f"invalid_task_status:{status}")
        self.status = status

    def mark_child_total(self, total: int):
        self.children_total = total

    def inc_child_completed(self):
        self.children_completed += 1

    def set_error(self, err: str):
        self.error = err

    def stat(self, key: str, value: Any):
        """Record/overwrite a stat value."""
        self.stats[key] = value

    def inc_stat(self, key: str, delta: int = 1):
        """Increment a numeric stat counter."""
        current = self.stats.get(key, 0)
        try:
            self.stats[key] = current + delta
        except Exception:
            # fall back to overwrite if non-numeric
            self.stats[key] = delta

    def close(self):
        self.end_ts = time.time()

    def duration_ms(self) -> int:
        end = self.end_ts or time.time()
        return int((end - self.start_ts) * 1000)

    # convenience predicates
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING.value

    def is_finished(self) -> bool:
        return self.status in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value, TaskStatus.CANCELED.value, TaskStatus.SKIPPED.value)
