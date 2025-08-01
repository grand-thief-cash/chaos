# py_poc/controllers/data_controller.py
from fastapi import APIRouter, Request, HTTPException
from controllers.base_controller import BaseController
from services.data_service import DataService
from models.request import DataFetchRequest, DataRefreshRequest
from models.response import DataFetchResponse, DataStatusResponse, ErrorResponse
from typing import Union

class DataController(BaseController):
    """数据相关控制器"""

    def __init__(self):
        super().__init__()
        self.data_service = DataService()
        self.router = APIRouter(prefix="/api/v1/data", tags=["data"])
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.router.get("/fetch", response_model=DataFetchResponse)
        async def fetch_data(request: Request):
            """获取数据接口"""
            self.log_request(request, "fetch_data")

            try:
                data = await self.data_service.fetch_data()
                return DataFetchResponse(
                    message="Data fetched successfully",
                    data=data,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Data fetch")

        @self.router.get("/status", response_model=DataStatusResponse)
        async def get_fetch_status(request: Request):
            """获取数据获取状态"""
            self.log_request(request, "get_fetch_status")

            try:
                status = await self.data_service.get_fetch_status()
                return DataStatusResponse(
                    message="Status retrieved successfully",
                    data=status,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Get fetch status")

        @self.router.post("/refresh", response_model=DataFetchResponse)
        async def refresh_data(request: Request, refresh_req: DataRefreshRequest = DataRefreshRequest()):
            """手动刷新数据"""
            self.log_request(request, "refresh_data")

            try:
                result = await self.data_service.refresh_data(refresh_req)
                return DataFetchResponse(
                    message="Data refresh triggered successfully",
                    data=result,
                    trace_id=self.get_trace_id()
                )
            except Exception as e:
                self.handle_exception(e, "Data refresh")

    def get_router(self) -> APIRouter:
        """获取路由器"""
        return self.router