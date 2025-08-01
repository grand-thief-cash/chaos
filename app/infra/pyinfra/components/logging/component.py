# components/logging/component.py
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional
from components.logging.schema import LoggingConfig  # 使用统一的配置类
from components.logging.context_filter import LoggingContextFilter
from core.component import BaseComponent


class LoggingComponent(BaseComponent):
    def __init__(self, config: LoggingConfig):
        super().__init__(config)
        self.logger: Optional[logging.Logger] = None
        self._default_level = logging.INFO

    def start(self):
        """初始化日志系统"""
        Path(self.config.log_dir).mkdir(parents=True, exist_ok=True)

        log_file = Path(self.config.log_dir) / f"{self.config.app_name}.log"
        handler = TimedRotatingFileHandler(
            filename=log_file,
            when=self.config.when,
            interval=self.config.interval,
            backupCount=self.config.backup_count,
            encoding='utf-8',
            utc=True,
        )

        formatter = logging.Formatter(self.config.format)
        handler.setFormatter(formatter)
        handler.addFilter(LoggingContextFilter())

        # 配置根日志
        self.logger = logging.getLogger()
        self._default_level = getattr(logging, self.config.level.upper(), logging.INFO)
        self.logger.setLevel(self._default_level)

        # 移除所有现有处理器
        for h in self.logger.handlers[:]:
            self.logger.removeHandler(h)

        self.logger.addHandler(handler)
        logging.info("Logging system initialized")

    def stop(self):
        """关闭日志系统"""
        if self.logger:
            for handler in self.logger.handlers:
                handler.close()
                self.logger.removeHandler(handler)
            logging.info("Logging system shutdown")