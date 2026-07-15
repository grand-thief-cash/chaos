from __future__ import annotations

import importlib
from typing import Any

from artemis.feature_platform.domain.enums import ImplementationKind
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureManifest
from artemis.feature_platform.manifests.checksum import registry_projection


PLUGIN_METHODS = ("validate", "load_inputs", "compute", "validate_output")


def load_entrypoint(entrypoint: str) -> type[Any]:
    module_name, class_name = entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise FeaturePlatformError(
            "PLUGIN_IMPORT_FAILED",
            f"cannot import feature entrypoint {entrypoint}: {exc}",
            status_code=422,
        ) from exc
    if not isinstance(plugin_class, type):
        raise FeaturePlatformError(
            "PLUGIN_IMPORT_FAILED",
            f"feature entrypoint {entrypoint} is not a class",
            status_code=422,
        )
    missing = [name for name in PLUGIN_METHODS if not callable(getattr(plugin_class, name, None))]
    if missing:
        raise FeaturePlatformError(
            "PLUGIN_PROTOCOL_INVALID",
            f"feature entrypoint {entrypoint} is missing methods: {', '.join(missing)}",
            status_code=422,
        )
    return plugin_class


def validate_manifest(manifest: FeatureManifest, *, check_entrypoint: bool = True) -> dict[str, Any]:
    projection = registry_projection(manifest)
    if manifest.quality.allow_nan or manifest.quality.allow_infinite or manifest.quality.allow_duplicates:
        raise FeaturePlatformError(
            "QUALITY_POLICY_UNSUPPORTED",
            f"Phase 2 numeric snapshots require finite, unique outputs for {manifest.identity}",
            status_code=422,
        )
    if manifest.implementation.kind != ImplementationKind.PYTHON:
        raise FeaturePlatformError(
            "UNSUPPORTED_IMPLEMENTATION",
            f"Phase 2 cannot execute {manifest.implementation.kind.value} implementation {manifest.identity}",
            status_code=422,
        )
    if check_entrypoint:
        load_entrypoint(manifest.implementation.entrypoint)
    return {
        "feature": manifest.identity,
        "manifest_checksum": projection["version"]["manifest_checksum"],
        "implementation_checksum": projection["implementation"]["checksum"],
        "valid": True,
    }
