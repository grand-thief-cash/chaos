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
_DEFAULT_RUNTIME_KEY = "__default__"

# ---------------------------------------------------------------------------
# Mock data provider (数据未 ready 时使用)
# ---------------------------------------------------------------------------

class MockFactorDataProvider:
    """占位数据源 — 返回空数据，用于流程验证。Phase 4: security_id identity."""

    def get_active_securities(self, market: str, as_of_date: str) -> Dict[int, Dict[str, Any]]:
        logger.warning("MockFactorDataProvider: returning empty securities map")
        return {}

    def get_industry_map(
        self,
        taxonomy: str,
        market: str,
        use_batch: bool = True,
        security_ids: Optional[List[int]] = None,
    ) -> Dict[int, str]:
        return {}

    def get_industry_context(self, security_id: int, taxonomy: str, market: str) -> Dict[str, Any]:
        return {}

    def get_financial_data(self, security_id: int, as_of_date: str) -> Dict[str, pd.DataFrame]:
        return {}

    def get_market_data(self, security_id: int, as_of_date: str, adjust: Optional[str] = None) -> Optional[pd.DataFrame]:
        return None

    def get_current_period(self, security_id: int, as_of_date: str) -> Optional[str]:
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


def _init_provider(source: str | None = None) -> FactorDataProvider:
    """Initialize PhoenixA provider if available, otherwise use mock."""
    try:
        # Try to create PhoenixA client from config
        client = _build_phoenix_client(source)
        # Test connection by making a simple query
        client.get_securities(limit=1)
        logger.info({"event": "factor_service_provider_initialized", "source": source or "default", "provider": "PhoenixADataProvider"})
        return PhoenixADataProvider(client)
    except Exception as e:
        logger.warning({
            "event": "factor_service_phoenixa_unavailable",
            "fallback": "using MockFactorDataProvider",
            "source": source or "default",
            "error": str(e),
        })
        return MockFactorDataProvider()


# ---------------------------------------------------------------------------
# Runtime registry (per source)
# ---------------------------------------------------------------------------

_runtimes: Dict[str, tuple[FactorStore, FactorDataProvider, FactorPipeline]] = {}


def _runtime_key(source: str | None = None) -> str:
    normalized = str(source or "").strip()
    return normalized or _DEFAULT_RUNTIME_KEY


def _get_runtime(source: str | None = None) -> tuple[FactorStore, FactorDataProvider, FactorPipeline]:
    key = _runtime_key(source)
    runtime = _runtimes.get(key)
    if runtime is not None:
        return runtime

    store = FactorStore()
    provider = _init_provider(source)
    pipeline = FactorPipeline(provider, store)
    runtime = (store, provider, pipeline)
    _runtimes[key] = runtime
    return runtime


def compute_full(as_of_date: str, market: str = "zh_a", source: str | None = None) -> dict:
    """触发全量因子计算。"""
    as_of_date = normalize_date(as_of_date)
    _, _, pipeline = _get_runtime(source)
    logger.info({"event": "factor_compute_full", "as_of_date": as_of_date, "market": market, "source": source or "default"})
    result = pipeline.run_full(as_of_date, market)
    return {"status": "ok", "symbols_count": len(result), "as_of_date": as_of_date, "source": source or "default"}


def _get_client(source: str | None = None) -> Optional[PhoenixAClient]:
    """Return the runtime's PhoenixA client if available, else build one, else None."""
    runtime = _runtimes.get(_runtime_key(source))
    if runtime is not None and isinstance(runtime[1], PhoenixADataProvider):
        return runtime[1].client
    try:
        return _build_phoenix_client(source)
    except Exception as exc:
        logger.warning({"event": "factor_service_client_unavailable", "source": source or "default", "error": str(exc)})
        return None


def _resolve_security_ids(symbols: List[str], source: str | None = None) -> List[int]:
    """Resolve symbol convenience input → security_ids (strict, §8.bis-5).

    Raises ValueError if ANY supplied symbol cannot be resolved (partial or
    all-miss) — matches the Phase 3 rule that explicit identity must not
    silently degrade or partially execute. Also raises if the phoenixA client
    is unavailable (cannot resolve).
    """
    sym_list = [str(s).strip() for s in symbols if str(s).strip()]
    if not sym_list:
        raise ValueError("no non-empty symbols supplied")
    client = _get_client(source)
    if client is None:
        raise ValueError("cannot resolve symbols: phoenixA client unavailable")
    resolved = client.resolve_security_ids(symbols=sym_list)
    if len(resolved) != len(sym_list):
        raise ValueError(
            f"could not resolve all {len(sym_list)} symbol(s); only {len(resolved)} found "
            f"in security_registry (symbols={sym_list}); ensure STOCK_ZH_A_LIST has upserted them"
        )
    return resolved


def _resolve_security_id(symbol: str, source: str | None = None) -> int:
    """Resolve a single symbol → security_id (strict; raises on unresolvable)."""
    return _resolve_security_ids([symbol], source)[0]


def compute_incremental(
    security_ids: Optional[List[int]] = None,
    as_of_date: str = "",
    market: str = "zh_a",
    source: str | None = None,
    symbols: Optional[List[str]] = None,
) -> dict:
    """增量因子计算。Identity is security_id (Phase 4); `symbols` is convenience
    input resolved to security_ids via the registry before the call (§8.bis-5).

    Strict (Phase 3): an explicit empty/non-positive security_ids, or a symbols
    list where any entry fails to resolve (partial), raises ValueError — never
    silently computes a subset."""
    as_of_date = normalize_date(as_of_date)
    # Validate / resolve identity BEFORE building the runtime (fail fast on bad
    # input; avoids a phoenixA connection attempt for malformed requests).
    if security_ids is not None:
        if not security_ids:
            raise ValueError("security_ids is empty")
        if any(i <= 0 for i in security_ids):
            raise ValueError("security_ids must be positive integers")
        resolved = list(security_ids)
    elif symbols:
        resolved = _resolve_security_ids(symbols, source)  # strict — raises on partial
    else:
        raise ValueError("compute_incremental requires security_ids or symbols")
    _, _, pipeline = _get_runtime(source)
    logger.info({"event": "factor_compute_incr", "security_ids": resolved[:5], "as_of_date": as_of_date, "source": source or "default"})
    pipeline.run_incremental(resolved, as_of_date, market)
    return {"status": "ok", "securities_count": len(resolved), "source": source or "default"}


def get_snapshot(
    security_id: Optional[int] = None,
    as_of_date: str = "",
    market: str = "zh_a",
    source: str | None = None,
    symbol: Optional[str] = None,
) -> Optional[dict]:
    """Query a single-security factor snapshot. Identity is security_id (Phase 4);
    `symbol` is convenience input resolved via the registry (§8.bis-5).

    Strict (Phase 3): a non-positive security_id or an unresolvable symbol
    raises ValueError. Returns None only if no identity is supplied (the route
    400s before that) or the snapshot does not exist."""
    as_of_date = normalize_date(as_of_date)
    # Validate / resolve identity BEFORE building the runtime (fail fast on bad
    # input; avoids a phoenixA connection attempt for malformed requests).
    if security_id is not None:
        if security_id <= 0:
            raise ValueError("security_id must be a positive integer")
        resolved = security_id
    elif symbol:
        resolved = _resolve_security_id(symbol, source)  # strict — raises on unresolvable
    else:
        return None
    store, _, _ = _get_runtime(source)
    snap = store.get_factor_snapshot(resolved, as_of_date, market)
    if snap is None:
        return None
    snap = dict(snap)
    snap["security_id"] = int(resolved)
    return snap


def get_ranking(factor_name: str, as_of_date: str, market: str = "zh_a", top_n: int = 50, source: str | None = None) -> List[dict]:
    as_of_date = normalize_date(as_of_date)
    store, _, _ = _get_runtime(source)
    df = store.get_normalized_snapshot(as_of_date, market)
    if df.empty or factor_name not in df.columns:
        return []
    meta = get_factor_meta(factor_name)
    ascending = False if meta is None else not meta.higher_is_better
    s = df[factor_name].dropna().sort_values(ascending=ascending).head(top_n)
    labels = store.get_security_labels(as_of_date, market)
    return [
        {"security_id": int(sec_id), "symbol": labels.get(int(sec_id), ""), factor_name: float(val)}
        for sec_id, val in s.items()
    ]


def get_meta() -> List[dict]:
    return list_factors()


def get_availability(refresh: bool = False, source: str | None = None) -> dict:
    factor_defs = list_factors()
    capabilities = _get_catalog_capabilities(refresh=refresh, source=source)
    source_status = _analyze_capability_sources(capabilities)
    reachable = _capabilities_reachable(capabilities)
    capability_source = "phoenixA_catalog"
    if not reachable:
        capability_source = "unavailable"
    elif not capabilities.get("capabilities"):
        capability_source = "phoenixA_catalog_empty"

    factors = []
    summary = Counter()
    for item in factor_defs:
        availability = _build_factor_availability(item, source_status)
        summary[availability["availability_status"]] += 1
        factors.append(availability)

    return {
        "capability_source": capability_source,
        "capability_error": capabilities.get("_error") or "",
        "capability_http_status": capabilities.get("_status_code"),
        "selected_source": source or "default",
        "source_status": source_status,
        "summary": dict(summary),
        "factors": factors,
    }


def _get_catalog_capabilities(refresh: bool = False, source: str | None = None) -> Dict[str, Any]:
    client: PhoenixAClient | None = None
    runtime = _runtimes.get(_runtime_key(source))
    if runtime is not None and isinstance(runtime[1], PhoenixADataProvider):
        client = runtime[1].client
    else:
        try:
            client = _build_phoenix_client(source)
        except Exception as exc:
            logger.warning({
                "event": "factor_availability_client_unavailable",
                "source": source or "default",
                "error": str(exc),
            })
            return {"capabilities": [], "_reachable": False, "_error": str(exc)}
    return client.get_catalog_capabilities(refresh=refresh) if client else {"capabilities": [], "_reachable": False}


def _analyze_capability_sources(capabilities: Dict[str, Any]) -> Dict[str, dict]:
    reachable = _capabilities_reachable(capabilities)
    payload_present = bool(capabilities.get("capabilities"))
    default_status = "missing" if reachable and payload_present else "unknown"

    status: Dict[str, dict] = {
        key: {
            "available": False,
            "status": default_status,
            "sources": {},
            "time_range": None,
            "fields_known": [],
            "data_types": [],
            "row_count": 0,
            "notes": (["capabilities_unreachable_or_untrusted"] if default_status == "unknown" else []),
        }
        for key in ["bars", "income", "balance_sheet", "cashflow", "corporate_action"]
    }

    if not reachable or not payload_present:
        return status

    def _field_names(output_fields: List[dict]) -> List[str]:
        names: set[str] = set()
        for field in output_fields:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                continue
            names.add(name)
            if "/" in name:
                names.update(part.strip() for part in name.split("/") if part.strip())
        return sorted(names)

    def _table_has_rows(table: Dict[str, Any], data_sources: List[dict]) -> bool:
        table_row_count = int(table.get("row_count") or 0)
        if table_row_count > 0:
            return True
        if any(int(ds.get("row_count") or 0) > 0 for ds in data_sources if isinstance(ds, dict)):
            return True
        return bool(table.get("time_range"))

    def _merge(key: str, table: Dict[str, Any], type_values: List[str]) -> None:
        stats = status[key]
        data_sources = table.get("data_sources") or []
        output_fields = table.get("capability", {}).get("output_fields") or []
        time_range = table.get("time_range") or None
        table_name = str(table.get("table_name") or "")
        stats["row_count"] += int(table.get("row_count") or 0)
        for ds in data_sources:
            if not isinstance(ds, dict):
                continue
            source = str(ds.get("source") or "unknown")
            stats["sources"][source] = int(ds.get("row_count") or 0)
        if time_range:
            stats["time_range"] = time_range
        fields = _field_names(output_fields)
        if fields:
            stats["fields_known"] = sorted(set(stats["fields_known"]) | set(fields))
        if type_values:
            stats["data_types"] = sorted(set(stats["data_types"]) | set(type_values))
        if _table_has_rows(table, data_sources):
            stats["available"] = True
            stats["status"] = "ready"
        elif stats["status"] != "ready":
            stats["status"] = "empty"
        notes = set(stats.get("notes") or [])
        notes.add(f"table:{table_name}")
        stats["notes"] = sorted(notes)

    for domain in capabilities.get("capabilities", []):
        domain_name = str(domain.get("domain") or "")
        for table in domain.get("tables", []):
            table_name = str(table.get("table_name") or "")
            capability = table.get("capability") or {}
            type_values = [
                str(dt.get("type_value") or "")
                for dt in capability.get("data_types") or []
                if isinstance(dt, dict) and dt.get("type_value")
            ]

            if domain_name == "bars" or table_name.startswith("bars_"):
                _merge("bars", table, type_values)
            if table_name == "financial_statement" or any(t in {"income", "balance_sheet", "cashflow"} for t in type_values):
                for type_value in type_values:
                    if type_value in {"income", "balance_sheet", "cashflow"}:
                        _merge(type_value, table, type_values)
            if table_name == "corporate_action" or any(t in {"dividend", "right_issue", "bs_dividend"} for t in type_values):
                _merge("corporate_action", table, type_values)

    return status


def _build_factor_availability(factor_def: Dict[str, Any], source_status: Dict[str, dict]) -> Dict[str, Any]:
    required_sources = list(factor_def.get("required_data_sources") or [])
    required_fields = list(factor_def.get("required_fields") or [])

    available_sources = [source for source in required_sources if source_status.get(source, {}).get("status") == "ready"]
    missing_sources = [
        source for source in required_sources
        if source_status.get(source, {}).get("status") in {"missing", "empty"}
    ]
    unknown_sources = [source for source in required_sources if source_status.get(source, {}).get("status") == "unknown"]
    missing_fields, unknown_fields, field_notes = _evaluate_required_fields(required_fields, source_status)

    availability_status = "available"
    if missing_sources or missing_fields:
        availability_status = "partial" if available_sources else "missing"
    elif unknown_sources or unknown_fields:
        availability_status = "unknown"
    elif not required_sources and not required_fields:
        availability_status = "unknown"

    notes: List[str] = []
    if missing_sources:
        notes.append(f"missing_sources:{','.join(missing_sources)}")
    if unknown_sources:
        notes.append(f"unknown_sources:{','.join(unknown_sources)}")
    if missing_fields:
        notes.append(f"missing_required_fields:{','.join(missing_fields)}")
    if unknown_fields:
        notes.append(f"unknown_required_fields:{','.join(unknown_fields)}")
    for source in available_sources:
        stats = source_status.get(source, {})
        if not stats.get("sources") and int(stats.get("row_count") or 0) <= 0:
            notes.append(f"source_without_row_counts:{source}")
    notes.extend(field_notes)

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
        "unknown_sources": unknown_sources,
        "missing_fields": missing_fields,
        "unknown_fields": unknown_fields,
        "source_status": {source: source_status.get(source, {}) for source in required_sources},
        "provenance": factor_def.get("provenance") or {},
        "notes": notes,
    }


def _evaluate_required_fields(required_fields: List[str], source_status: Dict[str, dict]) -> tuple[List[str], List[str], List[str]]:
    missing_fields: List[str] = []
    unknown_fields: List[str] = []
    notes: List[str] = []

    for field in required_fields:
        source_key, column_name, mode = _classify_required_field(field)
        if not source_key:
            continue
        stats = source_status.get(source_key, {})
        readiness = str(stats.get("status") or "unknown")
        known_fields = set(stats.get("fields_known") or [])

        if readiness == "unknown":
            unknown_fields.append(field)
            continue
        if readiness in {"missing", "empty"}:
            missing_fields.append(field)
            continue

        if mode == "jsonb_nested":
            if column_name in known_fields:
                continue
            if "data_json" in known_fields:
                notes.append(f"field_level_unverified:{field}")
                continue
            missing_fields.append(field)
            continue

        if column_name not in known_fields:
            missing_fields.append(field)

    return missing_fields, unknown_fields, notes


def _classify_required_field(field: str) -> tuple[str, str, str]:
    parts = str(field or "").split(".")
    if len(parts) < 2:
        return "", "", ""
    root = parts[0]
    if root == "financial" and len(parts) >= 4:
        statement_type = parts[1]
        if parts[2] == "data_json":
            return statement_type, parts[-1], "jsonb_nested"
        return statement_type, parts[-1], "direct"
    if root == "bars":
        return "bars", parts[-1], "direct"
    if root == "corporate_action":
        mode = "jsonb_nested" if "data_json" in parts else "direct"
        return "corporate_action", parts[-1], mode
    return "", "", ""


def _capabilities_reachable(capabilities: Dict[str, Any]) -> bool:
    if "_reachable" in capabilities:
        return bool(capabilities.get("_reachable"))
    return bool(capabilities.get("capabilities"))


