from __future__ import annotations

from typing import Any

from artemis.core import cfg_mgr
from artemis.core.clients import PhoenixAClient
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.registry.client import FeatureRegistryClient


def build_registry_client(source_profile: str, logger: Any = None) -> FeatureRegistryClient:
    try:
        profile = None if source_profile in {"", "default", "relx"} else source_profile
        services = cfg_mgr.get_dept_services_for_source(profile)
    except ValueError as exc:
        raise FeaturePlatformError(
            "SOURCE_PROFILE_NOT_FOUND",
            f"source profile {source_profile!r} is not configured",
            status_code=400,
        ) from exc
    endpoint = services.phoenixA
    if endpoint.host is None or endpoint.port is None:
        raise FeaturePlatformError(
            "SOURCE_UNAVAILABLE",
            f"source profile {source_profile!r} has no PhoenixA endpoint",
            status_code=503,
        )
    timeout = float(cfg_mgr.http_client_config.timeout_seconds if cfg_mgr.http_client_config else 5)
    transport = PhoenixAClient(
        host=endpoint.host,
        port=endpoint.port,
        logger=logger,
        timeout_seconds=timeout,
    )
    return FeatureRegistryClient(transport)
