from __future__ import annotations

from enum import StrEnum
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerCfg(StrictConfigModel):
    host: str = "0.0.0.0"
    port: int = Field(default=18400, ge=1, le=65535)
    access_log: bool = False


class HttpClientCfg(StrictConfigModel):
    timeout_seconds: float = Field(default=30, gt=0)
    verify_ssl: bool = True
    headers: dict[str, str] = Field(default_factory=dict)


class ServiceEndpointCfg(StrictConfigModel):
    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)
    scheme: str = "http"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


class DeptServicesCfg(StrictConfigModel):
    phoenixA: ServiceEndpointCfg = Field(
        default_factory=lambda: ServiceEndpointCfg(port=18085)
    )
    cronjob: ServiceEndpointCfg = Field(
        default_factory=lambda: ServiceEndpointCfg(port=18090)
    )
    # Optional read-only report catalog used only by development sampling.
    # Run/result persistence always uses phoenixA above.
    sampling_catalog_phoenixA: ServiceEndpointCfg | None = None


class MinIOEndpointCfg(StrictConfigModel):
    endpoint: str
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False
    # Optional path to another service's YAML config. ConfigManager imports
    # only its `minio` connection fields, so credentials are not duplicated.
    credential_source: str | None = None
    # Documents a security boundary and enables fail-closed validation when a
    # development environment points sampling at production data. The actual
    # MinIO identity must also have a server-side read-only policy.
    read_only: bool = False


class MinIOBucketCfg(StrictConfigModel):
    """Logical bucket reference: resolves to (endpoint, physical_bucket)."""
    endpoint: str
    name: str


class MinIOCfg(StrictConfigModel):
    """Multi-endpoint MinIO registry. Business code references buckets by logical name."""
    endpoints: dict[str, MinIOEndpointCfg] = Field(default_factory=dict)
    buckets: dict[str, MinIOBucketCfg] = Field(default_factory=dict)
    # logical bucket name used as the source PDF store
    source_bucket: str = "source"
    # Optional, development-only source for field-discovery sampling. This can
    # point at a production bucket without changing the normal extraction source.
    sampling_source_bucket: str | None = None

    def resolve_bucket(self, logical_name: str) -> tuple[MinIOEndpointCfg, str]:
        bucket = self.buckets.get(logical_name)
        if bucket is None:
            raise ValueError(f"minio bucket '{logical_name}' is not configured")
        endpoint = self.endpoints.get(bucket.endpoint)
        if endpoint is None:
            raise ValueError(
                f"minio bucket '{logical_name}' references unknown endpoint '{bucket.endpoint}'"
            )
        return endpoint, bucket.name

    def resolve_sampling_bucket(self) -> tuple[MinIOEndpointCfg, str]:
        return self.resolve_bucket(self.sampling_source_bucket or self.source_bucket)


class ModelProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI_COMPATIBLE_PDF = "openai_compatible_pdf"
    ZHIPU_TEXT = "zhipu_text"
    OPENROUTER = "openrouter"
    NVIDIA_NIM = "nvidia_nim"


# Providers whose chat payload uses OpenRouter's `reasoning: {enabled: true}`
# shape instead of Zhipu's `thinking: {type: enabled|disabled}` shape.
REASONING_PROVIDERS: frozenset[ModelProvider] = frozenset({ModelProvider.OPENROUTER})


class StructuredOutputMode(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


class ThinkingMode(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class LLMCapabilitiesCfg(StrictConfigModel):
    """Declares what a model can do; roles bind only to models with matching capabilities."""
    structured_output: bool = False
    pdf_direct: bool = False
    text_extraction: bool = False
    thinking: bool = False
    # Whether the chat endpoint accepts OpenAI's response_format parameter.
    # Free-tier OpenRouter models often reject it even when they emit valid JSON.
    response_format_api: bool = True


class LLMAPIKeyCfg(StrictConfigModel):
    """One API key in a model's key pool, with its own per-key concurrency cap."""
    key: str = ""
    key_env: str = ""
    max_concurrency: int = Field(default=2, ge=1)

    @property
    def resolved_key(self) -> str:
        if self.key_env:
            return os.getenv(self.key_env, self.key)
        return self.key


class LLMModelCfg(StrictConfigModel):
    """A named model endpoint. Business params (temperature/thinking) are per-call, not here."""
    provider: ModelProvider
    base_url: str
    model: str
    capabilities: LLMCapabilitiesCfg
    api_keys: list[LLMAPIKeyCfg] = Field(min_length=1)
    timeout_seconds: float = Field(default=900, gt=0)
    maximum_output_tokens: int = Field(default=16384, ge=256)
    # Ollama otherwise silently selects a 4096-token context on GPUs below
    # 24 GiB, even when the model itself supports a much larger window.
    context_window_tokens: int = Field(default=4096, ge=2048)
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA
    # model-level business defaults; overridable per call
    temperature: float = Field(default=0, ge=0, le=2)
    thinking_mode: ThinkingMode | None = None
    # Provider-specific, OpenAI-compatible request extensions. This keeps new
    # free endpoints pluggable without adding provider branches for every
    # chat-template flag. Core fields such as model/messages cannot be replaced.
    extra_body: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_extra_body(self) -> "LLMModelCfg":
        protected = {"model", "messages", "stream"} & self.extra_body.keys()
        if protected:
            raise ValueError(
                "llm model extra_body cannot override protected fields: "
                f"{sorted(protected)}"
            )
        return self


class LLMHarnessStrategy(StrEnum):
    PRIORITY_FAILOVER = "priority_failover"
    BALANCED_FAILOVER = "balanced_failover"


class LLMHarnessCfg(StrictConfigModel):
    """Pluggable model chain for an expensive or failure-prone workflow stage."""

    models: list[str] = Field(min_length=1)
    strategy: LLMHarnessStrategy = LLMHarnessStrategy.PRIORITY_FAILOVER
    failure_threshold: int = Field(default=2, ge=1, le=20)
    cooldown_seconds: float = Field(default=120, ge=0, le=3600)


class LLMCfg(StrictConfigModel):
    """Model registry + role bindings. Roles (extraction/agent) reference model names."""
    roles: dict[str, str] = Field(default_factory=dict)
    models: dict[str, LLMModelCfg] = Field(default_factory=dict)
    harnesses: dict[str, LLMHarnessCfg] = Field(default_factory=dict)

    def model_for_role(self, role: str) -> tuple[str, LLMModelCfg]:
        name = self.roles.get(role)
        if name is None:
            raise ValueError(f"LLM role '{role}' is not bound to any model")
        model = self.models.get(name)
        if model is None:
            raise ValueError(f"LLM role '{role}' references unknown model '{name}'")
        return name, model

    def harness_for_stage(self, stage: str) -> LLMHarnessCfg | None:
        return self.harnesses.get(stage)

    @model_validator(mode="after")
    def validate_capability_boundaries(self) -> "LLMCfg":
        for harness_name, harness in self.harnesses.items():
            missing = [name for name in harness.models if name not in self.models]
            if missing:
                raise ValueError(
                    f"llm harness '{harness_name}' references unknown models: {missing}"
                )
            if harness_name in {"sampling_extraction", "sampling_review"}:
                unusable = [
                    name
                    for name in harness.models
                    if not self.models[name].capabilities.text_extraction
                ]
                if unusable:
                    raise ValueError(
                        f"llm harness '{harness_name}' requires text-extraction models: "
                        f"{unusable}"
                    )
        extraction_name = self.roles.get("extraction")
        if extraction_name is not None:
            extraction = self.models.get(extraction_name)
            if extraction is not None and not (
                extraction.capabilities.pdf_direct or extraction.capabilities.text_extraction
            ):
                raise ValueError(
                    "llm role 'extraction' must bind to a PDF-capable or text-extracting model"
                )
        agent_name = self.roles.get("agent")
        if agent_name is not None:
            agent = self.models.get(agent_name)
            if agent is not None and not agent.capabilities.structured_output:
                raise ValueError(
                    "llm role 'agent' must bind to a structured-output-capable model"
                )
        return self


class KnowledgeEngineCfg(StrictConfigModel):
    pipeline_version: str = "atlas-kg-v1"
    research_report_source: str = "eastmoney"
    poll_batch_size: int = Field(default=20, ge=1, le=1000)
    llm_concurrency: int = Field(default=1, ge=1)
    maximum_total_attempts: int = Field(default=3, ge=1, le=10)
    sampling_maximum_chunks: int = Field(default=3, ge=1, le=12)
    sampling_chunk_output_tokens: int = Field(default=1536, ge=512, le=8192)
    sampling_merge_output_tokens: int = Field(default=2560, ge=512, le=8192)
    sampling_prompt_reserve_tokens: int = Field(default=2200, ge=512, le=8192)
    sampling_field_review_batch_size: int = Field(default=4, ge=1, le=10)
    sampling_field_review_output_tokens: int = Field(default=2800, ge=512, le=8192)
    sampling_minimum_success_ratio: float = Field(default=0.6, ge=0, le=1)
    sampling_enable_semantic_summarizer: bool = False
    # Shared Document Harness. Sampling and production text-model extraction
    # both use this quality-gated parser chain; only Sampling APIs are dev-only.
    document_layout_sidecar_url: str | None = None
    document_local_ocr_enabled: bool = False
    document_local_ocr_dpi: int = Field(default=160, ge=96, le=240)
    document_local_ocr_maximum_pages: int = Field(default=12, ge=1, le=60)
    # Ephemeral live-event journal used by the development Sampling UI.
    harness_event_buffer_size: int = Field(default=400, ge=20, le=5000)
    harness_event_maximum_runs: int = Field(default=20, ge=1, le=200)
    # Sampling is a development-time schema-discovery workflow. Production
    # consumes approved field catalogs and must not expose sampling endpoints.
    sampling_enabled: bool = True
    semantic_config_path: str = "config/semantic/atlas-semantic-v0001.yaml"
    prompt_mapping_path: str = "config/report_prompt_mapping.yaml"


class TaxonomySchemeCfg(StrictConfigModel):
    source: str
    taxonomy: str
    market: str = "zh_a"


class TaxonomyCfg(StrictConfigModel):
    canonical_seed_scheme: str = "SW2021"
    schemes: dict[str, TaxonomySchemeCfg] = Field(default_factory=dict)


class EngineCfg(StrictConfigModel):
    knowledge_engine: KnowledgeEngineCfg = Field(default_factory=KnowledgeEngineCfg)


class Config(StrictConfigModel):
    env: str = "development"
    server: ServerCfg = Field(default_factory=ServerCfg)
    http_client: HttpClientCfg = Field(default_factory=HttpClientCfg)
    dept_services: DeptServicesCfg = Field(default_factory=DeptServicesCfg)
    minio: MinIOCfg = Field(default_factory=MinIOCfg)
    llm: LLMCfg = Field(default_factory=LLMCfg)
    taxonomy: TaxonomyCfg = Field(default_factory=TaxonomyCfg)
    engine: EngineCfg = Field(default_factory=EngineCfg)

    @model_validator(mode="after")
    def validate_environment_boundaries(self) -> "Config":
        sampling_enabled = self.engine.knowledge_engine.sampling_enabled
        if self.env == "production" and sampling_enabled:
            raise ValueError("sampling must be disabled in the production environment")
        sampling_bucket = self.minio.sampling_source_bucket
        if sampling_enabled and sampling_bucket:
            endpoint, _ = self.minio.resolve_bucket(sampling_bucket)
            if not endpoint.read_only:
                raise ValueError(
                    "the dedicated sampling_source_bucket must use a read_only MinIO endpoint"
                )
        return self
