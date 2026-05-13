"""因子计算服务。"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.factor_engine.pipeline import FactorPipeline, FactorDataProvider
from artemis.engines.factor_engine.providers.phoenixa_provider import PhoenixADataProvider
from artemis.engines.factor_engine.registry import list_factors
from artemis.engines.factor_engine.storage.factor_store import FactorStore
from artemis.log.logger import get_logger

logger = get_logger("factor_service")

# ---------------------------------------------------------------------------
# Mock data provider (数据未 ready 时使用)
# ---------------------------------------------------------------------------

class MockFactorDataProvider:
    """占位数据源 — 返回空数据，用于流程验证。"""

    def get_active_symbols(self, market: str, as_of_date: str) -> List[str]:
        logger.warning("MockFactorDataProvider: returning empty symbol list")
        return []

    def get_industry_map(self, taxonomy: str, market: str) -> Dict[str, str]:
        return {}

    def get_financial_data(self, symbol: str, as_of_date: str) -> Dict[str, pd.DataFrame]:
        return {}

    def get_market_data(self, symbol: str, as_of_date: str) -> Optional[pd.DataFrame]:
        return None

    def get_current_period(self, symbol: str, as_of_date: str) -> Optional[str]:
        return None


# ---------------------------------------------------------------------------
# PhoenixA provider initialization
# ---------------------------------------------------------------------------

def _build_phoenix_client(source: str | None = None) -> PhoenixAClient:
    """从配置构建 PhoenixAClient。source 指定数据源名称。"""
    dept = cfg_mgr.get_dept_services_for_source(source)
    if not dept or not dept.phoenixA:
        raise ValueError("phoenixA service not configured")
    cfg = dept.phoenixA
    return PhoenixAClient(
        host=cfg.host,
        port=cfg.port,
        logger=logger,
        timeout_seconds=getattr(cfg, "timeout_seconds", 30),
    )


def _init_provider() -> FactorDataProvider:
    """Initialize PhoenixA provider if available, otherwise use mock."""
    try:
        # Try to create PhoenixA client from config
        client = _build_phoenix_client()
        # Test connection by making a simple query
        client.get_securities(limit=1)
        logger.info("factor_service: using PhoenixA data provider")
        return PhoenixADataProvider(client)
    except Exception as e:
        logger.warning({
            "event": "factor_service_phoenixa_unavailable",
            "fallback": "using MockFactorDataProvider",
            "error": str(e),
        })
        return MockFactorDataProvider()


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------

_store = FactorStore()
_provider: FactorDataProvider = _init_provider()
_pipeline = FactorPipeline(_provider, _store)


def compute_full(as_of_date: str, market: str = "zh_a") -> dict:
    """触发全量因子计算。"""
    logger.info({"event": "factor_compute_full", "as_of_date": as_of_date, "market": market})
    result = _pipeline.run_full(as_of_date, market)
    return {"status": "ok", "symbols_count": len(result), "as_of_date": as_of_date}


def compute_incremental(symbols: List[str], as_of_date: str, market: str = "zh_a") -> dict:
    """增量因子计算。"""
    logger.info({"event": "factor_compute_incr", "symbols": symbols[:5], "as_of_date": as_of_date})
    _pipeline.run_incremental(symbols, as_of_date, market)
    return {"status": "ok", "symbols_count": len(symbols)}


def get_snapshot(symbol: str, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
    return _store.get_factor_snapshot(symbol, as_of_date, market)


def get_ranking(factor_name: str, as_of_date: str, market: str = "zh_a", top_n: int = 50) -> List[dict]:
    df = _store.get_normalized_snapshot(as_of_date, market)
    if df.empty or factor_name not in df.columns:
        return []
    s = df[factor_name].dropna().sort_values(ascending=False).head(top_n)
    return [{"symbol": sym, factor_name: float(val)} for sym, val in s.items()]


def get_meta() -> List[dict]:
    return list_factors()

