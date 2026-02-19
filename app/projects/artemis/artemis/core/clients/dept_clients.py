from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Dict

import httpx
from opentelemetry import trace  # type: ignore


class OTELHTTPClientMixin:
    """Inject `traceparent` header for distributed tracing.

    This must be used for *all* outbound calls:
      cronjob -> artemis -> phoenixA
    so each request stays in the same trace.
    """

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

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h: Dict[str, str] = {'Content-Type': 'application/json'}
        tp = self._get_traceparent()
        if tp:
            h['traceparent'] = tp
        if extra:
            h.update(extra)
        return h


@dataclass(frozen=True)
class _ClientKey:
    base_url: str
    timeout_seconds: float


class SharedHTTPXClientPool:
    """Process-wide pool for sharing httpx.Client instances.

    httpx.Client keeps connection pools; sharing improves performance and avoids
    re-creating TCP connections for every task.

    NOTE: This is in-memory and best-effort; it's fine for Artemis.
    """

    _clients: Dict[_ClientKey, httpx.Client] = {}

    @classmethod
    def get(cls, base_url: str, timeout_seconds: float) -> httpx.Client:
        key = _ClientKey(base_url=base_url.rstrip('/'), timeout_seconds=float(timeout_seconds))
        cli = cls._clients.get(key)
        if cli is None:
            cli = httpx.Client(base_url=key.base_url, timeout=key.timeout_seconds)
            cls._clients[key] = cli
        return cli


class BaseDeptServiceClient:
    """Base interface for dependent-service clients."""

    pass


class NoopDeptServiceClient(BaseDeptServiceClient):
    """A no-op dependent-service client."""

    pass


class HTTPDeptServiceClient(BaseDeptServiceClient, OTELHTTPClientMixin):
    """Generic OTEL-aware HTTP client for dependent services.

    It uses a shared httpx.Client so connections are reused across tasks.
    """

    def __init__(self, host: str, port: int, logger: Any = None, timeout_seconds: Optional[float] = None):
        self.host = host
        self.port = port
        self.logger = logger
        self.timeout_seconds = float(timeout_seconds or 5.0)
        self.base_url = f"http://{host}:{port}"
        self._client = SharedHTTPXClientPool.get(self.base_url, self.timeout_seconds)

    def _build_path(self, path: str) -> str:
        if not path:
            return '/'
        return path if path.startswith('/') else '/' + path

    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        p = self._build_path(path)
        return self._client.get(p, params=params, headers=self._headers(headers))

    def post(self, path: str, payload: Any, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        p = self._build_path(path)
        return self._client.post(p, json=payload, headers=self._headers(headers))
