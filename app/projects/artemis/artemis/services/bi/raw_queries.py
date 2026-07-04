"""Raw financial / corporate-action / equity-structure queries.

Thin passthroughs to phoenixA raw data APIs. Identity is security_id (Phase 4);
symbol/symbols are convenience input resolved to security_id via the
PhoenixAClient before the call (refactor §8.bis-5). Callers that already hold
a security_id pass it directly and skip the resolve.
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
        security_id: Optional[int] = None,
        security_ids: Optional[List[int]] = None,
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
        params.update(self._security_id_params(client, security_id, security_ids, symbol, symbols, market))
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
        security_id: Optional[int] = None,
        security_ids: Optional[List[int]] = None,
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
        params.update(self._security_id_params(client, security_id, security_ids, symbol, symbols, market))
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
        security_id: Optional[int] = None,
        security_ids: Optional[List[int]] = None,
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
        params.update(self._security_id_params(client, security_id, security_ids, symbol, symbols, market))
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
        security_id: Optional[int],
        security_ids: Optional[List[int]],
        symbol: Optional[str],
        symbols: Optional[Any],
        market: str,
    ) -> Dict[str, str]:
        """Coalesce explicit security_id(s) and symbol convenience input into the
        query params sent to a security_id-only phoenixA endpoint.

        security_id/security_ids are primary (used directly when supplied).
        symbol/symbols are convenience, resolved via the registry when no id is
        supplied. `symbols` may be a comma-separated string or a list. market
        scopes the resolve only (not sent to phoenixA). When NO identity is
        supplied, `{}` is returned (unfiltered query is intentional).

        Strict (Phase 1/3): a present-but-empty `symbol` (`?symbol=`) or a
        `symbols` with any empty token (`?symbols=,000001,` / `?symbols=`) →
        ValueError → 400, never silently treated as "no identity" (which would
        degrade to an unfiltered query). None = not supplied.
        """
        if symbol is not None and not symbol.strip():
            raise ValueError("symbol is empty; omit it or supply a non-empty value")
        sym_list: Optional[List[str]] = None
        if symbols is not None:
            if isinstance(symbols, str):
                sym_list = self._parse_symbols_strict(symbols)
            else:
                sym_list = [str(s).strip() for s in symbols]
                if not sym_list:
                    raise ValueError("symbols is empty")
                if any(not s for s in sym_list):
                    raise ValueError("symbols contains an empty token")
        return client.security_id_query_params(
            security_id=security_id,
            security_ids=security_ids,
            symbol=symbol or "",
            symbols=sym_list,
            exchange=None,
            asset_type="stock",
            market=market,
        )

    @staticmethod
    def _parse_symbols_strict(raw: str) -> List[str]:
        """Parse a comma-separated symbols string → list[str] (strict).

        Empty tokens (leading/trailing/consecutive comma, or bare `?symbols=`)
        → ValueError. Never returns an empty list for a present value.
        """
        out: List[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                raise ValueError("symbols contains an empty token")
            out.append(token)
        if not out:
            raise ValueError("symbols is empty")
        return out
