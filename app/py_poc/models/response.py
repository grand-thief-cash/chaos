# py_poc/models/response.py
from pydantic import BaseModel
from typing import Optional, Any, Dict

class BaseResponse(BaseModel):
    """基础响应模型"""
    status: str = "success"
    message: str
    trace_id: Optional[str] = None

class DataFetchResponse(BaseResponse):
    """数据获取响应模型"""
    data: Dict[str, Any]

class DataStatusResponse(BaseResponse):
    """数据获取状态响应模型"""
    data: Dict[str, Any]

class ErrorResponse(BaseResponse):
    """错误响应模型"""
    status: str = "error"
    data: Optional[Dict[str, Any]] = None