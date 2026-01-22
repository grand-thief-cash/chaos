import time
from typing import Any, Dict, Optional

from artemis.consts import TaskStatus
from artemis.consts.task_status import ALLOWED_TASK_STATUSES
from artemis.core.callback import HTTPCallbackClient, NoopCallbackClient, BaseCallbackClient
from artemis.core.config_manager import cfg_mgr
from artemis.core.task_registry import registry
from artemis.log import get_logger
from artemis.models import TaskRunReq


class TaskContext:
    """Unified execution context carrying params, status, counters, and logger.
    """

    def __init__(self, task_run_req: TaskRunReq):
        # self.task_code = task_run_req.task_meta.task_code
        self.task_meta = task_run_req.task_meta
        self.incoming_params = task_run_req.task_body
        self.params: Dict[str, Any] = {}
        self.start_ts = time.time()
        self.end_ts: Optional[float] = None
        self.status: str = TaskStatus.PENDING.value
        self.error: Optional[str] = None
        self.children_total: int = 0
        self.children_completed: int = 0
        self.stats: Dict[str, Any] = {}
        self.logger = get_logger(self.task_meta.task_code)  # will be injected
        try:
            self.callback = self.build_callback_client()
        except Exception as e:
            self.logger.warning({'event':'callback_client_init_failed','error':str(e),'task_code':self.task_code,'run_id': self.run_id})
        self.exec_cls = registry.get_task(self.task_code)


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

    @property
    def run_id(self) -> int:
        return self.task_meta.run_id

    @property
    def task_code(self) -> str:
        return self.task_meta.task_code
    @property
    def async_mode(self) -> bool:
        return self.task_meta.async_mode
    @property
    def exec_type(self):
        return self.task_meta.exec_type
    @property
    def task_id(self) -> Optional[int]:
        return self.task_meta.task_id


    def build_callback_client(self) -> BaseCallbackClient:
        progress_path = self.task_meta.callback_endpoints.progress # Correct field name based on definition
        callback_path = self.task_meta.callback_endpoints.callback # Correct field name based on definition
        cb_cfg = cfg_mgr.callback_config()
        if cb_cfg:
            host = cb_cfg.host
            ip = cb_cfg.port
            if host is not None and ip is not None:
                return HTTPCallbackClient(self.run_id, host, ip, callback_path, progress_path, self.logger)

        host = self.task_meta.callback_endpoints.callback_ip
        ip = self.task_meta.callback_endpoints.callback_port
        if host is not None and ip is not None:
            return HTTPCallbackClient(self.run_id, host, ip, callback_path, progress_path, self.logger)

        return NoopCallbackClient()
