"""Lightweight BI service — transparent passthrough to phoenixA raw data APIs.

Architecture: phoenixA is the data middle-platform (raw queries, field discovery,
coverage). artemis is a thin BI gateway that forwards requests to phoenixA
without business computation. cthulhu calls artemis /bi/* endpoints.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger

logger = get_logger("bi_simple_service")


class BISimpleService:
    """Thin BI service: passthrough phoenixA raw APIs."""

    def _client(self) -> PhoenixAClient:
        dept = cfg_mgr.get_dept_services_for_source(None)
        if not dept or not dept.phoenixA:
            raise ValueError("phoenixA service not configured")
        cfg = dept.phoenixA
        return PhoenixAClient(
            host=cfg.host,
            port=cfg.port,
            logger=logger,
            timeout_seconds=getattr(cfg, "timeout_seconds", 30),
        )

    # ─── Securities ───

    def list_securities(
        self,
        *,
        market: str = "zh_a",
        asset_type: str = "stock",
        exchange: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        client = self._client()
        params: Dict[str, Any] = {
            "market": market,
            "asset_type": asset_type,
            "limit": limit,
            "offset": offset,
        }
        if exchange:
            params["exchange"] = exchange
        if name:
            params["name"] = name

        resp = client.get("/api/v2/securities", params=params)
        resp.raise_for_status()
        items = resp.json().get("data", [])

        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        count_resp = client.get("/api/v2/securities/count", params=count_params)
        count_resp.raise_for_status()
        total = count_resp.json().get("data", {}).get("count", 0)

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

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

    # ─── Raw queries ───

    def query_financial(
        self,
        *,
        source: str,
        statement_type: str,
        symbol: Optional[str] = None,
        symbols: Optional[str] = None,
        market: str = "zh_a",
        fields: Optional[str] = None,
        format: str = "flat",
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        report_type: Optional[str] = None,
        statement_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        client = self._client()
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "format": format,
        }
        for key, val in (
            ("symbol", symbol),
            ("symbols", symbols),
            ("market", market),
            ("fields", fields),
            ("period_start", period_start),
            ("period_end", period_end),
            ("report_type", report_type),
            ("statement_code", statement_code),
        ):
            if val is not None and val != "":
                params[key] = val
        resp = client.get(f"/api/v2/financial/{source}/{statement_type}", params=params)
        resp.raise_for_status()
        return resp.json()

    def query_corporate_action(
        self,
        *,
        source: str,
        action_type: str,
        symbol: Optional[str] = None,
        symbols: Optional[str] = None,
        market: str = "zh_a",
        fields: Optional[str] = None,
        format: str = "flat",
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        client = self._client()
        params: Dict[str, Any] = {"page": page, "page_size": page_size, "format": format}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = symbols
        if market:
            params["market"] = market
        if fields:
            params["fields"] = fields
        if period_start:
            params["period_start"] = period_start
        if period_end:
            params["period_end"] = period_end
        resp = client.get(f"/api/v2/corporate-action/{source}/{action_type}", params=params)
        resp.raise_for_status()
        return resp.json()

    def query_equity_structure(
        self,
        *,
        source: str,
        symbol: Optional[str] = None,
        symbols: Optional[str] = None,
        market: str = "zh_a",
        fields: Optional[str] = None,
        format: str = "flat",
        change_start: Optional[str] = None,
        change_end: Optional[str] = None,
        current_only: Optional[bool] = None,
        valid_only: Optional[bool] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        client = self._client()
        params: Dict[str, Any] = {"page": page, "page_size": page_size, "format": format}
        if symbol:
            params["symbol"] = symbol
        if symbols:
            params["symbols"] = symbols
        if market:
            params["market"] = market
        if fields:
            params["fields"] = fields
        if change_start:
            params["change_start"] = change_start
        if change_end:
            params["change_end"] = change_end
        if current_only is not None:
            params["current_only"] = "1" if current_only else "0"
        if valid_only is not None:
            params["valid_only"] = "1" if valid_only else "0"
        resp = client.get(f"/api/v2/equity-structure/{source}", params=params)
        resp.raise_for_status()
        return resp.json()
