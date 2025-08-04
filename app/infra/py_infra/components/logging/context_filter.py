# components/logging/context_filter.py
import logging
from  components.logging.context import get_trace_id, get_execution_time

class LoggingContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.traceid = get_trace_id()
        exec_time = get_execution_time()
        record.execution_time = exec_time if exec_time is not None else 0.0
        return True
