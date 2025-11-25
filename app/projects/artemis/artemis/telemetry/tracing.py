from dataclasses import dataclass
from typing import Optional
from uuid import uuid4


@dataclass
class TraceContext:
    trace_id: str
    span_id: Optional[str] = None
    flags: str = '01'

_TRACE_ID_LEN = 32
_SPAN_ID_LEN = 16

def _is_valid_hex(s: str, length: int) -> bool:
    if len(s) != length:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False

def extract_trace(headers: dict) -> TraceContext:
    tp = headers.get('traceparent') or headers.get('Traceparent') or ''
    parts = tp.split('-')
    if len(parts) == 4 and parts[0] == '00' and _is_valid_hex(parts[1], _TRACE_ID_LEN) and _is_valid_hex(parts[2], _SPAN_ID_LEN):
        return TraceContext(trace_id=parts[1], span_id=parts[2], flags=parts[3])
    # create new trace
    return TraceContext(trace_id=uuid4().hex, span_id=None, flags='01')

def new_span(trace_id: str, parent_span_id: Optional[str], name: str) -> TraceContext:
    # minimal span representation
    return TraceContext(trace_id=trace_id, span_id=uuid4().hex[:_SPAN_ID_LEN], flags='01')
