from atlas.application import build_runtime
from atlas.core.clients import ZhipuTextPDFClient
from atlas.core.config_manager import ConfigManager
from atlas.models import (
    LLMCfg,
    ModelEndpointCfg,
    ModelProvider,
    StructuredOutputMode,
    ThinkingMode,
)
import pytest


def test_runtime_wires_ollama_agents_without_network_calls():
    config = ConfigManager().init_config(path="config/config.yaml", env="test")
    runtime = build_runtime(config)
    assert runtime.config.llm.agent.provider == "ollama"
    assert runtime.query_orchestrator is not None
    assert runtime.crosswalk_service is not None
    assert runtime.discovery_orchestrator is not None
    assert runtime.extraction_orchestrator.extractor.llm.model_id == (
        config.llm.extraction.model
    )


def test_model_configuration_rejects_ollama_as_direct_pdf_provider():
    with pytest.raises(ValueError, match="PDF-capable"):
        LLMCfg(
            extraction=ModelEndpointCfg(
                provider=ModelProvider.OLLAMA,
            ),
            agent=ModelEndpointCfg(
                provider=ModelProvider.OLLAMA,
            ),
        )


def test_zhipu_config_wires_extraction_agents_and_sample_storage():
    config = ConfigManager().init_config(
        path="config/config.yaml", env="test"
    )
    config.minio.bucket = "chaos-dev"
    config.minio.sample_bucket = "atlas-dev"
    config.llm = LLMCfg(
        extraction=ModelEndpointCfg(
            provider=ModelProvider.ZHIPU_TEXT,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4.7-flash",
            api_key="test-key",
            structured_output_mode=StructuredOutputMode.JSON_OBJECT,
            thinking_mode=ThinkingMode.DISABLED,
        ),
        agent=ModelEndpointCfg(
            provider=ModelProvider.OPENAI_COMPATIBLE,
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4.7-flash",
            api_key="test-key",
            structured_output_mode=StructuredOutputMode.JSON_OBJECT,
            thinking_mode=ThinkingMode.DISABLED,
        ),
    )
    runtime = build_runtime(config)
    assert config.minio.bucket == "chaos-dev"
    assert config.minio.sample_bucket == "atlas-dev"
    assert config.llm.extraction.model == "glm-4.7-flash"
    assert config.llm.agent.model == "glm-4.7-flash"
    assert isinstance(
        runtime.extraction_orchestrator.extractor.llm,
        ZhipuTextPDFClient,
    )
    assert runtime.extraction_orchestrator.extractor.llm.input_mode == "TEXT_EXTRACTED"
    assert runtime.discovery_orchestrator.sample_store.bucket == "atlas-dev"
