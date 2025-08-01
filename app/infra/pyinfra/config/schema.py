# app/infra/pyinfra/config/schema.py
from pydantic import BaseModel, Field
from typing import Optional

from components.fastapi_server import FastAPIServerConfig
from components.logging.schema import LoggingConfig

class AppConfig(BaseModel):
    # 移除默认值，这些组件应该在运行时根据配置创建
    logging: Optional[LoggingConfig] = None
    fastapi_server: Optional[FastAPIServerConfig] = None