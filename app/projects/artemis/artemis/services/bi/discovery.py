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

    def get_symbol_coverage(
        self,
        symbol: Optional[str] = None,
        market: str = "zh_a",
        *,
        security_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Per-security data coverage summary.

        Identity is security_id (Phase 4). `security_id` is primary; `symbol` is
        convenience input resolved to security_id via the PhoenixAClient before
        the call (refactor §8.bis-5). Raises if the identity cannot be resolved
        (not in registry). One of security_id/symbol is required.
        """
        client = self._client()
        if not security_id:
            if not symbol:
                raise ValueError("get_symbol_coverage requires security_id or symbol")
            security_id = client.resolve_security_id(symbol, asset_type="stock", market=market)
            if not security_id:
                raise ValueError(
                    f"cannot resolve security_id for symbol={symbol!r} (market={market}); "
                    "ensure STOCK_ZH_A_LIST has upserted it to security_registry"
                )
        resp = client.get(
            f"/api/v2/catalog/securities/{security_id}/datasets/summary",
        )
        resp.raise_for_status()
        return resp.json()
