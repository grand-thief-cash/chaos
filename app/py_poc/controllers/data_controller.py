# py_poc/controllers/data_controller.py (更新版本)
from fastapi import APIRouter, Request, HTTPException
from controllers.base_controller import BaseController
from services.data_service import DataService
from services.heartbeat_service import HeartbeatService
from models.response import DataFetchResponse, DataStatusResponse
from pydantic import BaseModel


class HeartbeatCheckRequest(BaseModel):
    """心跳检测请求"""
    message: str = "ping"


class DataController(BaseController):
    """数据相关控制器"""

    def __init__(self):
        super().__init__()
        self.data_service = DataService()
        self.heartbeat_service = HeartbeatService()
        self.router = APIRouter(prefix="/api/v1/data", tags=["data"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        # 原有的数据接口...

        # 心跳检测接口
        @self.router.post("/heartbeat/check", response_model=DataFetchResponse)
        async def check_heartbeat(request: Request, heartbeat_req: HeartbeatCheckRequest = HeartbeatCheckRequest()):
            """检测GRPC服务心跳"""
            self.log_request(request, "check_heartbeat")

            try:
                result = await self.heartbeat_service.check_heartbeat(heartbeat_req.message)
                return DataFetchResponse(
                    message="Heartbeat check completed",
                    data=result,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Heartbeat check")

        @self.router.get("/heartbeat/status", response_model=DataStatusResponse)
        async def get_heartbeat_status(request: Request):
            """获取GRPC连接状态"""
            self.log_request(request, "get_heartbeat_status")

            try:
                status = await self.heartbeat_service.get_connection_status()
                return DataStatusResponse(
                    message="Heartbeat status retrieved successfully",
                    data=status,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Get heartbeat status")

        @self.router.post("/pylon/ping", response_model=DataFetchResponse)
        async def ping_pylon(request: Request, heartbeat_req: HeartbeatCheckRequest = HeartbeatCheckRequest()):
            """Ping Pylon服务"""
            self.log_request(request, "ping_pylon")

            try:
                result = await self.heartbeat_service.ping_pylon_service(heartbeat_req.message)
                return DataFetchResponse(
                    message="Pylon ping completed",
                    data=result,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Pylon ping")

        @self.router.get("/pylon/health", response_model=DataFetchResponse)
        async def check_pylon_health(request: Request):
            """Pylon服务健康检查"""
            self.log_request(request, "check_pylon_health")

            try:
                result = await self.heartbeat_service.health_check_pylon()
                return DataFetchResponse(
                    message="Pylon health check completed",
                    data=result,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Pylon health check")

    def get_router(self) -> APIRouter:
        """获取路由器"""
        return self.router