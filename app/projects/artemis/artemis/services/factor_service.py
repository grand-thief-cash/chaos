"""因子计算服务。"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import pandas as pd

from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient
from artemis.engines.factor_engine.pipeline import FactorPipeline, FactorDataProvider
from artemis.engines.factor_engine.providers.phoenixa_provider import PhoenixADataProvider
from artemis.engines.factor_engine.registry import get_factor_meta, list_factors
from artemis.engines.factor_engine.storage.factor_store import FactorStore
from artemis.engines.factor_engine.ttm import normalize_date
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

    def get_industry_context(self, symbol: str, taxonomy: str, market: str) -> Dict[str, Any]:
        return {}

    def get_financial_data(self, symbol: str, as_of_date: str) -> Dict[str, pd.DataFrame]:
        return {}

    def get_market_data(self, symbol: str, as_of_date: str, adjust: Optional[str] = None) -> Optional[pd.DataFrame]:
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
    as_of_date = normalize_date(as_of_date)
    logger.info({"event": "factor_compute_full", "as_of_date": as_of_date, "market": market})
    result = _pipeline.run_full(as_of_date, market)
    return {"status": "ok", "symbols_count": len(result), "as_of_date": as_of_date}


def compute_incremental(symbols: List[str], as_of_date: str, market: str = "zh_a") -> dict:
    """增量因子计算。"""
    as_of_date = normalize_date(as_of_date)
    logger.info({"event": "factor_compute_incr", "symbols": symbols[:5], "as_of_date": as_of_date})
    _pipeline.run_incremental(symbols, as_of_date, market)
    return {"status": "ok", "symbols_count": len(symbols)}


def get_snapshot(symbol: str, as_of_date: str, market: str = "zh_a") -> Optional[dict]:
    as_of_date = normalize_date(as_of_date)
    return _store.get_factor_snapshot(symbol, as_of_date, market)


def get_ranking(factor_name: str, as_of_date: str, market: str = "zh_a", top_n: int = 50) -> List[dict]:
    as_of_date = normalize_date(as_of_date)
    df = _store.get_normalized_snapshot(as_of_date, market)
    if df.empty or factor_name not in df.columns:
        return []
    meta = get_factor_meta(factor_name)
    ascending = False if meta is None else not meta.higher_is_better
    s = df[factor_name].dropna().sort_values(ascending=ascending).head(top_n)
    return [{"symbol": sym, factor_name: float(val)} for sym, val in s.items()]


def get_meta() -> List[dict]:
    return list_factors()


def get_availability(refresh: bool = False) -> dict:
    factor_defs = list_factors()
    capabilities = _get_catalog_capabilities(refresh=refresh)
    source_status = _analyze_capability_sources(capabilities)

    factors = []
    summary = Counter()
    for item in factor_defs:
        availability = _build_factor_availability(item, source_status)
        summary[availability["availability_status"]] += 1
        factors.append(availability)

    return {
        "capability_source": "phoenixA_catalog" if capabilities.get("capabilities") else "unavailable",
        "source_status": source_status,
        "summary": dict(summary),
        "factors": factors,
    }


def _get_catalog_capabilities(refresh: bool = False) -> Dict[str, Any]:
    client: PhoenixAClient | None = None
    if isinstance(_provider, PhoenixADataProvider):
        client = _provider.client
    else:
        try:
            client = _build_phoenix_client()
        except Exception as exc:
            logger.warning({
                "event": "factor_availability_client_unavailable",
                "error": str(exc),
            })
            return {"capabilities": []}
    return client.get_catalog_capabilities(refresh=refresh) if client else {"capabilities": []}


def _analyze_capability_sources(capabilities: Dict[str, Any]) -> Dict[str, dict]:
    status: Dict[str, dict] = {
        "bars": {"available": False, "sources": {}, "time_range": None, "fields_known": []},
        "income": {"available": False, "sources": {}, "time_range": None, "fields_known": []},
        "balance_sheet": {"available": False, "sources": {}, "time_range": None, "fields_known": []},
        "cashflow": {"available": False, "sources": {}, "time_range": None, "fields_known": []},
        "corporate_action": {"available": False, "sources": {}, "time_range": None, "fields_known": []},
    }

    for domain in capabilities.get("capabilities", []):
        for table in domain.get("tables", []):
            table_name = str(table.get("table_name") or "")
            data_sources = table.get("data_sources") or []
            capability = table.get("capability") or {}
            output_fields = capability.get("output_fields") or []
            time_range = table.get("time_range") or None

            def _merge(key: str) -> None:
                status[key]["available"] = True
                for ds in data_sources:
                    source = str(ds.get("source") or "unknown")
                    status[key]["sources"][source] = int(ds.get("row_count") or 0)
                if time_range:
                    status[key]["time_range"] = time_range
                fields = [f.get("name") for f in output_fields if isinstance(f, dict) and f.get("name")]
                if fields:
                    status[key]["fields_known"] = sorted(set(status[key]["fields_known"]) | set(fields))

            if table_name.startswith("bars_"):
                _merge("bars")
            elif table_name == "financial_statement":
                for dt in capability.get("data_types") or []:
                    type_value = str(dt.get("type_value") or "")
                    if type_value in {"income", "balance_sheet", "cashflow"}:
                        _merge(type_value)
            elif table_name == "corporate_action":
                _merge("corporate_action")

    return status


def _build_factor_availability(factor_def: Dict[str, Any], source_status: Dict[str, dict]) -> Dict[str, Any]:
    required_sources = list(factor_def.get("required_data_sources") or [])
    required_fields = list(factor_def.get("required_fields") or [])

    available_sources = [source for source in required_sources if source_status.get(source, {}).get("available")]
    missing_sources = [source for source in required_sources if source not in available_sources]
    availability_status = "unknown"
    if required_sources:
        if len(available_sources) == len(required_sources):
            availability_status = "available"
        elif available_sources:
            availability_status = "partial"
        else:
            availability_status = "missing"

    notes: List[str] = []
    if missing_sources:
        notes.append(f"missing_sources:{','.join(missing_sources)}")
    for source in available_sources:
        stats = source_status.get(source, {})
        if not stats.get("sources"):
            notes.append(f"source_without_row_counts:{source}")

    return {
        "name": factor_def["name"],
        "cn_name": factor_def["cn_name"],
        "category": factor_def["category"],
        "availability_expected": (factor_def.get("availability") or {}).get("expected", "unknown"),
        "availability_status": availability_status,
        "required_data_sources": required_sources,
        "required_fields": required_fields,
        "required_field_count": len(required_fields),
        "available_sources": available_sources,
        "missing_sources": missing_sources,
        "source_status": {source: source_status.get(source, {}) for source in required_sources},
        "provenance": factor_def.get("provenance") or {},
        "notes": notes,
    }


