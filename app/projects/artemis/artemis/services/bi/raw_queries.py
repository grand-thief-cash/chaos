"""Raw financial / corporate-action / equity-structure queries.

Thin passthroughs to phoenixA raw data APIs. Identity is security_id
(Phase 4, no dual-track). Callers pass security_id/security_ids directly.
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
        if security_id is not None:
            params["security_id"] = str(security_id)
        elif security_ids is not None:
            params["security_ids"] = ",".join(str(i) for i in security_ids)
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
        if security_id is not None:
            params["security_id"] = str(security_id)
        elif security_ids is not None:
            params["security_ids"] = ",".join(str(i) for i in security_ids)
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
        if security_id is not None:
            params["security_id"] = str(security_id)
        elif security_ids is not None:
            params["security_ids"] = ",".join(str(i) for i in security_ids)
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
