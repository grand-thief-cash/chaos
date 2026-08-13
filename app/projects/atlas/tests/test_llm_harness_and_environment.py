from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from atlas.api.http_gateway.routes import create_app
from atlas.core.config_manager import ConfigManager
from atlas.core.llm import FailoverLLMClient
from atlas.models import Config, LLMHarnessCfg, LLMHarnessStrategy


class _Client:
    input_mode = "TEXT_EXTRACTED"

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = 0

    async def complete_text(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response or "{}"


class _RoutingClient(_Client):
    model_id = "openrouter/free"

    def consume_response_model(self):
        return "openai/gpt-oss-120b:free"


@pytest.mark.asyncio
async def test_harness_fails_over_and_opens_provider_circuit():
    primary = _Client(error=RuntimeError("free endpoint unavailable"))
    fallback = _Client(response='{"ok":true}')
    now = [100.0]
    harness = FailoverLLMClient(
        [("free", primary), ("local", fallback)],
        LLMHarnessCfg(
            models=["free", "local"],
            strategy=LLMHarnessStrategy.PRIORITY_FAILOVER,
            failure_threshold=1,
            cooldown_seconds=60,
        ),
        clock=lambda: now[0],
    )

    assert await harness.complete_text(prompt="p", extracted_text="t", filename="a") == '{"ok":true}'
    assert harness.status()["free"]["circuit_open"] is True
    assert await harness.complete_text(prompt="p", extracted_text="t", filename="b") == '{"ok":true}'
    assert primary.calls == 1
    assert fallback.calls == 2
    assert harness.consume_request_providers() == ["local", "local"]
    assert harness.consume_request_providers() == []


@pytest.mark.asyncio
async def test_harness_fails_over_on_business_validation_error():
    wrong_shape = _Client(response='{"master_catalog":[]}')
    valid = _Client(response='{"fields":[]}')
    harness = FailoverLLMClient(
        [("wrong", wrong_shape), ("valid", valid)],
        LLMHarnessCfg(
            models=["wrong", "valid"],
            strategy=LLMHarnessStrategy.PRIORITY_FAILOVER,
            failure_threshold=1,
        ),
    )

    def validator(raw: str):
        if '"fields"' not in raw:
            raise ValueError("wrong catalog schema")

    result = await harness.complete_text_validated(
        prompt="p", extracted_text="t", filename="catalog.json", validator=validator
    )
    assert result == '{"fields":[]}'
    assert wrong_shape.calls == 1 and valid.calls == 1
    assert harness.status()["wrong"]["circuit_open"] is True
    assert harness.consume_request_providers() == ["valid"]


@pytest.mark.asyncio
async def test_harness_records_actual_model_selected_by_router():
    harness = FailoverLLMClient(
        [("openrouter-free", _RoutingClient(response='{"ok":true}'))],
        LLMHarnessCfg(models=["openrouter-free"]),
    )
    assert await harness.complete_text(
        prompt="p", extracted_text="t", filename="a"
    ) == '{"ok":true}'
    assert harness.consume_request_providers() == [
        "openrouter-free->openai/gpt-oss-120b:free"
    ]


def test_production_configuration_fails_if_sampling_is_enabled():
    payload = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    payload["env"] = "production"
    with pytest.raises(ValueError, match="sampling must be disabled"):
        Config.model_validate(payload)


def test_sampling_source_requires_read_only_endpoint():
    payload = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    payload["minio"]["sampling_source_bucket"] = "source"
    with pytest.raises(ValueError, match="read_only"):
        Config.model_validate(payload)


def test_config_manager_imports_only_minio_credentials(tmp_path: Path):
    source = tmp_path / "artemis-production.yaml"
    source.write_text(
        "minio:\n  endpoint: prod:9000\n  access_key: readonly\n"
        "  secret_key: secret\n  secure: true\nserver:\n  port: 9999\n",
        encoding="utf-8",
    )
    base = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    base["minio"]["endpoints"]["production"] = {
        "endpoint": "placeholder:9000",
        "access_key": "",
        "secret_key": "",
        "secure": False,
        "credential_source": str(source),
        "read_only": True,
    }
    base["minio"]["buckets"]["production_sample"] = {
        "endpoint": "production",
        "name": "chaos-prod",
    }
    base["minio"]["sampling_source_bucket"] = "production_sample"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(base), encoding="utf-8")
    config = ConfigManager().init_config(path=str(config_path), env="development")
    endpoint, bucket = config.minio.resolve_sampling_bucket()
    assert (endpoint.endpoint, endpoint.access_key, endpoint.secret_key, endpoint.secure) == (
        "prod:9000", "readonly", "secret", True
    )
    assert bucket == "chaos-prod"
    assert config.server.port != 9999


def test_production_app_does_not_register_sampling_routes():
    payload = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
    payload["env"] = "production"
    payload["engine"]["knowledge_engine"]["sampling_enabled"] = False

    class Runtime:
        config = Config.model_validate(payload)

    app = create_app(Runtime())
    paths = {route.path for route in app.routes}
    assert "/api/v1/atlas-kg/sample-runs" not in paths
    client = TestClient(app)
    response = client.post("/api/v1/atlas-kg/discovery-runs", json={
        "sample_size": 1, "report_types": ["stock"]
    })
    assert response.status_code == 404
    health = client.get("/health").json()
    assert health["sampling_enabled"] is False
