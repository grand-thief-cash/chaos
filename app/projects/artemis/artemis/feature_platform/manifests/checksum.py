from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureManifest


def _normalize_go_map_value(value: Any) -> Any:
    """Normalize map values the same way Go encoding/json re-encodes any."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FeaturePlatformError(
                "MANIFEST_JSON_INVALID",
                "manifest config must not contain NaN or infinite values",
                status_code=400,
            )
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {
            str(key): _normalize_go_map_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_go_map_value(item) for item in value]
    raise FeaturePlatformError(
        "MANIFEST_JSON_INVALID",
        f"manifest config contains non-JSON value of type {type(value).__name__}",
        status_code=400,
    )


def _go_json_bytes(value: Any) -> bytes:
    # Go's encoding/json keeps UTF-8 but escapes HTML-sensitive characters and
    # the two Unicode line separators by default.
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    text = (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return text.encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_go_json_bytes(value)).hexdigest()


def implementation_checksum(manifest: FeatureManifest) -> str:
    implementation = manifest.implementation
    # These capitalized keys intentionally mirror the untagged anonymous Go
    # struct used by PhoenixA's normalizeAndValidateManifest.
    payload = {
        "Kind": implementation.kind.value,
        "ProducerService": implementation.producer_service,
        "Backend": implementation.backend,
        "Entrypoint": implementation.entrypoint,
        "Revision": implementation.implementation_revision,
        "Config": _normalize_go_map_value(implementation.config),
    }
    computed = _sha256(payload)
    if implementation.checksum and implementation.checksum != computed:
        raise FeaturePlatformError(
            "IMPLEMENTATION_CHECKSUM_MISMATCH",
            f"implementation checksum does not match {manifest.identity}",
            status_code=400,
        )
    return computed


def _dependency_projection(dependency: Any) -> dict[str, Any]:
    if dependency.kind.value == "feature":
        return {
            "kind": "feature",
            "feature_code": dependency.feature_code,
            "feature_version": dependency.feature_version,
        }
    return {
        "kind": "data_field",
        "source": dependency.source,
        "dataset": dependency.dataset,
        "data_type": dependency.data_type,
        "raw_field": dependency.raw_field,
        "contract_version": dependency.contract_version,
    }


def registry_projection(manifest: FeatureManifest) -> dict[str, Any]:
    """Return the strict PhoenixA Phase 1 FeatureManifest wire contract."""
    impl_checksum = implementation_checksum(manifest)
    payload: dict[str, Any] = {
        "feature": {
            "code": manifest.feature.code,
            "display_name": manifest.feature.display_name,
            "description": manifest.feature.description,
            "kind": manifest.feature.kind.value,
            "entity_type": manifest.feature.entity_type.value,
            "value_type": manifest.feature.value_type.value,
            "unit": manifest.feature.unit,
            "category": manifest.feature.category,
            "owner": manifest.feature.owner,
            "tags": sorted(manifest.feature.tags),
        },
        "version": {
            "number": manifest.version.number,
            "status": manifest.version.status.value,
            "frequency": manifest.version.frequency,
            "as_of_semantics": manifest.version.as_of_semantics,
            "missing_policy": manifest.version.missing_policy,
            "manifest_checksum": "",
        },
        "implementation": {
            "kind": manifest.implementation.kind.value,
            "producer_service": manifest.implementation.producer_service,
            "backend": manifest.implementation.backend,
            "entrypoint": manifest.implementation.entrypoint,
            "implementation_revision": manifest.implementation.implementation_revision,
            "config": _normalize_go_map_value(manifest.implementation.config),
            "checksum": impl_checksum,
            "status": manifest.implementation.status.value,
        },
        "dependencies": [_dependency_projection(dep) for dep in manifest.dependencies],
    }
    computed = _sha256(payload)
    if manifest.version.manifest_checksum and manifest.version.manifest_checksum != computed:
        raise FeaturePlatformError(
            "MANIFEST_CHECKSUM_MISMATCH",
            f"manifest checksum does not match {manifest.identity}",
            status_code=400,
        )
    payload["version"]["manifest_checksum"] = computed
    return payload


def manifest_registry_checksum(manifest: FeatureManifest) -> str:
    return str(registry_projection(manifest)["version"]["manifest_checksum"])
