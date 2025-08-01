# pyinfra/app.py
from typing import Optional
from config.loader import load_config, merge_env_vars
from components.logging.factory import create_and_register_logging
from core.lifecycle import LifecycleManager
from core.container import Container

class PyAPP:
    def __init__(self, config_path: Optional[str] = None, app_name: str = "pyinfra-app"):
        self.app_name = app_name
        self.config_data = {}
        self._initialized = False

        if config_path:
            self.config_data = load_config(config_path)
            self.config_data = merge_env_vars(self.config_data)

    def initialize(self):
        """初始化应用基础设施"""
        if self._initialized:
            return

        self._init_logging()
        self._import_hooks()
        self._init_components()
        self._initialized = True

    def _init_logging(self):
        """初始化日志组件"""
        logging_component = create_and_register_logging(
            self.config_data,
            self.app_name
        )
        logging_component.start()

    def _import_hooks(self):
        """导入所有钩子模块"""
        import hooks

    def _init_components(self):
        """初始化其他组件"""
        pass

    def run(self):
        """启动应用"""
        if not self._initialized:
            self.initialize()

        LifecycleManager.start_all()
        LifecycleManager.wait_for_shutdown()

    def stop(self):
        """手动停止应用"""
        LifecycleManager.stop_all()

    def get_component(self, name: str):
        """获取组件实例"""
        return Container.resolve(name)