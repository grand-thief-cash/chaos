# infra/pyinfra/components/grpc_client/error_handler.py
import grpc
import logging
from functools import wraps
from typing import Dict, Any, Optional
from components.logging.context import get_trace_id

logger = logging.getLogger(__name__)


class GRPCError(Exception):
    """GRPC错误基类"""

    def __init__(self, message: str, code: grpc.StatusCode = None, details: str = None):
        super().__init__(message)
        self.code = code
        self.details = details
        self.trace_id = get_trace_id()


class GRPCConnectionError(GRPCError):
    """GRPC连接错误"""
    pass


class GRPCTimeoutError(GRPCError):
    """GRPC超时错误"""
    pass


class GRPCPermissionError(GRPCError):
    """GRPC权限错误"""
    pass


class GRPCUnavailableError(GRPCError):
    """GRPC服务不可用错误"""
    pass


def grpc_error_handler(operation_name: str = None):
    """GRPC错误处理装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            trace_id = get_trace_id()

            try:
                return func(*args, **kwargs)

            except grpc.RpcError as e:
                code = e.code()
                details = e.details()

                error_info = {
                    "operation": op_name,
                    "code": code.name if code else "UNKNOWN",
                    "details": details,
                    "trace_id": trace_id
                }

                logger.error(f"GRPC call failed: {error_info}")

                # 根据错误码抛出不同的异常
                if code == grpc.StatusCode.UNAVAILABLE:
                    raise GRPCUnavailableError(f"Service unavailable: {details}", code, details)
                elif code == grpc.StatusCode.DEADLINE_EXCEEDED:
                    raise GRPCTimeoutError(f"Request timed out: {details}", code, details)
                elif code == grpc.StatusCode.PERMISSION_DENIED:
                    raise GRPCPermissionError(f"Permission denied: {details}", code, details)
                elif code == grpc.StatusCode.UNAUTHENTICATED:
                    raise GRPCPermissionError(f"Authentication failed: {details}", code, details)
                elif code in [grpc.StatusCode.FAILED_PRECONDITION,
                              grpc.StatusCode.ABORTED,
                              grpc.StatusCode.INTERNAL]:
                    raise GRPCConnectionError(f"Connection error: {details}", code, details)
                else:
                    raise GRPCError(f"GRPC call failed with code {code}: {details}", code, details)

            except Exception as e:
                logger.error(f"Unexpected error in GRPC call {op_name}: {str(e)}, trace_id: {trace_id}")
                raise GRPCError(f"Unexpected error in {op_name}: {str(e)}")

        return wrapper

    return decorator


class GRPCErrorTranslator:
    """GRPC错误转换器"""

    @staticmethod
    def to_dict(error: GRPCError) -> Dict[str, Any]:
        """将GRPC错误转换为字典格式"""
        return {
            "error_type": type(error).__name__,
            "message": str(error),
            "code": error.code.name if error.code else None,
            "details": error.details,
            "trace_id": error.trace_id,
            "retryable": GRPCErrorTranslator.is_retryable(error)
        }

    @staticmethod
    def is_retryable(error: GRPCError) -> bool:
        """判断错误是否可重试"""
        if not error.code:
            return False

        retryable_codes = [
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
            grpc.StatusCode.ABORTED
        ]

        return error.code in retryable_codes