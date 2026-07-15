from copy import deepcopy
from datetime import datetime
from pathlib import Path
import time
from zoneinfo import ZoneInfo

import pytest

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import (
    FeatureManifest,
    FeatureNumericOutput,
    FeatureReference,
    NumericValue,
    RegistryFeatureVersion,
)
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.execution.output_validator import OutputValidator
from artemis.feature_platform.execution.python_executor import PythonFeatureExecutor
from artemis.feature_platform.manifests.loader import FeatureManifestLoader
from artemis.feature_platform.planning import DependencyPlanner, PlanNode
from artemis.feature_platform.plugins.smoke.datafield_pit_probe import DataFieldPITProbeFeature
from artemis.feature_platform.providers.phoenixa import PhoenixAFeatureProvider


CATALOG_ROOT = Path(__file__).parents[1] / "config" / "feature_catalog"
TZ = ZoneInfo("Asia/Shanghai")


def _registry_version(code: str, number: int, version_id: int, dependencies=None):
    return RegistryFeatureVersion(
        feature_code=code,
        definition={"feature_code": code, "value_type": "number"},
        version={
            "id": version_id,
            "version_number": number,
            "status": "published",
            "manifest_checksum": "a" * 64,
        },
        implementation={
            "kind": "python",
            "status": "active",
            "is_canonical": True,
            "entrypoint": "artemis.feature_platform.plugins.smoke.constant_one:ConstantOneFeature",
        },
        dependencies=dependencies or [],
    )


def _feature_dependency(owner_id: int, upstream_code: str, upstream_number: int, upstream_id: int):
    return {
        "feature_version_id": owner_id,
        "dependency_kind": "feature",
        "depends_on_feature_version_id": upstream_id,
        "dependency_ref_snapshot": {
            "kind": "feature",
            "feature_code": upstream_code,
            "feature_version": upstream_number,
        },
        "ordinal": 0,
    }


def test_dependency_planner_orders_upstream_once_and_has_stable_checksum():
    upstream = _registry_version("platform.security.upstream", 1, 10)
    root = _registry_version(
        "platform.security.root",
        1,
        20,
        [_feature_dependency(20, upstream.feature_code, 1, 10)],
    )
    versions = {(item.feature_code, item.version_number): item for item in (upstream, root)}
    planner = DependencyPlanner(lambda code, version: versions[(code, version)])
    first = planner.build([FeatureReference(code=root.feature_code, version=1)])
    second = planner.build([FeatureReference(code=root.feature_code, version=1)])
    assert first.feature_version_ids == [10, 20]
    assert first.plan_checksum == second.plan_checksum
    assert len(first.plan_checksum) == 64


def test_dependency_planner_rejects_cycle_even_if_registry_returns_one():
    a = _registry_version("platform.security.node_a", 1, 1)
    b = _registry_version("platform.security.node_b", 1, 2)
    a.dependencies = [_feature_dependency(1, b.feature_code, 1, 2)]
    b.dependencies = [_feature_dependency(2, a.feature_code, 1, 1)]
    versions = {(item.feature_code, item.version_number): item for item in (a, b)}
    with pytest.raises(FeaturePlatformError) as error:
        DependencyPlanner(lambda code, version: versions[(code, version)]).build(
            [FeatureReference(code=a.feature_code, version=1)]
        )
    assert error.value.code == "DEPENDENCY_CYCLE"


class _FinancialClient:
    def query_financial_flat(self, **kwargs):
        return {
            "dataset": "financial_statement",
            "source": "amazing_data",
            "data_type": "income",
            "rows": [
                {
                    "security_id": 1,
                    "reporting_period": "2025-12-31",
                    "ann_date": "2026-04-01",
                    "actual_ann_date": "2026-04-02",
                    "NET_PRO_EXCL_MIN_INT_INC": 10,
                },
                {
                    "security_id": 1,
                    "reporting_period": "2026-03-31",
                    "ann_date": "2026-07-01",
                    "actual_ann_date": "2026-07-10",
                    "NET_PRO_EXCL_MIN_INT_INC": 20,
                },
                {
                    "security_id": 1,
                    "reporting_period": "2026-06-30",
                    "ann_date": "2026-06-01",
                    "actual_ann_date": "2026-07-15",
                    "NET_PRO_EXCL_MIN_INT_INC": 999,
                },
            ],
            "total": 3,
        }


def _pit_context():
    manifest = FeatureManifestLoader(CATALOG_ROOT).load().get("platform.security.datafield_pit_probe", 1)
    dependency = manifest.dependencies[0].model_dump(mode="json", exclude_none=True)
    registry = _registry_version(manifest.feature.code, 1, 101)
    registry.definition["value_type"] = "number"
    registry.dependencies = [
        {
            "dependency_kind": "data_field",
            "data_field_dictionary_id": 77,
            "dependency_ref_snapshot": dependency,
            "ordinal": 0,
        }
    ]
    node = PlanNode(registry, (), (dependency,))
    return FeatureExecutionContext(
        run_id="run",
        node=node,
        manifest=manifest,
        as_of_time=datetime(2026, 7, 12, 15, tzinfo=TZ),
        data_cutoff_time=datetime(2026, 7, 12, 15, tzinfo=TZ),
        security_ids=(1, 2),
        source_profile="test",
        market="zh_a",
    )


def test_pit_provider_filters_future_actual_announcement_and_records_exact_max():
    ctx = _pit_context()
    provider = PhoenixAFeatureProvider(_FinancialClient())
    dependency = ctx.node.data_field_dependencies[0]
    inputs = provider.load_data_field(ctx, dependency)
    assert [record.value for record in inputs.records] == [10, 20]
    output = DataFieldPITProbeFeature().compute(ctx, inputs)
    first, missing = output.rows
    assert first.value == 20
    assert first.source_max_available_at == datetime(2026, 7, 10, tzinfo=TZ)
    assert missing.value_status.value == "missing"
    assert missing.source_max_available_at == ctx.data_cutoff_time
    validated = OutputValidator().validate(ctx, output, requires_source_availability=True)
    assert validated.valid_count == 1
    assert validated.missing_count == 1


def test_output_validator_rejects_subject_outside_frozen_universe():
    ctx = _pit_context()
    manifest_data = deepcopy(ctx.manifest.model_dump(mode="json"))
    manifest_data["quality"]["min_coverage_ratio"] = 0
    manifest = FeatureManifest.model_validate(manifest_data)
    bad_ctx = FeatureExecutionContext(**{**ctx.__dict__, "manifest": manifest})
    output = DataFieldPITProbeFeature().compute(
        bad_ctx,
        type("Batch", (), {"records": (), "dependency": {}})(),
    )
    output.rows[0].security_id = 999
    with pytest.raises(FeaturePlatformError) as error:
        OutputValidator().validate(bad_ctx, output, requires_source_availability=True)
    assert error.value.code == "OUTPUT_OUTSIDE_UNIVERSE"


class SlowFeaturePlugin:
    def validate(self, definition, version, implementation):
        pass

    def load_inputs(self, ctx, provider, dependencies):
        return None

    def compute(self, ctx, inputs):
        time.sleep(0.05)
        return FeatureNumericOutput(
            feature_version_id=ctx.feature_version_id,
            observed_at=ctx.as_of_time,
            rows=[NumericValue(security_id=1, value=1.0, value_status="valid")],
        )

    def validate_output(self, ctx, output):
        pass


def test_python_executor_maps_plugin_deadline_to_structured_timeout():
    manifest = FeatureManifestLoader(CATALOG_ROOT).load().get("platform.security.constant_one", 1)
    raw = manifest.model_dump(mode="json")
    raw["implementation"]["entrypoint"] = (
        "tests.test_feature_platform_planning_execution:SlowFeaturePlugin"
    )
    slow_manifest = FeatureManifest.model_validate(raw)
    registry = _registry_version(slow_manifest.feature.code, 1, 301)
    node = PlanNode(registry, (), ())
    ctx = FeatureExecutionContext(
        run_id="run",
        node=node,
        manifest=slow_manifest,
        as_of_time=datetime(2026, 7, 12, 15, tzinfo=TZ),
        data_cutoff_time=datetime(2026, 7, 12, 15, tzinfo=TZ),
        security_ids=(1,),
        source_profile="test",
        market="zh_a",
    )
    with pytest.raises(FeaturePlatformError) as error:
        PythonFeatureExecutor(timeout_seconds=0.001).execute(ctx, object())
    assert error.value.code == "PLUGIN_TIMEOUT"
