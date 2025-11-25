"""Logging helper utilities."""
from __future__ import annotations

import logging
from typing import Any

from .logger import get_logger

_DEF_EVENT_KEY = 'event'

def log_event(logger: logging.Logger | str, event: str, **fields: Any) -> None:
    """Emit a structured log event with arbitrary fields.
    Accepts either a logger instance or a logger name.
    Usage:
        log_event('my.component', 'user_login', user_id=123)
    """
    lg = get_logger(logger) if isinstance(logger, str) else logger
    payload = {_DEF_EVENT_KEY: event, **fields}
    lg.info(payload)

__all__ = ['log_event']

