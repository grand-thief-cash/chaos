# py_poc/services/data_service.py
from services.base_service import BaseService
from dao.data_dao import DataDAO
from models.request import DataRefreshRequest
from models.entity import DataRecord, FetchStatus
from typing import List, Dict, Any
import asyncio
from datetime import datetime


class DataService(BaseService):
    """数据服务"""

    def __init__(self):
        super().__init__()
        self.data_dao = DataDAO()
        # 获取GRPC客户端
        # self.user_service_stub = get_grpc_stub("user_service", UserServiceStub)


    async def fetch_data(self) -> Dict[str, Any]:
        """获取数据"""
        await self.log_operation("fetch_data", "Starting data fetch")

        try:
            # 通过DAO获取数据
            records = await self.data_dao.fetch_all_records()

            # 业务逻辑处理
            processed_data = await self._process_data(records)

            # 更新获取状态
            await self.data_dao.update_fetch_status("completed")

            return {
                "records": processed_data,
                "total": len(processed_data),
                "timestamp": datetime.utcnow().isoformat(),
                "fetch_id": f"fetch_{int(datetime.utcnow().timestamp())}"
            }

        except Exception as e:
            await self.data_dao.update_fetch_status("failed")
            self.logger.error(f"Data fetch failed: {str(e)}")
            raise

    async def get_fetch_status(self) -> Dict[str, Any]:
        """获取数据获取状态"""
        await self.log_operation("get_fetch_status")

        status = await self.data_dao.get_current_status()
        return {
            "status": status.status,
            "last_fetch": status.last_fetch_time.isoformat() if status.last_fetch_time else None,
            "next_fetch": status.next_fetch_time.isoformat() if status.next_fetch_time else None,
            "total_records": status.total_records
        }

    async def refresh_data(self, refresh_req: DataRefreshRequest = None) -> Dict[str, Any]:
        """刷新数据"""
        await self.log_operation("refresh_data", f"Force: {refresh_req.force if refresh_req else False}")

        try:
            # 检查是否可以刷新
            if refresh_req and not refresh_req.force:
                status = await self.data_dao.get_current_status()
                if status.status == "running":
                    raise ValueError("Data fetch is already running")

            # 启动刷新任务
            refresh_id = f"refresh_{int(datetime.utcnow().timestamp())}"
            await self.data_dao.update_fetch_status("running")

            # 异步执行刷新
            asyncio.create_task(self._background_refresh(refresh_id))

            return {
                "refresh_id": refresh_id,
                "started_at": datetime.utcnow().isoformat(),
                "status": "started"
            }

        except Exception as e:
            await self.data_dao.update_fetch_status("failed")
            raise

    async def _process_data(self, records: List[DataRecord]) -> List[Dict]:
        """处理数据"""
        processed = []
        for record in records:
            processed.append({
                "id": record.id,
                "name": record.name,
                "value": record.value,
                "processed_at": datetime.utcnow().isoformat()
            })
        return processed

    async def _background_refresh(self, refresh_id: str):
        """后台刷新任务"""
        try:
            self.logger.info(f"Starting background refresh: {refresh_id}")

            # 模拟数据获取
            await asyncio.sleep(2)

            # 更新数据
            await self.data_dao.refresh_all_data()
            await self.data_dao.update_fetch_status("completed")

            self.logger.info(f"Background refresh completed: {refresh_id}")

        except Exception as e:
            await self.data_dao.update_fetch_status("failed")
            self.logger.error(f"Background refresh failed: {refresh_id}, error: {str(e)}")