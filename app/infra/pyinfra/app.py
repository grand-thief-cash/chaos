# app/infra/pyinfra/app.py
from config.loader import load_config, merge_env_vars
from config.schema import AppConfig
from core.lifecycle import LifecycleManager
from components.logging.factory import create_and_register_logging
from components.fastapi_server.factory import create_and_register_fastapi_server
import logging

class PyAPP:
    def __init__(self, config_path: str, app_name: str):
        self.config_path = config_path
        self.app_name = app_name
        self.config_dict = {}
        self.config = None

    def initialize(self):
        """初始化应用"""
        # 加载配置
        self.config_dict = load_config(self.config_path)
        self.config_dict = merge_env_vars(self.config_dict)

        # 先创建和注册组件（不进行配置验证）
        create_and_register_logging(self.config_dict, self.app_name)
        create_and_register_fastapi_server(self.config_dict, self.app_name)

        # 组件初始化后再获取logger
        logger = logging.getLogger(__name__)
        # logger.info("Application infrastructure initialized")

    def run(self):
        """运行应用"""
        # 启动所有组件
        LifecycleManager.start_all()

        # 等待关闭信号
        LifecycleManager.wait_for_shutdown()

    def stop(self):
        """停止应用"""
        LifecycleManager.stop_all()