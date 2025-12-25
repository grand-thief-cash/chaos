import time
from typing import Optional, Dict, Any

import httpx

try:
    from opentelemetry import trace  # type: ignore
except Exception:  # pragma: no cover
    trace = None  # type: ignore


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
        caller_ip: str,
        caller_port: str,
        override_host: Optional[str],
        override_port: Optional[int],
        progress_path: str,
        callback_path: str,
        logger: Any = None,
    ):
        host = override_host or caller_ip
        port = override_port or _safe_parse_port(caller_port)
        base = f"http://{host}:{port}"
        self.run_id = run_id
        self.progress_url = base + progress_path
        self.callback_url = base + callback_path
        self.logger = logger
        self._finalized = False
        self._traceparent = self._build_traceparent()

    def _build_traceparent(self) -> Optional[str]:
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
        if self._traceparent:
            h['traceparent'] = self._traceparent
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


def _safe_parse_port(p: str) -> int:
    try:
        i=int(p)
        if 0<i<65536:
            return i
    except Exception:
        pass
    return 80


def build_callback_client(params: Dict[str, Any], logger: Any = None) -> BaseCallbackClient:
    meta = params.get('_meta') if isinstance(params, dict) else None
    if not isinstance(meta, dict):
        return NoopCallbackClient()
    run_id = meta.get('run_id')
    if not run_id:
        return NoopCallbackClient()
    caller_ip = (headers or {}).get('X-Caller-IP') or (headers or {}).get('x-caller-ip') or '127.0.0.1'
    caller_port = (headers or {}).get('X-Caller-Port') or (headers or {}).get('x-caller-port') or '80'
    from artemis.core.config import callback_config
    cb_cfg = callback_config()
    override_host = cb_cfg.get('override_host') or None
    ovp = cb_cfg.get('override_port')
    override_port = ovp if isinstance(ovp,int) and ovp>0 else None
    endpoints = (meta.get('callback_endpoints') or {})
    progress_path = endpoints.get('progress') or f"/runs/{run_id}/progress"
    callback_path = endpoints.get('callback') or f"/runs/{run_id}/callback"
    return HTTPCallbackClient(run_id, caller_ip, caller_port, override_host, override_port, progress_path, callback_path, logger)
