# pyinfra/core/component.py
from pydantic import BaseModel
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class ComponentConfig(BaseModel):
    """各组件自定义继承这个类"""
    enabled: bool = True

class BaseComponent(ABC):
    """组件行为接口"""
    def __init__(self, config: ComponentConfig):
        self.config = config
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @abstractmethod
    def start(self):
        """启动组件"""
        self._active = True
        logger.info(f"{self.__class__.__name__} started")

    @abstractmethod
    def stop(self):
        """停止组件"""
        self._active = False
        logger.info(f"{self.__class__.__name__} stopped")

    def health_check(self) -> bool:
        """默认健康检查实现"""
        return self._active