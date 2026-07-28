from __future__ import annotations

from enum import StrEnum
import os

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


class MinioCfg(StrictConfigModel):
    endpoint: str = "127.0.0.1:9000"
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False
    bucket: str = "research-report"


class ModelProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI_COMPATIBLE_PDF = "openai_compatible_pdf"


class StructuredOutputMode(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"


class ModelEndpointCfg(StrictConfigModel):
    provider: ModelProvider
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3-14b-q4_k_m"
    api_key: str = ""
    api_key_env: str = ""
    timeout_seconds: float = Field(default=900, gt=0)
    temperature: float = Field(default=0, ge=0, le=2)
    maximum_output_tokens: int = Field(default=16384, ge=256)
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA

    @property
    def resolved_api_key(self) -> str:
        return os.getenv(self.api_key_env, "") if self.api_key_env else self.api_key


class LLMCfg(StrictConfigModel):
    extraction: ModelEndpointCfg = Field(
        default_factory=lambda: ModelEndpointCfg(
            provider=ModelProvider.OPENAI_COMPATIBLE_PDF,
            structured_output_mode=StructuredOutputMode.JSON_OBJECT,
        )
    )
    agent: ModelEndpointCfg = Field(
        default_factory=lambda: ModelEndpointCfg(provider=ModelProvider.OLLAMA)
    )

    @model_validator(mode="after")
    def validate_capability_boundaries(self) -> "LLMCfg":
        if self.extraction.provider != ModelProvider.OPENAI_COMPATIBLE_PDF:
            raise ValueError(
                "llm.extraction must use a PDF-capable provider"
            )
        if self.agent.provider == ModelProvider.OPENAI_COMPATIBLE_PDF:
            raise ValueError(
                "llm.agent must use ollama or openai_compatible"
            )
        return self


class KnowledgeEngineCfg(StrictConfigModel):
    pipeline_version: str = "atlas-kg-v1"
    research_report_source: str = "eastmoney"
    poll_batch_size: int = Field(default=20, ge=1, le=1000)
    llm_concurrency: int = Field(default=1, ge=1)
    maximum_total_attempts: int = Field(default=3, ge=1, le=10)
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
    minio: MinioCfg = Field(default_factory=MinioCfg)
    llm: LLMCfg = Field(default_factory=LLMCfg)
    taxonomy: TaxonomyCfg = Field(default_factory=TaxonomyCfg)
    engine: EngineCfg = Field(default_factory=EngineCfg)
