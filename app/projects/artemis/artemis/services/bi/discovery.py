"""Discovery: datasets, fields, enums, and per-symbol coverage.

Raw passthrough to the phoenixA catalog APIs.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.services.bi.base import BIServiceBase


class DiscoveryMixin(BIServiceBase):
    """Dataset/field/enum discovery and per-symbol coverage."""

    # ─── Discovery: datasets, fields, enums ───

    def list_datasets(self, source: Optional[str] = None) -> Dict[str, Any]:
        client = self._client()
        params = {}
        if source:
            params["source"] = source
        resp = client.get("/api/v2/catalog/datasets", params=params)
        resp.raise_for_status()
        return resp.json()

    def discover_fields(
        self,
        dataset: str,
        *,
        source: Optional[str] = None,
        data_type: Optional[str] = None,
        search: Optional[str] = None,
        include: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = self._client()
        params: Dict[str, Any] = {}
        if source:
            params["source"] = source
        if data_type:
            params["type"] = data_type
        if search:
            params["search"] = search
        if include:
            params["include"] = include
        resp = client.get(f"/api/v2/catalog/datasets/{dataset}/fields", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_enum(self, enum_name: str, source: Optional[str] = None) -> Dict[str, Any]:
        client = self._client()
        params = {}
        if source:
            params["source"] = source
        resp = client.get(f"/api/v2/catalog/enums/{enum_name}", params=params)
        resp.raise_for_status()
        return resp.json()

    # ─── Per-symbol coverage ───

    def get_symbol_coverage(self, symbol: str, market: str = "zh_a") -> Dict[str, Any]:
        client = self._client()
        resp = client.get(
            f"/api/v2/catalog/securities/{symbol}/datasets/summary",
            params={"market": market},
        )
        resp.raise_for_status()
        return resp.json()
