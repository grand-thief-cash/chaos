from pathlib import Path

import pytest
from pydantic import ValidationError

from artemis.feature_platform.domain.models import FeatureComputeRequest, RegistryFeatureVersion
from artemis.feature_platform.manifests.checksum import manifest_registry_checksum
from artemis.feature_platform.manifests.loader import FeatureManifestLoader
from artemis.feature_platform.planning import DependencyPlanner
from artemis.feature_platform.tasks.feature_compute_task import FeatureComputeTask
from artemis.services.feature_service import FeatureService


CATALOG_ROOT = Path(__file__).parents[1] / "config" / "feature_catalog"


def _constant_registry_version():
    manifest = FeatureManifestLoader(CATALOG_ROOT).load().get("platform.security.constant_one", 1)
    return RegistryFeatureVersion(
        feature_code=manifest.feature.code,
        definition={
            "id": 1,
            "feature_code": manifest.feature.code,
            "value_type": "number",
        },
        version={
            "id": 11,
            "feature_id": 1,
            "version_number": 1,
            "status": "published",
            "manifest_checksum": manifest_registry_checksum(manifest),
        },
        implementation={
            "id": 21,
            "feature_version_id": 11,
            "kind": "python",
            "producer_service": "artemis",
            "backend": "python",
            "entrypoint": manifest.implementation.entrypoint,
            "implementation_revision": 1,
            "config": {},
            "checksum": "b" * 64,
            "is_canonical": True,
            "status": "active",
        },
        dependencies=[],
    )


class _TaskEngine:
    def __init__(self):
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return {"accepted": True}


class _RegistryClient:
    def __init__(self, *, reused=False):
        self.version = _constant_registry_version()
        self.reused = reused
        self.subjects = []

    def resolve_version(self, code, version):
        assert (code, version) == (self.version.feature_code, 1)
        return self.version

    def create_run(self, payload):
        self.payload = payload
        return {
            "accepted": True,
            "reused": self.reused,
            "run_id": "5cecd0dc-5c46-4ef7-a71a-caa53b0fe8a9",
            "status": "succeeded" if self.reused else "queued",
            "request_fingerprint": "c" * 64,
        }

    def batch_subjects(self, run_id, security_ids, included_reason):
        self.subjects = list(security_ids)
        return {"inserted": len(security_ids)}

    def cancel_run(self, run_id):
        raise AssertionError("new run should not be cancelled")


def _request():
    return FeatureComputeRequest.model_validate(
        {
            "features": [{"code": "platform.security.constant_one", "version": 1}],
            "security_ids": [1, 2, 3],
            "as_of_time": "2026-07-14T15:00:00+08:00",
            "data_cutoff_time": "2026-07-14T15:00:00+08:00",
            "market": "zh_a",
            "source_profile": "home",
            "trigger_type": "manual",
        }
    )


def test_compute_request_rejects_coerced_identity_and_sensitive_parameters():
    raw = _request().model_dump(mode="json")
    raw["security_ids"] = ["1"]
    with pytest.raises(ValidationError):
        FeatureComputeRequest.model_validate(raw)

    raw = _request().model_dump(mode="json")
    raw["parameters"] = {"nested": {"api_token": "do-not-persist"}}
    with pytest.raises(ValidationError, match="sensitive runtime parameter"):
        FeatureComputeRequest.model_validate(raw)


def test_feature_service_freezes_run_and_submits_async_task():
    task_engine = _TaskEngine()
    registry = _RegistryClient()
    service = FeatureService(
        task_engine,
        registry_factory=lambda profile: registry,
        code_revision="test-revision",
    )
    response = service.compute(_request())
    assert response.status == "queued"
    assert registry.subjects == [1, 2, 3]
    assert registry.payload["dependency_plan_checksum"]
    assert registry.payload["root_feature_version_ids"] == [11]
    assert len(task_engine.requests) == 1
    task = task_engine.requests[0]
    assert task.task_meta.exec_type == "ASYNC"
    assert task.task_body["expected_plan_checksum"] == registry.payload["dependency_plan_checksum"]


def test_feature_service_reused_run_does_not_resubmit_or_rewrite_subjects():
    task_engine = _TaskEngine()
    registry = _RegistryClient(reused=True)
    service = FeatureService(
        task_engine,
        registry_factory=lambda profile: registry,
        code_revision="test-revision",
    )
    response = service.compute(_request())
    assert response.reused is True
    assert registry.subjects == []
    assert task_engine.requests == []


class _TaskRegistryClient(_RegistryClient):
    def __init__(self):
        super().__init__()
        self.run_status = "queued"
        self.items = {}
        self.values = []

    def update_run(self, run_id, expected_status, new_status, **kwargs):
        assert self.run_status == expected_status
        self.run_status = new_status
        return {"status": new_status}

    def batch_items(self, run_id, feature_version_ids):
        self.items = {version_id: "queued" for version_id in feature_version_ids}
        return {"inserted": len(feature_version_ids)}

    def update_item(self, run_id, feature_version_id, expected_status, new_status, **kwargs):
        assert self.items[feature_version_id] == expected_status
        self.items[feature_version_id] = new_status
        return {"status": new_status}

    def write_numeric_values(self, run_id, feature_version_id, observed_at, values):
        self.values.extend(values)
        return {"inserted": len(values)}

    def complete_run(self, run_id):
        assert self.run_status == "validating"
        assert set(self.items.values()) == {"succeeded"}
        self.run_status = "succeeded"
        return {"status": "succeeded"}


class _TaskContext:
    def __init__(self, run_id, body, client):
        self.run_id = run_id
        self.task_id = run_id
        self.task_code = "feature_platform_compute"
        self.incoming_params = body
        self.params = {}
        self.stats = {}
        self.status = "PENDING"
        self.error = None
        self.failed_phase = None
        self.logger = None
        self.feature_registry_client = client

    def set_status(self, status):
        self.status = status

    def has_failed(self):
        return self.status == "FAILED"

    def fail(self, error, phase=None):
        self.status = "FAILED"
        self.error = str(error)
        if phase and not self.failed_phase:
            self.failed_phase = phase

    def close(self):
        pass

    def emit_failure_log(self, phase_durations=None):
        pass


def test_feature_compute_task_runs_constant_one_through_remote_state_machine():
    client = _TaskRegistryClient()
    roots = [{"code": client.version.feature_code, "version": 1}]
    plan = DependencyPlanner(client.resolve_version).build(
        [FeatureComputeRequest.model_validate(_request().model_dump()).features[0]]
    )
    run_id = "5cecd0dc-5c46-4ef7-a71a-caa53b0fe8a9"
    context = _TaskContext(
        run_id,
        {
            "run_id": run_id,
            "root_features": roots,
            "root_feature_version_ids": list(plan.root_version_ids),
            "expected_plan_checksum": plan.plan_checksum,
            "security_ids": [1, 2, 3],
            "as_of_time": "2026-07-14T15:00:00+08:00",
            "data_cutoff_time": "2026-07-14T15:00:00+08:00",
            "source_profile": "home",
            "market": "zh_a",
            "parameters": {},
        },
        client,
    )
    FeatureComputeTask().run(context)
    assert context.status == "SUCCESS"
    assert client.run_status == "succeeded"
    assert client.items == {11: "succeeded"}
    assert [row["value"] for row in client.values] == [1.0, 1.0, 1.0]
    assert context.stats["numeric_values_written"] == 3
