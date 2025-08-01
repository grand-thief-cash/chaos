# py_poc/models/request.py
from pydantic import BaseModel
from typing import Optional

class DataRefreshRequest(BaseModel):
    """数据刷新请求模型"""
    force: bool = False

class DataFetchRequest(BaseModel):
    """数据获取请求模型"""
    pass  # 目前为空，可以根据需要添加字段