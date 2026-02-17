from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ServerCfg(BaseModel):
    host: str = '0.0.0.0'
    port: int = 18000
    access_log: bool = False


class LoggingFileCfg(BaseModel):
    dir: str = './logs'
    filename: str = 'artemis'


class LoggingRotateCfg(BaseModel):
    enabled: bool = True
    rotate_interval: str = '1d'
    max_age: str = '72h'
    cleanup_enabled: bool = True


class LoggingCfg(BaseModel):
    enabled: bool = True
    level: str = 'INFO'
    format: str = 'json'
    output: str = 'file'
    include_caller: bool = True
    file_config: LoggingFileCfg = Field(default_factory=LoggingFileCfg)
    rotate_config: LoggingRotateCfg = Field(default_factory=LoggingRotateCfg)


class TelemetryOtlpCfg(BaseModel):
    protocol: str = 'http'
    endpoint: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = 5000


class TelemetryCfg(BaseModel):
    enabled: bool = True
    service_name: str = 'artemis'
    sampling: str = 'always'
    otlp: TelemetryOtlpCfg = Field(default_factory=TelemetryOtlpCfg)


class HttpClientCfg(BaseModel):
    timeout_seconds: int = 5
    verify_ssl: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)


class CallbackCfg(BaseModel):
    """Legacy callback override config (deprecated).

    Use Config.dept_services.cronjob instead.
    """

    host: Optional[str] = None
    port: Optional[int] = None


class ServiceEndpointCfg(BaseModel):
    """Generic service endpoint config.

    Keep it minimal for now (host/port), but we can extend later (scheme/base_path/headers, etc.).
    """

    host: Optional[str] = None
    port: Optional[int] = None


class DeptServicesCfg(BaseModel):
    """Dependent services configuration.

    - cronjob: where Artemis reports progress/results
    - phoenixA: another dependent project service

    We keep both explicit fields for discoverability, and also allow
    arbitrary future services via `extras`.
    """

    cronjob: ServiceEndpointCfg = Field(default_factory=ServiceEndpointCfg)
    phoenixA: ServiceEndpointCfg = Field(default_factory=ServiceEndpointCfg)
    extras: Dict[str, ServiceEndpointCfg] = Field(default_factory=dict)


class Config(BaseModel):
    env: str = 'development'
    server: ServerCfg = Field(default_factory=ServerCfg)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)
    telemetry: TelemetryCfg = Field(default_factory=TelemetryCfg)
    http_client: HttpClientCfg = Field(default_factory=HttpClientCfg)

    # SDK configurations
    sdk: Dict[str, Any] = Field(default_factory=dict)

    # new preferred config
    dept_services: DeptServicesCfg = Field(default_factory=DeptServicesCfg)

    # legacy (kept for compatibility; will be mapped to dept_services.cronjob when present)
    callback: CallbackCfg = Field(default_factory=CallbackCfg)

    task_defaults: Dict[str, Any] = Field(default_factory=dict)
    output_defaults: Dict[str, Any] = Field(default_factory=dict)
