# py_poc/models/entity.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any

class DataRecord(BaseModel):
    """数据记录实体"""
    id: int
    name: str
    value: Any
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class FetchStatus(BaseModel):
    """获取状态实体"""
    status: str
    last_fetch_time: Optional[datetime] = None
    next_fetch_time: Optional[datetime] = None
    total_records: int = 0