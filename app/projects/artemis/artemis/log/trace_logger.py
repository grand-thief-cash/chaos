import logging
from typing import Any, Dict

class ContextLogger:
    def __init__(self, base: logging.Logger, static_fields: Dict[str, Any]):
        self._base = base
        self._fields = static_fields
    def _emit(self, level: str, event: str, **fields):
        payload = {**self._fields, 'event': event, **fields}
        getattr(self._base, level if level in ('debug','info','warning','error') else 'info')(payload)
    def debug(self, event: str, **fields): self._emit('debug', event, **fields)
    def info(self, event: str, **fields): self._emit('info', event, **fields)
    def warning(self, event: str, **fields): self._emit('warning', event, **fields)
    def error(self, event: str, **fields): self._emit('error', event, **fields)

def build_context_logger(base: logging.Logger, ctx) -> ContextLogger:
    static_fields = {
        'trace_id': getattr(ctx, 'trace_id', None),
        'span_id': getattr(ctx, 'span_id', None),
        'task_code': getattr(ctx, 'task_code', None),
    }
    return ContextLogger(base, static_fields)

