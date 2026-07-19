"""General securities lookup service.

A general capability shared across features (BI DuPont, workbench, ...), not
BI-specific. Thin passthrough to phoenixA's v2 security APIs:

  - search: GET /api/v2/securities/search  (one-pass items+total over L1 snapshot)
  - by-id:  GET /api/v2/securities/{id}    (O(1) single-row lookup)

artemis /securities/* routes and the legacy /bi/securities route both delegate
here, so the two stay behaviorally identical during the deprecation window.

``security_id`` remains the internal identity handed to downstream endpoints
(e.g. /bi/dupont/{security_id}); this service only resolves the user-facing
name/symbol -> security_id question.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.services.bi.base import BIServiceBase


class SecuritiesService(BIServiceBase):
    """Securities registry passthrough: search + by-id over phoenixA."""

    def list_securities(
        self,
        *,
        q: Optional[str] = None,
        market: str = "zh_a",
        asset_type: str = "stock",
        exchange: Optional[str] = None,
        name: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search the registry. Returns {items, total, limit, offset}.

        ``q`` is the unified term (symbol exact OR name contains). Legacy
        ``name``/``symbol`` are forwarded for backward-compatible callers.
        """
        return self._client().search_securities(
            q=q, asset_type=asset_type, market=market, exchange=exchange,
            status=status, name=name, symbol=symbol, limit=limit, offset=offset,
        )

    def get_security(self, security_id: int) -> Dict[str, Any]:
        """Fetch one security by id. Raises ValueError (-> 404) if not found."""
        if security_id is None or security_id <= 0:
            raise ValueError(f"security_id must be a positive integer, got {security_id!r}")
        item = self._client().get_security_by_id(security_id)
        if item is None:
            raise ValueError(f"security_id {security_id} not found")
        return item
