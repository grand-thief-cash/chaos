import inspect
import json
import logging
import sys
from typing import Any, Dict

from artemis.core.config import logging_config

_config_applied = False
_reconfigurable_handler: logging.Handler | None = None

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            'timestamp': self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            'level': record.levelname.lower(),
            'logger': record.name,
            'message': record.getMessage(),
        }
        if isinstance(record.args, dict):
            base.update(record.args)
        cfg = logging_config()
        if cfg.get('include_caller', True):
            frame = record.__dict__.get('frame') or inspect.currentframe()
            if frame:
                fi = inspect.getframeinfo(frame)
                base['caller'] = f"{fi.filename}:{fi.lineno}"
        if 'run_id' in base or 'task_code' in base:
            base['event_type'] = 'task'
        else:
            base['event_type'] = 'log'
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
