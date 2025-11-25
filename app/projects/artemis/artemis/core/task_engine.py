from artemis.log.logger import get_logger
from artemis.log.trace_logger import build_context_logger
from artemis.telemetry.otel import init_otel
from . import task_registry
from .context import TaskContext


class TaskEngine:
    def __init__(self):
        self.logger = get_logger('TaskEngine')

    def _execute(self, task_code: str, incoming_params: dict, headers: dict | None, async_mode: bool = False):
        cls = task_registry.get(task_code)
        if not cls:
            self.logger.error(f"Task {task_code} not found")
            if async_mode:
                return None
            raise ValueError(f"task '{task_code}' not found")
        init_otel()
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
        except Exception:
            tracer = None
        ctx = TaskContext(task_code, incoming_params)
        base_logger = get_logger(task_code)
        ctx.set_logger(build_context_logger(base_logger, ctx))
        try:
            from artemis.callback.client import build_callback_client
            ctx.callback = build_callback_client(incoming_params, logger=ctx.logger, headers=headers)
        except Exception as e:
            if ctx.logger:
                ctx.logger.warning({'event':'callback_client_init_failed','error':str(e),'task_code':task_code})
        def run_unit():
            try:
                unit = cls()
                unit.run(ctx)
                return True, ctx
            except Exception as e:
                if ctx.logger:
                    ctx.logger.error({'event':'task_error','error':str(e),'task_code':task_code})
                try:
                    cb = ctx.callback
                    if cb and not cb.finalized():
                        cb.finalize_failed(str(e))
                except Exception as fe:
                    if ctx.logger:
                        ctx.logger.warning({'event':'callback_finalize_failed_error','error':str(fe),'task_code':task_code})
                return False, ctx
        if tracer:
            from opentelemetry.trace import Span
            with tracer.start_as_current_span(f"task.run.{task_code}") as span:  # type: Span
                ok,_ = run_unit()
                sc = span.get_span_context()
                if sc and sc.is_valid:
                    try:
                        from opentelemetry.trace import Status, StatusCode
                        span.set_attribute('task.code', task_code)
                        span.set_status(Status(StatusCode.OK if ok else StatusCode.ERROR))
                    except Exception:
                        pass
        else:
            run_unit()
        if async_mode:
            return None
        return {'task_code': task_code,'duration_ms': ctx.duration_ms(),'stats': ctx.stats}

    def run(self, task_code: str, incoming_params: dict, headers: dict | None = None) -> dict:
        return self._execute(task_code, incoming_params, headers, async_mode=False)

    def run_async(self, task_code: str, incoming_params: dict, headers: dict | None = None) -> dict:
        import threading
        threading.Thread(target=self._execute, args=(task_code, incoming_params, headers, True), daemon=True).start()
        meta = (incoming_params.get('_meta') or {})
        return {'task_code': task_code,'accepted': True,'exec_type': meta.get('exec_type','ASYNC'),'run_id': meta.get('run_id')}
