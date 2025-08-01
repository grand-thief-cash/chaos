# app/infra/pyinfra/components/logging/component.py
import logging
import logging.handlers
import os
from core.component import BaseComponent
from components.logging.schema import LoggingConfig
from components.logging.context_filter import LoggingContextFilter
from components.logging.context import set_trace_id
import uuid

logger = logging.getLogger(__name__)

class LoggingComponent(BaseComponent):
    def __init__(self, config: LoggingConfig):
        super().__init__(config)
        self.config: LoggingConfig = config

    def start(self):
        """初始化日志系统"""
        # 设置初始 TraceID
        set_trace_id(str(uuid.uuid4()))

        # 创建日志目录
        if not os.path.exists(self.config.log_dir):
            os.makedirs(self.config.log_dir)

        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.level.upper()))

        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 创建文件处理器
        log_file = os.path.join(self.config.log_dir, f"{self.config.app_name}.log")
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when=self.config.when,
            interval=self.config.interval,
            backupCount=self.config.backup_count,
            encoding='utf-8',
        )
        file_handler.suffix = self.config.suffix   # 设置日志文件后缀格式


        # 创建控制台处理器
        # console_handler = logging.StreamHandler()

        # 设置格式化器
        formatter = logging.Formatter(self.config.format)
        file_handler.setFormatter(formatter)
        # console_handler.setFormatter(formatter)

        # 添加上下文过滤器
        context_filter = LoggingContextFilter()
        file_handler.addFilter(context_filter)
        # console_handler.addFilter(context_filter)

        # 添加处理器到根日志记录器
        root_logger.addHandler(file_handler)
        # root_logger.addHandler(console_handler)

        super().start()
        logger.info("Logging system initialized")

    def stop(self):
        """停止日志系统"""
        # 关闭所有日志处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        super().stop()
        logger.info("Logging system stopped")