# pyinfra/core/lifecycle.py
import signal
import threading
import logging
import atexit
import sys
from typing import List, Callable, Dict
from core.component import BaseComponent

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
    _shutdown_called = False

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
            comp.start()
            logger.info(f"Started component: {type(comp).__name__}")

        cls.run_hooks('after_start')

    @classmethod
    def stop_all(cls):
        """停止所有组件"""
        if cls._shutdown_called:
            return

        cls._shutdown_called = True
        logger.info("Initiating shutdown sequence...")

        cls.run_hooks('before_shutdown')

        for comp in reversed(cls._components):
            logger.info(f"Stopping component: {type(comp).__name__}")
            try:
                comp.stop()
            except Exception as e:
                logger.error(f"Error stopping {type(comp).__name__}: {str(e)}")

        cls.run_hooks('after_shutdown')
        logger.info("Shutdown sequence completed")

    @classmethod
    def _signal_handler(cls, sig, frame):
        """信号处理器"""
        logger.info(f"Received signal {sig}, shutting down...")
        cls._stop_event.set()

    @classmethod
    def _atexit_handler(cls):
        """程序退出时的清理处理器"""
        logger.info("Application exiting, performing cleanup...")
        cls.stop_all()

    @classmethod
    def setup_signal_handlers(cls):
        """设置信号处理器"""
        # 注册 atexit 处理器（处理所有退出场景）
        atexit.register(cls._atexit_handler)

        # 注册信号处理器
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, cls._signal_handler)

        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, cls._signal_handler)

        # Windows 特殊处理
        if sys.platform == "win32":
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, cls._signal_handler)

    @classmethod
    def wait_for_shutdown(cls):
        """等待关闭信号"""
        cls.setup_signal_handlers()

        logger.info("Application running, waiting for shutdown signal...")

        try:
            cls._stop_event.wait()
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt")
        finally:
            cls.stop_all()