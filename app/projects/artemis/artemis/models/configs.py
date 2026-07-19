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


class TaskEngineCfg(BaseModel):
    """Task engine tunables."""
    worker_task_timeout: int = 180
    amazing_data_cache_dir: str = "../cache/artemis"


class PartitionRuleCfg(BaseModel):
    """A single partition rule: match conditions + granularity."""
    match: Dict[str, str] = Field(default_factory=dict)
    granularity: str = "yearly"  # "yearly" | "monthly"


class CacheEngineCfg(BaseModel):
    """Cache engine configuration."""
    enabled: bool = False
    cache_dir: str = "./cache/artemis"
    max_cache_size: str = "5GB"
    eviction_policy: str = "lru"
    eviction_check_interval: int = 100
    partition_rules: list[PartitionRuleCfg] = Field(default_factory=list)


class FeaturePlatformCfg(BaseModel):
    """Feature Platform manifest and execution settings."""

    enabled: bool = False
    manifest_root: str = "./config/feature_catalog"
    max_parallel_features: int = Field(default=2, gt=0)
    write_batch_size: int = Field(default=5000, gt=0, le=5000)
    heartbeat_interval_seconds: int = Field(default=15, gt=0)
    stale_run_timeout_seconds: int = Field(default=300, gt=0)
    plugin_timeout_seconds: int = Field(default=1800, gt=0)


class EngineCfg(BaseModel):
    """Top-level engine configuration."""
    task_engine: TaskEngineCfg = Field(default_factory=TaskEngineCfg)
    cache_engine: CacheEngineCfg = Field(default_factory=CacheEngineCfg)
    feature_platform: FeaturePlatformCfg = Field(default_factory=FeaturePlatformCfg)


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


class MinioCfg(BaseModel):
    """MinIO object storage connection config.

    Used by research-report (and future) tasks to sink downloaded PDFs.
    `endpoint` is host:port. When endpoint is empty, MinioClient degrades to
    NoopMinioClient so the task can be developed before real MinIO is up.
    """
    endpoint: Optional[str] = None
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False


class MinioBusinessCfg(BaseModel):
    """MinIO business layout for research-report storage.

    Research reports are split into a stock folder and an industry folder.
    Under the stock folder, each symbol gets its own subfolder. Object key
    convention: "{stock_prefix}/{symbol}/{publish_date}_{title}.pdf".
    """
    bucket: str = "research-report"
    stock_prefix: str = "stock"
    industry_prefix: str = "industry"


class DataOption(BaseModel):
    """单个选项（value + 展示 label）。"""
    value: str
    label: str


class AdjustRule(BaseModel):
    """asset_type → 可用 adjust 列表。"""
    asset_type: str
    options: list[DataOption]


class DataOptionsCfg(BaseModel):
    """Workbench 数据维度选项配置，顶层独立于 engine。"""
    asset_types: list[DataOption] = Field(default_factory=list)
    markets: list[DataOption] = Field(default_factory=list)
    periods: list[DataOption] = Field(default_factory=list)
    adjust_rules: list[AdjustRule] = Field(default_factory=list)


class Config(BaseModel):
    env: str = 'development'
    server: ServerCfg = Field(default_factory=ServerCfg)
    logging: LoggingCfg = Field(default_factory=LoggingCfg)
    telemetry: TelemetryCfg = Field(default_factory=TelemetryCfg)
    http_client: HttpClientCfg = Field(default_factory=HttpClientCfg)

    # SDK configurations
    sdk: Dict[str, Any] = Field(default_factory=dict)

    # task engine
    engine: EngineCfg = Field(default_factory=EngineCfg)

    # workbench data dimension options (top-level, not under engine)
    data_options: DataOptionsCfg = Field(default_factory=DataOptionsCfg)

    # new preferred config
    dept_services: DeptServicesCfg = Field(default_factory=DeptServicesCfg)

    # MinIO object storage (research-report PDFs sink here)
    minio: MinioCfg = Field(default_factory=MinioCfg)
    minio_business: MinioBusinessCfg = Field(default_factory=MinioBusinessCfg)

    # legacy (kept for compatibility; will be mapped to dept_services.cronjob when present)
    callback: CallbackCfg = Field(default_factory=CallbackCfg)

    task_defaults: Dict[str, Any] = Field(default_factory=dict)
    output_defaults: Dict[str, Any] = Field(default_factory=dict)
