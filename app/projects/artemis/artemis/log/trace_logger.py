import logging
from typing import Any, Dict

class ContextLogger:
    def __init__(self, base: logging.Logger, static_fields: Dict[str, Any]):
        self._base = base
        self._fields = static_fields
    def _emit(self, level: str, event: Any, **fields):
        # If event is a dict, merge it with fields
        if isinstance(event, dict):
            fields.update(event)
            event_name = fields.get('event', 'unknown')
        else:
            event_name = event

        payload = {**self._fields, **fields}
        if 'event' not in payload:
            payload['event'] = event_name

        # Use stacklevel=3 so that the log record reflects the caller of ctx.logger.info(...)
        # This requires Python 3.8+
        getattr(self._base, level if level in ('debug','info','warning','error') else 'info')(payload, stacklevel=3)

    def debug(self, event: Any, **fields): self._emit('debug', event, **fields)
    def info(self, event: Any, **fields): self._emit('info', event, **fields)
    def warning(self, event: Any, **fields): self._emit('warning', event, **fields)
    def error(self, event: Any, **fields): self._emit('error', event, **fields)

def build_context_logger(base: logging.Logger, ctx) -> ContextLogger:
    static_fields = {
        'trace_id': getattr(ctx, 'trace_id', None),
        'span_id': getattr(ctx, 'span_id', None),
        'task_code': getattr(ctx, 'task_code', None),
    }
    return ContextLogger(base, static_fields)

