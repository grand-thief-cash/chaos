from atlas.application import build_runtime
from atlas.core.config_manager import ConfigManager
from atlas.models import LLMCfg, ModelEndpointCfg, ModelProvider
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
