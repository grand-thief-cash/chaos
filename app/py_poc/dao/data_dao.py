# py_poc/dao/data_dao.py
from dao.base_dao import BaseDAO
from models.entity import DataRecord, FetchStatus
from typing import List
import asyncio
from datetime import datetime


class DataDAO(BaseDAO):
    """数据访问对象"""

    def __init__(self):
        super().__init__()
        # 模拟数据存储
        self._data_storage = []
        self._status_storage = FetchStatus(
            status="idle",
            last_fetch_time=None,
            next_fetch_time=None,
            total_records=0
        )

    async def fetch_all_records(self) -> List[DataRecord]:
        """获取所有数据记录"""
        await self.log_operation("fetch_all_records")

        # 模拟数据库查询
        await asyncio.sleep(0.1)

        if not self._data_storage:
            # 初始化一些示例数据
            self._data_storage = [
                DataRecord(id=1, name="sample_data_1", value=100),
                DataRecord(id=2, name="sample_data_2", value=200),
                DataRecord(id=3, name="sample_data_3", value=300)
            ]

        return self._data_storage.copy()

    async def get_current_status(self) -> FetchStatus:
        """获取当前状态"""
        await self.log_operation("get_current_status")
        return self._status_storage

    async def update_fetch_status(self, status: str):
        """更新获取状态"""
        await self.log_operation("update_fetch_status", f"Status: {status}")

        self._status_storage.status = status
        if status == "completed":
            self._status_storage.last_fetch_time = datetime.utcnow()
            self._status_storage.total_records = len(self._data_storage)

        # 模拟数据库更新
        await asyncio.sleep(0.05)

    async def refresh_all_data(self):
        """刷新所有数据"""
        await self.log_operation("refresh_all_data")

        # 模拟从外部源获取新数据
        await asyncio.sleep(1)

        # 更新数据
        new_data = [
            DataRecord(id=i, name=f"refreshed_data_{i}", value=i * 50)
            for i in range(1, 6)
        ]
        self._data_storage = new_data

        self.logger.info(f"Data refreshed, total records: {len(self._data_storage)}")