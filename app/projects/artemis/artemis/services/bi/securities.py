"""Securities listing — raw passthrough to phoenixA."""
from __future__ import annotations

from typing import Any, Dict, Optional

from artemis.services.bi.base import BIServiceBase


class SecuritiesMixin(BIServiceBase):
    """Securities catalog listing."""

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
