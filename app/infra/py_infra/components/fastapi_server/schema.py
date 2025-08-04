# components/fastapi_server/schema.py
from core.component import ComponentConfig
from typing import Optional, List

class FastAPIServerConfig(ComponentConfig):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    workers: int = 1
    app_name: str = "FastAPI App"
    title: Optional[str] = None
    description: Optional[str] = None
    version: str = "1.0.0"
    docs_url: Optional[str] = "/docs"
    redoc_url: Optional[str] = "/redoc"
    openapi_url: Optional[str] = "/openapi.json"
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]
    access_log: bool = True