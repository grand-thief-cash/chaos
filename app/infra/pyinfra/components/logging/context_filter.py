# components/logging/context_filter.py
import logging
from .context import get_trace_id, get_execution_time

class LoggingContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.traceid = get_trace_id()
        record.execution_time = get_execution_time()
        return True
