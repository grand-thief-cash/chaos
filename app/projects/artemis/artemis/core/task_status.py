from enum import Enum

class TaskStatus(str, Enum):
    """Canonical task lifecycle statuses for Artemis tasks.
    Extend cautiously; keep stable string values for persistence & logs.
    """
    PENDING = "PENDING"          # context created, not started
    RUNNING = "RUNNING"          # execution in progress
    SUCCESS = "SUCCESS"          # completed successfully
    FAILED = "FAILED"            # failed with error
    CANCELED = "CANCELED"        # (reserved) externally canceled before completion
    SKIPPED = "SKIPPED"          # (reserved) intentionally skipped

ALLOWED_TASK_STATUSES = {s.value for s in TaskStatus}

__all__ = ["TaskStatus", "ALLOWED_TASK_STATUSES"]

