"""Raw financial / corporate-action / equity-structure queries.

Thin passthroughs to phoenixA raw data APIs. PhoenixA data-table APIs are
security_id-only after Phase 3; these methods keep a symbol/symbols convenience
interface for cthulhu/factor callers and resolve to security_id via the
PhoenixAClient before the call (refactor §8.bis-5). Full symbol→security_id
contract migration is Phase 4.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
        params.update(self._security_id_params(client, symbol, symbols, market))
        for key, val in (
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
        params.update(self._security_id_params(client, symbol, symbols, market))
        for key, val in (
            ("fields", fields),
            ("period_start", period_start),
            ("period_end", period_end),
        ):
            if val is not None and val != "":
                params[key] = val
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
        params.update(self._security_id_params(client, symbol, symbols, market))
        for key, val in (
            ("fields", fields),
            ("change_start", change_start),
            ("change_end", change_end),
        ):
            if val is not None and val != "":
                params[key] = val
        if current_only is not None:
            params["current_only"] = "1" if current_only else "0"
        if valid_only is not None:
            params["valid_only"] = "1" if valid_only else "0"
        resp = client.get(f"/api/v2/equity-structure/{source}", params=params)
        resp.raise_for_status()
        return resp.json()

    # ─── Helpers ───

    def _security_id_params(
        self,
        client,
        symbol: Optional[str],
        symbols: Optional[Any],
        market: str,
    ) -> Dict[str, str]:
        """Resolve symbol/symbols convenience input → security_id query params
        via the PhoenixAClient. `symbols` may be a comma-separated string or a
        list. market scopes the resolve only (not sent to phoenixA).
        """
        sym_list: Optional[List[str]] = None
        if symbols:
            if isinstance(symbols, str):
                sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
            else:
                sym_list = [str(s).strip() for s in symbols if str(s).strip()]
        return client.security_id_query_params(
            security_id=None,
            security_ids=None,
            symbol=symbol or "",
            symbols=sym_list,
            exchange=None,
            asset_type="stock",
            market=market,
        )
