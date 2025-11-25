from typing import List, Any

import httpx

from artemis.core.context import TaskContext
from artemis.telemetry.tracing import new_span
from .base import BaseSink


class HttpSink(BaseSink):
    def __init__(self, endpoint: str | None):
        self.endpoint = endpoint

    def emit(self, batch: List[Any], ctx: TaskContext):
        if not self.endpoint:
            if ctx.logger:
                ctx.logger.warning({'event': 'http_sink_skip', 'reason': 'no_endpoint'})
            return
        payload = [b.dict() if hasattr(b, 'dict') else b for b in batch]
        span = new_span(ctx.trace_id, ctx.span_id, 'emit.http_sink')
        headers = {'traceparent': f"00-{ctx.trace_id}-{span.span_id}-01"}
        try:
            r = httpx.post(self.endpoint, json=payload, timeout=5.0, headers=headers)
            if ctx.logger:
                ctx.logger.info({'event': 'http_sink_emit', 'status_code': r.status_code, 'count': len(batch), 'span_id': span.span_id})
        except Exception as e:
            if ctx.logger:
                ctx.logger.error({'event': 'http_sink_error', 'error': str(e), 'span_id': span.span_id})
