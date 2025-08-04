# app/infra/pyinfra/components/logging/context.py
import threading
from typing import Optional

# 线程本地存储
_local = threading.local()

def set_trace_id(trace_id: str):
    """设置当前线程的追踪ID"""
    _local.trace_id = trace_id

def get_trace_id() -> str:
    """获取当前线程的追踪ID"""
    return getattr(_local, 'trace_id', 'unknown')

def set_execution_time(execution_time: float):
    """设置当前线程的执行时间"""
    _local.execution_time = execution_time

def get_execution_time() -> Optional[float]:
    """获取当前线程的执行时间"""
    return getattr(_local, 'execution_time', None)

def clear_context():
    """清除当前线程的上下文"""
    for attr in ['trace_id', 'execution_time']:
        if hasattr(_local, attr):
            delattr(_local, attr)