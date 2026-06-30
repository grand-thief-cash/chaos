"""Raw financial / corporate-action / equity-structure queries.

Thin passthroughs to phoenixA raw data APIs.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.services.bi.base import BIServiceBase


class RawQueryMixin(BIServiceBase):
    """Raw data queries forwarded to phoenixA."""

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
