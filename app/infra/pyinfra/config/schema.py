from pydantic import BaseModel, Field
from typing import Optional

from components.logging.schema import LoggingConfig


# class LoggingConfig(BaseModel):
#     level: str = Field(default="INFO", description="Logging level")
#     format: str = Field(default="[%(asctime)s] [%(levelname)s] %(message)s")

class MySQLConfig(BaseModel):
    host: str
    port: int = 3306
    user: str
    password: str
    database: str

class RedisConfig(BaseModel):
    host: str
    port: int = 6379
    db: int = 0

class AppConfig(BaseModel):
    logging: Optional[LoggingConfig] = LoggingConfig()
    mysql: Optional[MySQLConfig] = None
    redis: Optional[RedisConfig] = None
    # 可扩展：grpcserver, httpserver, mq, tracing 等