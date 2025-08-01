# py_poc/controllers/base_controller.py
from abc import ABC
from fastapi import Request, HTTPException
from typing import Any, Dict
import logging
from components.logging.context import get_trace_id

class BaseController(ABC):
    """基础控制器，提供通用功能"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_trace_id(self) -> str:
        """获取当前请求的追踪ID"""
        return get_trace_id()

    def log_request(self, request: Request, operation: str):
        """记录请求日志"""
        self.logger.info(f"Processing {operation}: {request.method} {request.url.path}")

    def handle_exception(self, e: Exception, operation: str):
        """统一异常处理"""
        error_msg = f"{operation} failed: {str(e)}"
        self.logger.error(error_msg)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": error_msg,
                "trace_id": self.get_trace_id()
            }
        )