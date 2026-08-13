from atlas.application import build_runtime
from atlas.core.clients import ZhipuTextPDFClient
from atlas.core.config_manager import ConfigManager
from atlas.models import (
    LLMAPIKeyCfg,
    LLMCapabilitiesCfg,
    LLMCfg,
    LLMModelCfg,
    MinIOBucketCfg,
    MinIOCfg,
    MinIOEndpointCfg,
    ModelProvider,
    StructuredOutputMode,
    ThinkingMode,
)
import pytest


def test_runtime_wires_ollama_agents_without_network_calls():
    config = ConfigManager().init_config(path="config/config.yaml", env="test")
    runtime = build_runtime(config)
    agent_name, agent_model = config.llm.model_for_role("agent")
    assert agent_model.provider == "ollama"
    assert runtime.query_orchestrator is not None
    assert runtime.crosswalk_service is not None
    assert runtime.discovery_orchestrator is not None
    _extraction_name, extraction_model = config.llm.model_for_role("extraction")
    assert (
        runtime.extraction_orchestrator.extractor.llm.model_id
        == extraction_model.model
    )


def test_model_configuration_rejects_non_pdf_extraction_model():
    with pytest.raises(ValueError, match="PDF-capable"):
        LLMCfg(
            roles={"extraction": "ollama-model", "agent": "ollama-model"},
            models={
                "ollama-model": LLMModelCfg(
                    provider=ModelProvider.OLLAMA,
                    base_url="http://localhost:11434/v1",
                    model="qwen3:14b",
                    capabilities=LLMCapabilitiesCfg(structured_output=True),
                    api_keys=[LLMAPIKeyCfg(key="k")],
                ),
            },
        )


def test_zhipu_config_wires_extraction_and_shared_key_pool():
    config = ConfigManager().init_config(path="config/config.yaml", env="test")
    config.minio = MinIOCfg(
        endpoints={
            "primary": MinIOEndpointCfg(
                endpoint="minio:9000", access_key="a", secret_key="s"
            )
        },
        buckets={"source": MinIOBucketCfg(endpoint="primary", name="chaos-dev")},
        source_bucket="source",
    )
    config.llm = LLMCfg(
        roles={"extraction": "glm", "agent": "glm"},
        models={
            "glm": LLMModelCfg(
                provider=ModelProvider.ZHIPU_TEXT,
                base_url="https://open.bigmodel.cn/api/paas/v4",
                model="glm-4.7-flash",
                capabilities=LLMCapabilitiesCfg(
                    structured_output=True, text_extraction=True
                ),
                api_keys=[LLMAPIKeyCfg(key="test-key", max_concurrency=2)],
                structured_output_mode=StructuredOutputMode.JSON_OBJECT,
                thinking_mode=ThinkingMode.DISABLED,
                temperature=0.1,
            ),
        },
    )
    runtime = build_runtime(config)
    _name, extraction_model = config.llm.model_for_role("extraction")
    assert extraction_model.model == "glm-4.7-flash"
    assert isinstance(
        runtime.extraction_orchestrator.extractor.llm, ZhipuTextPDFClient
    )
    assert (
        runtime.extraction_orchestrator.extractor.llm.input_mode == "TEXT_EXTRACTED"
    )
    # extraction and agent bind the same model -> one shared KeyPool
    assert (
        runtime.extraction_orchestrator.extractor.llm.key_pool
        is runtime.discovery_orchestrator.agent_client.key_pool
    )
    # cronjob callback + sample task registry are wired
    assert runtime.cronjob_callback is not None
    assert runtime.sample_task_registry is not None
