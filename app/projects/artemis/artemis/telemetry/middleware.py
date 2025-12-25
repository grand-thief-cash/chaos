from fastapi import FastAPI, Request
from starlette.datastructures import MutableHeaders
import uuid
import time

from artemis.telemetry.otel import current_trace_ids
from artemis.log.logger import get_logger

logger = get_logger("http_access")


def add_trace_id_middleware(app: FastAPI) -> None:
    """Attach middleware to inject/ensure X-Trace-Id header.

    行为约定：
    1. 优先从当前 OpenTelemetry span 中读取 trace_id（如果 OTEL 已开启且有活跃 span）。
    2. 若没有 OTEL span（例如未初始化或未采样），则从请求 headers 中解析/生成 traceparent，
       确保本次请求依然有一个可追踪的 trace_id，方便后续调用下游服务时传递。
    3. 无论 SYNC/ASYNC，都尽量设置 X-Trace-Id，提升可观测性。
    """

    @app.middleware("http")
    async def add_trace_id_header(request: Request, call_next):  # type: ignore[unused-ignore]
        start_time = time.time()

        # 1) Check/Generate trace context
        traceparent = request.headers.get("traceparent")
        trace_id = request.headers.get("X-Trace-Id")

        inject_headers = False
        new_traceparent = None

        if not traceparent:
            # No standard traceparent.
            # If we have X-Trace-Id, try to use it.
            if trace_id:
                # Validate length (simple check)
                if len(trace_id) != 32:
                    # Invalid length for W3C, generate new one for OTEL
                    trace_id = uuid.uuid4().hex
            else:
                # No trace_id either. Generate one.
                trace_id = uuid.uuid4().hex

            # Create a dummy parent span ID to form a valid traceparent
            # This forces OTEL to use our trace_id
            span_id = uuid.uuid4().hex[:16]
            new_traceparent = f"00-{trace_id}-{span_id}-01"
            inject_headers = True

        if inject_headers and new_traceparent:
            # Modify request headers
            headers = MutableHeaders(scope=request.scope)
            headers["traceparent"] = new_traceparent
            if "X-Trace-Id" not in headers:
                headers["X-Trace-Id"] = trace_id

        # 2) Process request
        response = await call_next(request)

        # 3) Add headers to response
        # Get the actual trace_id from OTEL context
        ids = current_trace_ids()
        final_trace_id = ids.get("trace_id")
        final_span_id = ids.get("span_id")

        # Fallback to our generated trace_id if OTEL didn't pick up
        if not final_trace_id and trace_id:
            final_trace_id = trace_id

        if final_trace_id:
            try:
                response.headers["X-Trace-Id"] = final_trace_id
                if final_span_id:
                    response.headers["traceparent"] = f"00-{final_trace_id}-{final_span_id}-01"
            except Exception:
                pass

        # 4) Log access
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info({
            "event": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None
        })

        return response
