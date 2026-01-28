import time
from typing import Any, Dict, Optional

from artemis.consts import TaskStatus, DeptServices
from artemis.consts.task_status import ALLOWED_TASK_STATUSES
from artemis.core.clients import BaseDeptServiceClient, NoopDeptServiceClient, CronjobClient, HTTPDeptServiceClient, \
    PhoenixAClient
from artemis.core.config_manager import cfg_mgr
from artemis.core.task_registry import registry
from artemis.log import get_logger
from artemis.models import TaskRunReq


class TaskContext:
    """Unified execution context carrying params, status, counters, and logger.

    Note: This context may talk to multiple dependent services (cronjob callback,
    phoenixA, etc.). We keep small factory helpers here so call sites stay clean.
    """

    def __init__(self, task_run_req: TaskRunReq):
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

        # dependent services: best-effort generic HTTP clients
        try:
            self.dept_http: Dict[str, BaseDeptServiceClient] = {
                DeptServices.CRONJOB: self.build_dept_http_client(DeptServices.CRONJOB),
                DeptServices.PHOENIXA: self.build_dept_http_client(DeptServices.PHOENIXA),
            }
        except Exception as e:
            self.dept_http = {
                DeptServices.CRONJOB: NoopDeptServiceClient(),
                DeptServices.PHOENIXA: NoopDeptServiceClient(),
            }
            if self.logger:
                self.logger.warning({'event': 'dept_http_client_init_failed', 'error': str(e), 'task_code': self.task_code, 'run_id': self.run_id})

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

    def _resolve_service_endpoint(self, service_name: str) -> tuple[Optional[str], Optional[int]]:
        """Resolve dependent service endpoint (host, port) from configuration.

        Resolution order:
          1) dept_services.<service_name>
          2) dept_services.extras[service_name]

        Returns (None, None) if not configured.
        """
        ds = cfg_mgr.dept_services_config()
        if not ds:
            return None, None

        endpoint = getattr(ds, service_name, None)
        if endpoint and getattr(endpoint, 'host', None) is not None and getattr(endpoint, 'port', None) is not None:
            return endpoint.host, endpoint.port

        return None, None

    def build_dept_http_client(self, service_name: str) -> BaseDeptServiceClient:
        """Build a generic OTEL-aware HTTP client for a dependent service.

        This is the common path for phoenixA and future services.
        We specialize CronjobClient to use the new subclass.
        """
        host, port = self._resolve_service_endpoint(service_name)
        if host is None or port is None:
            return NoopDeptServiceClient()

        timeout = None
        try:
            timeout = float(cfg_mgr.http_client_config.timeout_seconds) if cfg_mgr.http_client_config else None
        except Exception:
            timeout = None

        if service_name == DeptServices.CRONJOB:
            return CronjobClient(host=host, port=port, logger=self.logger, timeout_seconds=timeout)

        if service_name == DeptServices.PHOENIXA:
            return PhoenixAClient(host=host, port=port, logger=self.logger, timeout_seconds=timeout)

        return HTTPDeptServiceClient(host=host, port=port, logger=self.logger, timeout_seconds=timeout)
