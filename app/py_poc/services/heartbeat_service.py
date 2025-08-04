# py_poc/services/heartbeat_service.py (完整版本)
from services.base_service import BaseService
from components.grpc_client.utils import get_grpc_stub, grpc_call_with_trace, GRPCClientHelper
from components.grpc_client.error_handler import grpc_error_handler, GRPCError, GRPCErrorTranslator
from typing import Dict, Any
from datetime import datetime
import time

# 导入生成的GRPC代码
try:
    # 使用生成的文件路径
    import sys
    import os

    # 添加生成的proto文件路径到Python路径
    proto_path = os.path.join(os.path.dirname(__file__), '..', '..', 'generated', 'py_gen', 'grpc', 'internal',
                              'heartbeats', 'v1')
    if proto_path not in sys.path:
        sys.path.insert(0, proto_path)

    import heartbeats_pb2
    import heartbeats_pb2_grpc
    from google.protobuf.timestamp_pb2 import Timestamp

    PROTO_AVAILABLE = True

except ImportError as e:
    # proto文件导入失败的模拟类
    PROTO_AVAILABLE = False


    class MockHeartbeatServiceStub:
        def CheckHeartbeat(self, request, **kwargs):
            # 模拟响应
            response = MockHeartbeatResponse()
            response.response = f"Mock pong! Received: {request.message}"
            response.status = 1  # HEALTHY
            return response


    class MockHeartbeatRequest:
        def __init__(self, message="", sent_at=None):
            self.message = message
            self.sent_at = sent_at or MockTimestamp()


    class MockHeartbeatResponse:
        def __init__(self):
            self.response = "Mock response"
            self.status = 1  # HEALTHY
            self.replied_at = MockTimestamp()


    class MockTimestamp:
        def GetCurrentTime(self):
            pass

        def CopyFrom(self, other):
            pass

        def ToDatetime(self):
            return datetime.now()


    heartbeats_pb2_grpc = type('MockModule', (), {
        'HeartbeatServiceStub': MockHeartbeatServiceStub
    })()

    heartbeats_pb2 = type('MockModule', (), {
        'HeartbeatRequest': MockHeartbeatRequest,
        'HeartbeatResponse': MockHeartbeatResponse
    })()

    Timestamp = MockTimestamp


class HeartbeatService(BaseService):
    """心跳检测服务"""

    def __init__(self):
        super().__init__()
        self.heartbeat_stub = None
        self.proto_available = PROTO_AVAILABLE
        self._initialize_grpc_client()

    def _initialize_grpc_client(self):
        """初始化GRPC客户端"""
        try:
            self.heartbeat_stub = get_grpc_stub("heartbeat_service", heartbeats_pb2_grpc.HeartbeatServiceStub)
            if self.heartbeat_stub:
                self.logger.info("Heartbeat GRPC client initialized successfully")
            else:
                self.logger.warning("Heartbeat GRPC client not available")
        except Exception as e:
            self.logger.error(f"Failed to initialize heartbeat GRPC client: {str(e)}")

    @grpc_call_with_trace
    @grpc_error_handler("check_heartbeat")
    async def check_heartbeat(self, message: str = "ping") -> Dict[str, Any]:
        """执行心跳检测"""
        await self.log_operation("check_heartbeat", f"message: {message}")

        if not self.heartbeat_stub:
            error_result = {
                "success": False,
                "error": "GRPC client not available",
                "client_status": "disconnected",
                "proto_available": self.proto_available
            }
            self.logger.error(f"Heartbeat check failed: {error_result}")
            return error_result

        try:
            # 创建请求
            request = heartbeats_pb2.HeartbeatRequest()
            request.message = message

            # 设置时间戳
            if self.proto_available:
                current_time = Timestamp()
                current_time.GetCurrentTime()
                request.sent_at.CopyFrom(current_time)
            else:
                request.sent_at = Timestamp()

            # 创建元数据
            metadata = GRPCClientHelper.create_metadata()

            # 执行GRPC调用
            start_time = time.time()
            response = GRPCClientHelper.call_with_retry(
                self.heartbeat_stub.CheckHeartbeat,
                request,
                metadata=metadata,
                timeout=10,
                max_retries=2,
                retry_delay=1.0
            )

            latency = (time.time() - start_time) * 1000  # 转换为毫秒

            # 解析响应
            status_map = {
                0: "UNKNOWN",
                1: "HEALTHY",
                2: "WARNING"
            }

            result = {
                "success": True,
                "request_message": message,
                "response_message": response.response,
                "status": status_map.get(response.status, "UNKNOWN"),
                "status_code": response.status,
                "latency_ms": round(latency, 2),
                "sent_at": request.sent_at.ToDatetime().isoformat() if hasattr(request.sent_at,
                                                                               'ToDatetime') else datetime.now().isoformat(),
                "replied_at": response.replied_at.ToDatetime().isoformat() if hasattr(response.replied_at,
                                                                                      'ToDatetime') else datetime.now().isoformat(),
                "client_status": "connected",
                "proto_available": self.proto_available
            }

            self.logger.info(f"Heartbeat check completed: {result['status']}, latency: {latency:.2f}ms")
            return result

        except GRPCError as ge:
            # 处理已知的GRPC错误
            error_dict = GRPCErrorTranslator.to_dict(ge)
            result = {
                "success": False,
                "client_status": "error",
                "request_message": message,
                "proto_available": self.proto_available,
                **error_dict
            }

            self.logger.error(f"GRPC heartbeat check failed: {result}")
            return result

        except Exception as e:
            # 处理未知错误
            self.logger.error(f"Unexpected heartbeat check error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "client_status": "error",
                "request_message": message,
                "proto_available": self.proto_available
            }

    async def get_connection_status(self) -> Dict[str, Any]:
        """获取GRPC连接状态"""
        await self.log_operation("get_connection_status")

        grpc_component = self.get_component("grpc_clients")
        if not grpc_component:
            return {
                "grpc_clients_component": "not_found",
                "heartbeat_client": "unavailable",
                "proto_available": self.proto_available
            }

        # 获取heartbeat客户端状态
        heartbeat_client = grpc_component.get_client("heartbeat_service")
        if heartbeat_client:
            try:
                state = heartbeat_client.get_state(try_to_connect=False)

                # 处理不同版本的grpc状态获取方式
                if hasattr(state, 'value'):
                    state_value = state.value[0] if isinstance(state.value, (list, tuple)) else state.value
                else:
                    state_value = state

                state_name = {
                    0: "IDLE",
                    1: "CONNECTING",
                    2: "READY",
                    3: "TRANSIENT_FAILURE",
                    4: "SHUTDOWN"
                }.get(state_value, "UNKNOWN")

                return {
                    "grpc_clients_component": "available",
                    "heartbeat_client": "available",
                    "connection_state": state_name,
                    "connection_state_code": state_value,
                    "client_initialized": self.heartbeat_stub is not None,
                    "proto_available": self.proto_available
                }
            except Exception as e:
                return {
                    "grpc_clients_component": "available",
                    "heartbeat_client": "available",
                    "connection_state": "error",
                    "error": str(e),
                    "client_initialized": self.heartbeat_stub is not None,
                    "proto_available": self.proto_available
                }
        else:
            return {
                "grpc_clients_component": "available",
                "heartbeat_client": "not_found",
                "client_initialized": False,
                "proto_available": self.proto_available
            }

    @grpc_call_with_trace
    async def ping_pylon_service(self, message: str = "ping from data-fetcher") -> Dict[str, Any]:
        """专门用于测试Pylon服务的ping方法"""
        await self.log_operation("ping_pylon_service", f"message: {message}")

        result = await self.check_heartbeat(message)

        # 添加一些Pylon特定的信息
        if result.get("success"):
            result["pylon_service"] = "heartbeat"
            result["test_type"] = "ping"

        return result

    async def health_check_pylon(self) -> Dict[str, Any]:
        """Pylon服务健康检查"""
        await self.log_operation("health_check_pylon")

        try:
            # 执行多次ping检测平均延迟
            ping_count = 3
            latencies = []

            for i in range(ping_count):
                result = await self.check_heartbeat(f"health_check_{i + 1}")
                if result.get("success"):
                    latencies.append(result.get("latency_ms", 0))
                else:
                    return {
                        "success": False,
                        "error": "Health check failed",
                        "failed_at_ping": i + 1,
                        "last_error": result.get("error", "Unknown error")
                    }

            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            return {
                "success": True,
                "health_status": "healthy" if avg_latency < 100 else "slow",
                "average_latency_ms": round(avg_latency, 2),
                "ping_count": ping_count,
                "all_latencies": latencies,
                "pylon_service": "heartbeat"
            }

        except Exception as e:
            self.logger.error(f"Pylon health check failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }