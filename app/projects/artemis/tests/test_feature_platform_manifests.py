import json
from copy import deepcopy
from pathlib import Path

import pytest

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureManifest
from artemis.feature_platform.manifests.checksum import (
    manifest_registry_checksum,
    registry_projection,
)
from artemis.feature_platform.manifests.loader import FeatureManifestLoader


CATALOG_ROOT = Path(__file__).parents[1] / "config" / "feature_catalog"


def test_catalog_loads_phase_two_smoke_manifests_and_schema_is_json():
    catalog = FeatureManifestLoader(CATALOG_ROOT).load()
    assert [manifest.identity for manifest in catalog.manifests] == [
        "platform.security.constant_one@1",
        "platform.security.datafield_pit_probe@1",
    ]
    schema = json.loads((CATALOG_ROOT / "schema" / "feature-manifest.schema.json").read_text("utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    pit = catalog.get("platform.security.datafield_pit_probe", 1)
    dependency = pit.dependencies[0]
    assert dependency.raw_field == "NET_PRO_EXCL_MIN_INT_INC"
    assert dependency.contract_version == "2026-06-27"


def test_registry_projection_is_stable_and_excludes_local_execution_policy():
    manifest = FeatureManifestLoader(CATALOG_ROOT).load().get("platform.security.constant_one", 1)
    first = registry_projection(manifest)
    raw = manifest.model_dump(mode="json")
    raw["feature"]["tags"] = list(reversed(raw["feature"]["tags"]))
    reordered = FeatureManifest.model_validate(raw)
    second = registry_projection(reordered)
    assert first == second
    assert len(manifest_registry_checksum(manifest)) == 64
    assert "quality" not in first
    assert "materialization" not in first
    assert first["version"]["manifest_checksum"] == manifest_registry_checksum(manifest)


def test_manifest_rejects_sensitive_implementation_config():
    manifest = FeatureManifestLoader(CATALOG_ROOT).load().get("platform.security.constant_one", 1)
    raw = deepcopy(manifest.model_dump(mode="json"))
    raw["implementation"]["config"] = {"nested": {"api_token": "do-not-store"}}
    with pytest.raises(Exception, match="sensitive config key"):
        FeatureManifest.model_validate(raw)


def test_loader_rejects_paths_outside_catalog_root():
    loader = FeatureManifestLoader(CATALOG_ROOT)
    with pytest.raises(FeaturePlatformError) as error:
        loader.load(["../config.yaml"])
    assert error.value.code == "MANIFEST_PATH_INVALID"
