import time
from typing import Optional, Dict, Any

from artemis.core.clients.dept_clients import HTTPDeptServiceClient


class CronjobClient(HTTPDeptServiceClient):
    """Reusable callback client for CronJob service.

    - Inherits HTTPDeptServiceClient for OTEL traceparent injection + connection pooling.
    - Specialized for CronJob API:
        POST /api/v1/runs/{id}/progress
        POST /api/v1/runs/{id}/callback
    """

    MAX_FINALIZE_ATTEMPTS = 3

    def __init__(
        self,
        host: str,
        port: int,
        logger: Any = None,
        timeout_seconds: float = 2.0,
    ):
        super().__init__(host=host, port=port, logger=logger, timeout_seconds=timeout_seconds)
        self._finalized_by_run: Dict[int, bool] = {}

    def _get_run_id(self, ctx_or_id: Any) -> int:
        if hasattr(ctx_or_id, 'run_id'):
            return int(ctx_or_id.run_id)
        return int(ctx_or_id)

    def _post_wrapper(self, path: str, payload: Dict[str, Any], run_id: int) -> bool:
        try:
            resp = self.post(path, payload)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({
                    'event': 'callback_http_failure',
                    'run_id': run_id,
                    'path': path,
                    'status': resp.status_code,
                    'body_snippet': resp.text[:120]
                })
            return ok
        except Exception as e:
            if self.logger:
                self.logger.warning({
                    'event': 'callback_http_exception',
                    'run_id': run_id,
                    'path': path,
                    'error': str(e)
                })
            return False

    def progress(self, ctx: Any, current: int, total: int, message: Optional[str] = None) -> bool:
        run_id = self._get_run_id(ctx)
        path = f"/api/v1/runs/{run_id}/progress"
        payload = {'current': current, 'total': total, 'message': message or ''}
        ok = self._post_wrapper(path, payload, run_id)
        if ok and self.logger:
            self.logger.info({'event': 'callback_progress_sent', 'run_id': run_id, 'current': current, 'total': total})
        return ok

    def finalize_success(self, ctx: Any, code: int = 200, body: Optional[str] = None) -> bool:
        run_id = self._get_run_id(ctx)
        payload = {'success': True, 'code': code, 'message': body or 'success'}
        return self._finalize_with_retry(run_id, payload)

    def finalize_failed(self, ctx: Any, error_message: str) -> bool:
        run_id = self._get_run_id(ctx)
        payload = {'success': False, 'message': error_message or 'failed'}
        return self._finalize_with_retry(run_id, payload)

    def _finalize_with_retry(self, run_id: int, payload: Dict[str, Any]) -> bool:
        path = f"/api/v1/runs/{run_id}/callback"
        attempt = 0
        wait = 0.5
        while attempt < self.MAX_FINALIZE_ATTEMPTS:
            attempt += 1
            if self._post_wrapper(path, payload, run_id):
                self._finalized_by_run[run_id] = True
                if self.logger:
                    self.logger.info({'event': 'callback_finalize_sent', 'run_id': run_id, 'result': payload.get('success')})
                return True
            if self.logger:
                self.logger.warning({'event': 'callback_finalize_retry', 'run_id': run_id, 'attempt': attempt})
            time.sleep(wait)
            wait *= 2
        if self.logger:
            self.logger.error({'event': 'callback_finalize_give_up', 'run_id': run_id})
        return False

    def finalized(self, ctx: Any = None) -> bool:
        if ctx is None:
            return False
        run_id = self._get_run_id(ctx)
        return bool(self._finalized_by_run.get(run_id))



