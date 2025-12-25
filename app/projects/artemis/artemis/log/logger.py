import json
import logging
import os
import sys
from typing import Any, Dict

from artemis.core.config import logging_config

_config_applied = False
_reconfigurable_handler: logging.Handler | None = None

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Try to get trace info from OTEL
        trace_id, span_id = None, None
        try:
            from artemis.telemetry.otel import current_trace_ids
            ids = current_trace_ids()
            trace_id = ids.get('trace_id')
            span_id = ids.get('span_id')
        except (ImportError, Exception):
            pass

        base: Dict[str, Any] = {
            'timestamp': self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            'level': record.levelname.lower(),
            'logger': record.name,
        }

        if trace_id:
            base['trace_id'] = trace_id
        if span_id:
            base['span_id'] = span_id

        # Handle message
        msg_obj = record.msg
        if isinstance(msg_obj, dict):
            base['message'] = msg_obj
        else:
            base['message'] = record.getMessage()

        if isinstance(record.args, dict):
            base.update(record.args)

        cfg = logging_config()
        if cfg.get('include_caller', True):
            pathname = record.pathname
            try:
                pathname = os.path.relpath(pathname)
            except ValueError:
                pass
            base['caller'] = f"{pathname}:{record.lineno}"

        return json.dumps(base, ensure_ascii=False)

def _apply_config(force: bool = False):
    global _config_applied, _reconfigurable_handler
    if _config_applied and not force:
        return
    try:
        cfg = logging_config()
    except Exception:
        cfg = {}
    level = getattr(logging, cfg.get('level', 'INFO').upper(), logging.INFO)
    fmt = cfg.get('format', 'json')
    output = cfg.get('output', 'stdout')
    if output == 'stderr':
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.StreamHandler(sys.stdout)
    if fmt == 'json':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    root = logging.getLogger()
    if _reconfigurable_handler in root.handlers:
        root.removeHandler(_reconfigurable_handler)
    root.addHandler(handler)
    root.setLevel(level)
    _reconfigurable_handler = handler
    _config_applied = True

_apply_config()

def reconfigure_logging():
    _apply_config(force=True)

_loggers: Dict[str, logging.Logger] = {}

def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    l = logging.getLogger(name)
    _loggers[name] = l
    return l
