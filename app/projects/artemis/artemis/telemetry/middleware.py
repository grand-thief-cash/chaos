from fastapi import FastAPI, Request

from artemis.telemetry.otel import current_trace_ids
from artemis.telemetry.tracing import extract_trace


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
        # 1) 先让业务逻辑/其他中间件处理请求
        response = await call_next(request)

        trace_id = None

        # 2) 优先从 OTEL 当前 span 中拿 trace_id
        ids = current_trace_ids()
        if ids:
            trace_id = ids.get("trace_id")

        # 3) 如果当前没有有效 span，则从 traceparent 抽取或生成一个 trace_id
        if not trace_id:
            try:
                headers_dict = dict(request.headers)
                ctx = extract_trace(headers_dict)
                trace_id = ctx.trace_id
            except Exception:
                trace_id = None

        # 4) 写入响应头，不影响原有 Response 类型/内容
        if trace_id:
            try:
                response.headers["X-Trace-Id"] = trace_id
            except Exception:
                # 不允许 tracing 影响主流程
                pass

        return response
