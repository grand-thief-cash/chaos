# pyinfra/core/lifecycle.py
import signal
import threading
import logging
from typing import List, Callable, Dict, Type
from .component import BaseComponent

logger = logging.getLogger(__name__)

class LifecycleManager:
    _components: List[BaseComponent] = []
    _hooks: Dict[str, List[Callable]] = {
        'before_start': [],
        'after_start': [],
        'before_shutdown': [],
        'after_shutdown': [],
    }
    _stop_event = threading.Event()

    @classmethod
    def register_component(cls, component: BaseComponent):
        """注册组件到生命周期管理"""
        cls._components.append(component)
        logger.debug(f"Component registered: {type(component).__name__}")

    @classmethod
    def add_hook(cls, phase: str, func: Callable):
        """添加生命周期钩子"""
        if phase not in cls._hooks:
            raise ValueError(f"Invalid hook phase: {phase}")
        cls._hooks[phase].append(func)
        logger.debug(f"Hook added to {phase}: {func.__name__}")

    @classmethod
    def run_hooks(cls, phase: str):
        """执行指定阶段的钩子"""
        for hook in cls._hooks.get(phase, []):
            try:
                hook()
            except Exception as e:
                logger.error(f"Hook {hook.__name__} failed in {phase}: {str(e)}")

    @classmethod
    def start_all(cls):
        """启动所有组件"""
        cls.run_hooks('before_start')

        for comp in cls._components:
            logger.info(f"Starting component: {type(comp).__name__}")
            comp.start()

        cls.run_hooks('after_start')

    @classmethod
    def stop_all(cls):
        """停止所有组件"""
        cls.run_hooks('before_shutdown')

        for comp in reversed(cls._components):
            logger.info(f"Stopping component: {type(comp).__name__}")
            try:
                comp.stop()
            except Exception as e:
                logger.error(f"Error stopping {type(comp).__name__}: {str(e)}")

        cls.run_hooks('after_shutdown')

    @classmethod
    def wait_for_shutdown(cls):
        """等待关闭信号"""
        def _signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            cls._stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        logger.info("Application running, waiting for shutdown signal...")
        cls._stop_event.wait()
        cls.stop_all()