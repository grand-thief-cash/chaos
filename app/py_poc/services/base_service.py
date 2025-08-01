# py_poc/services/base_service.py
from abc import ABC
from core.container import Container
import logging


class BaseService(ABC):
    """基础服务类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.container = Container

    def get_component(self, name: str):
        """获取注册的组件"""
        component = self.container.resolve(name)
        if not component:
            self.logger.warning(f"Component '{name}' not found in container")
        return component

    async def log_operation(self, operation: str, details: str = ""):
        """记录操作日志"""
        self.logger.info(f"Service operation: {operation} {details}")