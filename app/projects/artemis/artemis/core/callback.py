import time
from typing import Optional, Dict, Any

import httpx
from opentelemetry import trace  # type: ignore


class BaseCallbackClient:
    """Interface for task run progress & final result callback to CronJob service."""

    def progress(self, current: int, total: int, message: Optional[str] = None) -> bool:  # noqa: D401
        return False

    def finalize_success(self, code: int = 200, body: Optional[str] = None) -> bool:
        return False

    def finalize_failed(self, error_message: str) -> bool:
        return False

    def finalized(self) -> bool:  # noqa: D401
        return True


class NoopCallbackClient(BaseCallbackClient):
    pass


class HTTPCallbackClient(BaseCallbackClient):
    TIMEOUT_SECONDS = 2.0
    MAX_FINALIZE_ATTEMPTS = 3

    def __init__(
        self,
        run_id: int,
        callback_ip: str,
        callback_port: int,
        progress_path: str,
        callback_path: str,
        logger: Any = None,
    ):
        # forced config override > endpoint overrides > params
        self.host = callback_ip
        self.port = callback_port

        self.run_id = run_id
        self.progress_url = f"http://{self.host}:{self.port}{progress_path}"
        self.callback_url = f"http://{self.host}:{self.port}{callback_path}"
        self.logger = logger
        self._finalized = False

    def _get_traceparent(self) -> Optional[str]:
        if not trace:
            return None
        try:
            span = trace.get_current_span()
            sc = span.get_span_context() if span else None
            if sc and sc.is_valid:
                return f"00-{sc.trace_id:032x}-{sc.span_id:016x}-01"
        except Exception:
            return None
        return None

    def _headers(self) -> Dict[str, str]:
        h = {'Content-Type': 'application/json'}
        tp = self._get_traceparent()
        if tp:
            h['traceparent'] = tp
        return h

    def _post(self, url: str, payload: Dict[str, Any]) -> bool:
        try:
            resp = httpx.post(url, json=payload, headers=self._headers(), timeout=self.TIMEOUT_SECONDS)
            ok = 200 <= resp.status_code < 300
            if not ok and self.logger:
                self.logger.warning({'event':'callback_http_failure','run_id':self.run_id,'url':url,'status':resp.status_code,'body_snippet':resp.text[:120]})
            return ok
        except Exception as e:
            if self.logger:
                self.logger.warning({'event':'callback_http_exception','run_id':self.run_id,'url':url,'error':str(e)})
            return False

    def progress(self, current: int, total: int, message: Optional[str] = None) -> bool:
        if self._finalized:
            return False
        url = self.progress_url
        payload = {'current': current, 'total': total, 'message': message or ''}
        ok = self._post(url, payload)
        if ok and self.logger:
            self.logger.info({'event':'callback_progress_sent','run_id':self.run_id,'current':current,'total':total})
        return ok

    def finalize_success(self, code: int = 200, body: Optional[str] = None) -> bool:
        if self._finalized:
            return False
        payload = {'result':'success','code':code,'body':body or ''}
        ok = self._finalize_with_retry(payload)
        return ok

    def finalize_failed(self, error_message: str) -> bool:
        if self._finalized:
            return False
        payload = {'result':'failed','error_message':error_message or 'callback_failed'}
        ok = self._finalize_with_retry(payload)
        return ok

    def _finalize_with_retry(self, payload: Dict[str, Any]) -> bool:
        url = self.callback_url
        attempt=0
        wait=0.5
        while attempt < self.MAX_FINALIZE_ATTEMPTS:
            attempt+=1
            if self._post(url,payload):
                self._finalized=True
                if self.logger:
                    self.logger.info({'event':'callback_finalize_sent','run_id':self.run_id,'result':payload.get('result')})
                return True
            if self.logger:
                self.logger.warning({'event':'callback_finalize_retry','run_id':self.run_id,'attempt':attempt})
            time.sleep(wait)
            wait*=2
        if self.logger:
            self.logger.error({'event':'callback_finalize_give_up','run_id':self.run_id})
        return False

    def finalized(self) -> bool:
        return self._finalized


# def _safe_parse_port(p: str) -> int:
#     try:
#         i=int(p)
#         if 0<i<65536:
#             return i
#     except Exception:
#         pass
#     return 80







