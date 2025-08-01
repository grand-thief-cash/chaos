# py_poc/dao/base_dao.py
from abc import ABC
from core.container import Container
import logging


class BaseDAO(ABC):
    """基础数据访问对象"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.container = Container

    def get_component(self, name: str):
        """获取注册的组件"""
        return self.container.resolve(name)

    async def log_operation(self, operation: str, details: str = ""):
        """记录数据操作日志"""
        self.logger.info(f"DAO operation: {operation} {details}")