import json
import logging
import logging.handlers
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict

from artemis.core import cfg_mgr

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

        cfg = cfg_mgr.logging_config()
        if cfg.include_caller:
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
        cfg = cfg_mgr.logging_config()
    except Exception:
        cfg = cfg_mgr.LoggingCfg()

    level = getattr(logging, cfg.level.upper(), logging.INFO)
    fmt = cfg.format
    output = cfg.output
    if output == 'file':
        log_dir = cfg.file_config.dir
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{cfg.file_config.filename}.log")

        # Parse max_age to compute backupCount (days to keep)
        backup_count = _parse_max_age_days(cfg)

        handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        handler.suffix = "%Y%m%d"
        handler.namer = lambda name: name if name.endswith('.log') else name

        # Clean up old log files on startup
        if cfg.rotate_config.cleanup_enabled:
            _cleanup_old_logs(log_dir, cfg.file_config.filename, backup_count)
    elif output == 'stderr':
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


def _parse_max_age_days(cfg) -> int:
    """Parse rotate_config.max_age (e.g. '72h', '3d', '7d') to backupCount (days)."""
    max_age = getattr(cfg, 'rotate_config', None)
    if max_age is None:
        return 7
    raw = getattr(max_age, 'max_age', '72h')
    m = re.match(r'^(\d+)([hd])$', str(raw).strip().lower())
    if not m:
        return 7
    val, unit = int(m.group(1)), m.group(2)
    if unit == 'h':
        return max(1, val // 24)
    return max(1, val)


def _cleanup_old_logs(log_dir: str, base_name: str, keep_days: int):
    """Delete rotated log files older than keep_days on startup."""
    now = time.time()
    cutoff = now - (keep_days * 86400)
    pattern = re.compile(re.escape(base_name) + r'\.log\.\d{8}$')
    try:
        for fname in os.listdir(log_dir):
            if not pattern.match(fname):
                continue
            fpath = os.path.join(log_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass
    except OSError:
        pass

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
