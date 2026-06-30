"""Shared base for the BI service: phoenixA client + numeric helpers.

phoenixA is the data middle-platform (raw queries, field discovery, coverage)
and does no business computation. artemis is the BI backend: it forwards raw
passthrough queries for simple needs AND owns business computation for
analytical features like DuPont. The mixins in this package build on
``BIServiceBase`` and are combined into :class:`BIService`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.log.logger import get_logger

logger = get_logger("bi_service")


class BIServiceBase:
    """Common plumbing for BI service mixins: client + numeric helpers."""

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

    @staticmethod
    def _to_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _avg(cls, cur: Optional[float], prev: Optional[float]) -> Optional[float]:
        """Two-point average; falls back to the available endpoint if one is missing."""
        if cur is None and prev is None:
            return None
        if cur is None:
            return prev
        if prev is None:
            return cur
        return (cur + prev) / 2

    @classmethod
    def _ratio(cls, numer: Optional[float], denom: Optional[float]) -> Optional[float]:
        if numer is None or denom is None or denom == 0:
            return None
        return numer / denom

    @classmethod
    def _delta_direction(cls, delta: Optional[float]) -> Optional[str]:
        if delta is None:
            return None
        if delta > 1e-9:
            return "up"
        if delta < -1e-9:
            return "down"
        return "flat"

    @classmethod
    def _amount(cls, row: Dict[str, Any], field: str) -> Optional[float]:
        return cls._to_float(row.get(field))

    @classmethod
    def _sum(cls, row: Dict[str, Any], fields: List[str]) -> Optional[float]:
        total = 0.0
        any_val = False
        for f in fields:
            v = cls._amount(row, f)
            if v is not None:
                total += v
                any_val = True
        return total if any_val else None
