"""OpenTelemetry initialization and helpers with graceful fallback.

Reads telemetry config:
telemetry:
  enabled: true
  service_name: artemis
  sampling: always  # always|parent|off|ratio:<0..1>
Exports init_otel() which sets up tracer provider and instrumentation.
"""
from __future__ import annotations

from typing import Optional

from artemis.core.config import telemetry_config, environment
from artemis.log.logger import get_logger

_OTEL_INITIALIZED = False
_meter = None
_task_duration_hist = None
_task_run_counter = None
_task_error_counter = None

def init_otel() -> bool:
    global _OTEL_INITIALIZED, _meter, _task_duration_hist, _task_run_counter, _task_error_counter
    if _OTEL_INITIALIZED:
        return True
    cfg = telemetry_config()
    if not cfg.get('enabled', True):
        return False
    log = get_logger('telemetry')
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        # metrics optional classes
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        # exporters referenced below lazily; don't import span exporter yet
    except ImportError:
        return False

    service_name = cfg.get('service_name', 'artemis')
    sampling_cfg = (cfg.get('sampling') or 'always').lower()
    ratio = 1.0
    if sampling_cfg.startswith('ratio:'):
        _, _, ratio_str = sampling_cfg.partition('ratio:')
        try:
            ratio = float(ratio_str)
            ratio = max(0.0, min(1.0, ratio))
        except ValueError:
            ratio = 1.0
        sampler = ParentBased(TraceIdRatioBased(ratio))
    elif sampling_cfg in ('always','parent'):
        sampler = ParentBased(TraceIdRatioBased(1.0))
    elif sampling_cfg == 'off':
        sampler = ParentBased(TraceIdRatioBased(0.0))
    else:
        sampler = ParentBased(TraceIdRatioBased(1.0))

    import platform, os
    service_version = cfg.get('service_version') or cfg.get('version') or 'unknown'
    deployment_env = environment()
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": deployment_env,
        "process.pid": os.getpid(),
        "process.runtime.name": platform.python_implementation(),
        "process.runtime.version": platform.python_version(),
        "os.type": platform.system(),
        "os.version": platform.version(),
        "host.name": platform.node(),
    })
    provider = TracerProvider(resource=resource, sampler=sampler)
    trace.set_tracer_provider(provider)

    otlp_cfg = cfg.get('otlp') or {}
    protocol = (otlp_cfg.get('protocol') or 'http').lower()
    endpoint = otlp_cfg.get('endpoint') or os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT') or ''
    headers = otlp_cfg.get('headers') or {}
    timeout_ms = int(otlp_cfg.get('timeout_ms', 5000))
    insecure = bool(otlp_cfg.get('insecure', False))
    use_console = bool(cfg.get('use_console_exporters', False))

    exporter = None
    if endpoint:
        try:
            if protocol == 'grpc':
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcExporter
                grpc_kwargs = {'endpoint': endpoint}
                if insecure: grpc_kwargs['insecure'] = True
                if headers: grpc_kwargs['headers'] = headers
                exporter = GrpcExporter(**grpc_kwargs)
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpExporter
                http_kwargs = {'endpoint': endpoint}
                if headers: http_kwargs['headers'] = headers
                if timeout_ms: http_kwargs['timeout'] = timeout_ms / 1000.0
                exporter = HttpExporter(**http_kwargs)
        except Exception as e:
            log.warning({'event': 'otel_exporter_init_failed', 'error': str(e), 'endpoint': endpoint})
            exporter = None
    elif use_console:
        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            log.info({'event': 'otel_console_span_exporter_enabled'})
        except Exception as e:
            log.warning({'event': 'otel_console_span_exporter_failed', 'error': str(e)})
    else:
        log.info({'event': 'otel_span_exporter_skipped', 'reason': 'no endpoint configured'})

    if exporter:
        try:
            provider.add_span_processor(BatchSpanProcessor(exporter))
            log.info({'event': 'otel_span_exporter_configured', 'endpoint': endpoint, 'protocol': protocol})
        except Exception as e:
            log.warning({'event': 'otel_span_processor_add_failed', 'error': str(e)})

    try:
        HTTPXClientInstrumentor().instrument()
    except Exception:
        pass

    # metrics setup (only if endpoint or console requested)
    metric_exporter = None
    readers = []
    if endpoint:
        try:
            metric_exporter = OTLPMetricExporter(endpoint=endpoint)
            readers.append(PeriodicExportingMetricReader(metric_exporter))
        except Exception as e:
            log.warning({'event': 'otel_metric_exporter_init_failed', 'error': str(e)})
    elif use_console:
        try:
            from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
            metric_exporter = ConsoleMetricExporter()
            readers.append(PeriodicExportingMetricReader(metric_exporter))
            log.info({'event': 'otel_console_metric_exporter_enabled'})
        except Exception as e:
            log.warning({'event': 'otel_console_metric_exporter_failed', 'error': str(e)})
    else:
        log.info({'event': 'otel_metric_exporter_skipped', 'reason': 'no endpoint configured'})

    try:
        from opentelemetry import metrics as metrics_api
        meter_provider = MeterProvider(resource=resource, metric_readers=readers) if readers else MeterProvider(resource=resource)
        metrics_api.set_meter_provider(meter_provider)
        _meter = metrics_api.get_meter("artemis")
        _task_duration_hist = _meter.create_histogram(name="task.duration.ms", unit="ms", description="Task execution duration in milliseconds")
        _task_run_counter = _meter.create_counter(name="task.run.count", description="Total number of task runs")
        _task_error_counter = _meter.create_counter(name="task.error.count", description="Total number of task errors")
    except Exception as e:
        log.warning({'event': 'otel_metric_init_failed', 'error': str(e)})
        _meter = None
        _task_duration_hist = None
        _task_run_counter = None
        _task_error_counter = None

    _OTEL_INITIALIZED = True
    return True


def instrument_fastapi_app(app) -> None:
    cfg = telemetry_config()
    if not cfg.get('enabled', True):
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
    except Exception:
        pass


def current_trace_ids() -> dict[str, Optional[str]]:
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if not span:
            return {"trace_id": None, "span_id": None}
        ctx = span.get_span_context()
        if not ctx or not ctx.is_valid:
            return {"trace_id": None, "span_id": None}
        return {
            "trace_id": f"{ctx.trace_id:032x}",
            "span_id": f"{ctx.span_id:016x}",
        }
    except Exception:
        return {"trace_id": None, "span_id": None}


def record_task_metrics(task_code: str, duration_ms: int | None, success: bool):
    if not _meter:
        return
    attrs = {"task.code": task_code}
    try:
        if _task_run_counter:
            _task_run_counter.add(1, attributes=attrs)
        if duration_ms is not None and _task_duration_hist:
            _task_duration_hist.record(float(duration_ms), attributes=attrs)
        if not success and _task_error_counter:
            _task_error_counter.add(1, attributes=attrs)
    except Exception:
        pass
