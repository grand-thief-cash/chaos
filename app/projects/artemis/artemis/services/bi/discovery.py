"""Discovery: datasets, fields, enums, and per-security coverage.

Raw passthrough to the phoenixA catalog APIs.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.services.bi.base import BIServiceBase


class DiscoveryMixin(BIServiceBase):
    """Dataset/field/enum discovery and per-security coverage."""

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

    # ─── Per-security coverage ───

    def get_security_coverage(
        self,
        security_id: int,
        market: str = "zh_a",
    ) -> Dict[str, Any]:
        """Per-security data coverage summary.

        Identity is security_id (Phase 4, no dual-track). ``security_id`` is
        required.
        """
        client = self._client()
        resp = client.get(
            f"/api/v2/catalog/securities/{security_id}/datasets/summary",
        )
        # 404 is a normal outcome after a registry rebuild (old security_id no
        # longer exists) — surface it as ValueError so the route maps to 404,
        # not as a generic 500 (raise_for_status would raise HTTPError → 500).
        if resp.status_code == 404:
            raise ValueError(f"security_id {security_id} not found")
        resp.raise_for_status()
        return resp.json()
