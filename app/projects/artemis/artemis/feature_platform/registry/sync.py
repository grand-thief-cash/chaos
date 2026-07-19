from __future__ import annotations

from artemis.feature_platform.manifests.loader import LoadedCatalog
from artemis.feature_platform.registry.client import FeatureRegistryClient


def sync_catalog(client: FeatureRegistryClient, catalog: LoadedCatalog) -> dict:
    return client.sync_manifests(catalog.manifests)
