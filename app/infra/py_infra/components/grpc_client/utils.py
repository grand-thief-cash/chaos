# infra/pyinfra/components/grpc_client/utils.py (更新版本)
import grpc
import logging
from typing import Optional, Any, Callable
from functools import wraps
from components.logging.context import get_trace_id, set_execution_time
from components.grpc_client.error_handler import grpc_error_handler, GRPCError
from core.container import Container
import time

logger = logging.getLogger(__name__)

def get_grpc_client(client_name: str) -> Optional[grpc.Channel]:
    """获取GRPC客户端连接"""
    grpc_component = Container.resolve("grpc_clients")
    if grpc_component:
        return grpc_component.get_client(client_name)
    logger.error("GRPC clients component not found")
    return None

def get_grpc_stub(client_name: str, stub_class):
    """获取GRPC Stub"""
    grpc_component = Container.resolve("grpc_clients")
    if grpc_component:
        return grpc_component.get_stub(client_name, stub_class)
    logger.error("GRPC clients component not found")
    return None

def grpc_call_with_trace(func: Callable):
    """GRPC调用装饰器，添加追踪和性能监控"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        trace_id = get_trace_id()

        try:
            logger.info(f"GRPC call started: {func.__name__}, trace_id: {trace_id}")

            # 执行GRPC调用
            result = func(*args, **kwargs)

            execution_time = time.time() - start_time
            set_execution_time(execution_time)

            logger.info(f"GRPC call completed: {func.__name__}, time: {execution_time:.3f}s")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            set_execution_time(execution_time)

            logger.error(f"GRPC call failed: {func.__name__}, time: {execution_time:.3f}s, error: {str(e)}")
            raise

    return wrapper

class GRPCClientHelper:
    """GRPC客户端辅助类"""

    @staticmethod
    def create_metadata(trace_id: Optional[str] = None) -> list:
        """创建GRPC元数据"""
        if not trace_id:
            trace_id = get_trace_id()

        return [
            ('trace-id', trace_id),
            ('user-agent', 'pyinfra-grpc-client/1.0'),
            ('client-version', '1.0.0')
        ]

    @staticmethod
    @grpc_error_handler("grpc_call_with_retry")
    def call_with_retry(stub_method, request, max_retries: int = 3,
                       retry_delay: float = 1.0, **kwargs):
        """带重试的GRPC调用"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"GRPC retry attempt {attempt}/{max_retries}")
                    time.sleep(retry_delay * attempt)

                # 添加元数据
                metadata = kwargs.get('metadata', [])
                if isinstance(metadata, list):
                    metadata.extend(GRPCClientHelper.create_metadata())
                    kwargs['metadata'] = metadata

                return stub_method(request, **kwargs)

            except grpc.RpcError as e:
                last_exception = e

                # 检查是否应该重试
                if e.code() in [grpc.StatusCode.UNAVAILABLE,
                               grpc.StatusCode.DEADLINE_EXCEEDED,
                               grpc.StatusCode.RESOURCE_EXHAUSTED]:
                    if attempt < max_retries:
                        logger.warning(f"GRPC call failed (attempt {attempt + 1}), retrying: {e.code()}")
                        continue

                # 不可重试的错误或重试次数用完
                break

        # 重试失败，抛出最后的异常
        if last_exception:
            raise last_exception