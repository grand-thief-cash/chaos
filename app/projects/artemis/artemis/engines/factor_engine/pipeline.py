"""因子计算 Pipeline 协调器。"""

from __future__ import annotations

from typing import Any
from typing import Dict, List, Optional, Protocol

import pandas as pd

from artemis.consts.task_params import ADJUST_BACKWARD, ADJUST_FORWARD, ADJUST_NONE
from artemis.engines.factor_engine.factors.base import BaseFactor
from artemis.engines.factor_engine.factors.profitability import ProfitabilityFactors
from artemis.engines.factor_engine.factors.growth import GrowthFactors
from artemis.engines.factor_engine.factors.quality import QualityFactors
from artemis.engines.factor_engine.factors.solvency import SolvencyFactors
from artemis.engines.factor_engine.factors.valuation import ValuationFactors
from artemis.engines.factor_engine.factors.efficiency import EfficiencyFactors
from artemis.engines.factor_engine.factors.per_share import PerShareFactors
from artemis.engines.factor_engine.normalizer import FactorNormalizer
from artemis.engines.factor_engine.registry import FACTOR_REGISTRY, get_factor_definition, get_factor_market_adjust_policy
from artemis.engines.factor_engine.storage.factor_store import FactorStore
from artemis.engines.factor_engine.models import FACTOR_VERSION, FactorFreshness


# ---------------------------------------------------------------------------
# Data provider protocol — 可替换为 PhoenixA 实现
# ---------------------------------------------------------------------------

class FactorDataProvider(Protocol):
    """因子数据源协议，MVP 可用 Mock 实现。

    Phase 4: identity is security_id throughout (refactor §3.6 / §10.c).
    """

    def get_active_securities(self, market: str, as_of_date: str) -> Dict[int, Dict[str, Any]]:
        """Return {security_id -> security info ({symbol, exchange, ...})} active as of date."""
        ...

    def get_industry_map(
        self,
        taxonomy: str,
        market: str,
        use_batch: bool = True,
        security_ids: Optional[List[int]] = None,
    ) -> Dict[int, str]: ...

    def get_industry_context(self, security_id: int, taxonomy: str, market: str) -> Dict[str, Any]: ...

    def get_financial_data(
        self, security_id: int, as_of_date: str,
    ) -> Dict[str, pd.DataFrame]:
        """返回 {statement_type: DataFrame}，已做 PIT 过滤。"""
        ...

    def get_market_data(self, security_id: int, as_of_date: str, adjust: Optional[str] = None) -> Optional[pd.DataFrame]: ...

    def get_current_period(self, security_id: int, as_of_date: str) -> Optional[str]: ...


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class FactorPipeline:
    """因子计算全流程。"""

    _FINANCIAL_COMPANY_TYPES = {
        2: "bank",
        3: "insurance",
        4: "broker",
    }
    _SUPPORTED_MARKET_ADJUSTS = {ADJUST_NONE, ADJUST_FORWARD, ADJUST_BACKWARD}

    def __init__(
        self,
        data_provider: FactorDataProvider,
        store: Optional[FactorStore] = None,
    ) -> None:
        self.provider = data_provider
        self.store = store or FactorStore()
        self.normalizer = FactorNormalizer()

        self.factor_groups: List[BaseFactor] = [
            ProfitabilityFactors(),
            GrowthFactors(),
            QualityFactors(),
            SolvencyFactors(),
            ValuationFactors(),
            EfficiencyFactors(),
            PerShareFactors(),
        ]

    def run_full(self, as_of_date: str, market: str = "zh_a") -> pd.DataFrame:
        """全量因子计算。"""

        from artemis.log.logger import get_logger
        logger = get_logger("factor_pipeline")

        # 1. 获取活跃股票列表 (security_id → info)
        securities = self.provider.get_active_securities(market, as_of_date)
        if not securities:
            logger.warning({"event": "factor_pipeline_no_symbols", "market": market, "as_of_date": as_of_date})
            return pd.DataFrame()

        # 2. 行业映射 - 使用批量查询优化性能
        taxonomy = "sw_l1"
        try:
            industry_map = self.provider.get_industry_map(taxonomy, market, True, None)
        except Exception as e:
            logger.error({"event": "factor_pipeline_industry_map_failed", "error": str(e)})
            return pd.DataFrame()

        # 3‑4. 计算原始因子
        raw_rows: Dict[int, dict] = {}
        snapshot_meta: Dict[int, dict] = {}
        failed_securities = []

        for sec_id, sec_info in securities.items():
            symbol = sec_info.get("symbol", "")
            try:
                fin_data = self.provider.get_financial_data(sec_id, as_of_date)
                period = self.provider.get_current_period(sec_id, as_of_date)
                industry_context = self.provider.get_industry_context(sec_id, taxonomy, market)
                market_data_cache: Dict[str, Optional[pd.DataFrame]] = {}
                primary_market_data: Optional[pd.DataFrame] = None

                sym_factors: dict = {}
                for group in self.factor_groups:
                    try:
                        mkt_data = self._market_data_for_group(group, sec_id, as_of_date, market_data_cache)
                        if primary_market_data is None and mkt_data is not None:
                            primary_market_data = mkt_data
                        result = group.compute(sec_id, fin_data, mkt_data, period)
                        sym_factors.update(result)
                    except ValueError as e:
                        # Re-raise configuration errors
                        raise
                    except Exception as e:
                        logger.warning({
                            "event": "factor_group_compute_failed",
                            "security_id": sec_id,
                            "group": group.__class__.__name__,
                            "error": str(e),
                        })
                self._apply_factor_policies(sym_factors, fin_data, industry_context)
                raw_rows[sec_id] = sym_factors
                meta = self._build_snapshot_meta(sym_factors, fin_data, primary_market_data, period, as_of_date, industry_map.get(sec_id), industry_context)
                meta["symbol"] = symbol
                snapshot_meta[sec_id] = meta
            except ValueError as e:
                # Re-raise configuration errors
                raise
            except Exception as e:
                logger.error({
                    "event": "factor_compute_symbol_failed",
                    "security_id": sec_id,
                    "error": str(e),
                })
                failed_securities.append(sec_id)

        raw_factors = pd.DataFrame.from_dict(raw_rows, orient="index")

        # 5. 去极值
        try:
            winsorized = raw_factors.apply(self.normalizer.winsorize_mad)
        except Exception as e:
            logger.error({"event": "factor_pipeline_winsorize_failed", "error": str(e)})
            winsorized = raw_factors

        # 6. 行业 Z‑Score
        try:
            normalized = self.normalizer.zscore_by_industry(winsorized, industry_map)
        except Exception as e:
            logger.error({"event": "factor_pipeline_normalize_failed", "error": str(e)})
            normalized = winsorized

        # 7. 存储
        try:
            self.store.save_factor_snapshot(as_of_date, market, raw_factors, normalized, snapshot_meta)
            self.store.save_industry_stats(
                as_of_date, market, self.normalizer.get_industry_stats(),
            )
        except Exception as e:
            logger.error({
                "event": "factor_pipeline_storage_failed",
                "error": str(e),
                "securities_count": len(securities),
            })

        logger.info({
            "event": "factor_pipeline_completed",
            "as_of_date": as_of_date,
            "market": market,
            "total_securities": len(securities),
            "failed_count": len(failed_securities),
        })

        return normalized

    def run_incremental(
        self,
        security_ids: List[int],
        as_of_date: str,
        market: str = "zh_a",
    ) -> None:
        """增量计算指定股票。"""
        from artemis.log.logger import get_logger
        logger = get_logger("factor_pipeline_incremental")

        industry_stats = self.store.load_industry_stats(as_of_date, market)
        if industry_stats is None:
            # 没有历史统计量 → 降级全量
            logger.warning({
                "event": "incremental_no_history_stats",
                "securities_count": len(security_ids),
                "action": "downgrade_to_full",
            })
            self.run_full(as_of_date, market)
            return

        taxonomy = "sw_l1"
        try:
            industry_map = self.provider.get_industry_map(taxonomy, market, True, security_ids)
        except Exception as e:
            logger.error({
                "event": "factor_pipeline_industry_map_batch_failed",
                "securities_count": len(security_ids),
                "error": str(e),
            })
            return
        # symbol decoration for snapshot meta (cached; may miss ids not in the active map)
        securities = self.provider.get_active_securities(market, as_of_date)
        failed_securities = []

        for sec_id in security_ids:
            symbol = securities.get(sec_id, {}).get("symbol", "")
            try:
                fin_data = self.provider.get_financial_data(sec_id, as_of_date)
                period = self.provider.get_current_period(sec_id, as_of_date)
                industry_context = self.provider.get_industry_context(sec_id, taxonomy, market)
                market_data_cache: Dict[str, Optional[pd.DataFrame]] = {}
                primary_market_data: Optional[pd.DataFrame] = None

                raw: dict = {}
                for group in self.factor_groups:
                    try:
                        mkt_data = self._market_data_for_group(group, sec_id, as_of_date, market_data_cache)
                        if primary_market_data is None and mkt_data is not None:
                            primary_market_data = mkt_data
                        result = group.compute(sec_id, fin_data, mkt_data, period)
                        raw.update(result)
                    except Exception as e:
                        logger.warning({
                            "event": "factor_group_compute_failed",
                            "security_id": sec_id,
                            "group": group.__class__.__name__,
                            "error": str(e),
                        })
                self._apply_factor_policies(raw, fin_data, industry_context)

                ind_code = industry_map.get(sec_id, "unknown")
                norm = self.normalizer.zscore_incremental(raw, ind_code, industry_stats)
                meta = self._build_snapshot_meta(raw, fin_data, primary_market_data, period, as_of_date, ind_code, industry_context)
                meta["symbol"] = symbol
                meta["incremental"] = True

                self.store.save_single_factor(
                    security_id=sec_id,
                    as_of_date=as_of_date,
                    raw_factors=raw,
                    norm_factors=norm,
                    meta=meta,
                    market=market,
                )
            except Exception as e:
                logger.error({
                    "event": "incremental_compute_symbol_failed",
                    "security_id": sec_id,
                    "error": str(e),
                    "traceback": logger.format_exc() if hasattr(logger, 'format_exc') else None,
                })
                failed_securities.append(sec_id)

        logger.info({
            "event": "incremental_pipeline_completed",
            "as_of_date": as_of_date,
            "market": market,
            "total_securities": len(security_ids),
            "failed_count": len(failed_securities),
            "batch_industry_map_used": True,
        })

    def _market_data_for_group(
        self,
        group: BaseFactor,
        security_id: int,
        as_of_date: str,
        market_data_cache: Dict[str, Optional[pd.DataFrame]],
    ) -> Optional[pd.DataFrame]:
        adjust = self._market_adjust_for_group(group)
        if adjust is None:
            return None
        if adjust not in market_data_cache:
            market_data_cache[adjust] = self.provider.get_market_data(security_id, as_of_date, adjust=adjust)
        return market_data_cache[adjust]

    def _market_adjust_for_group(self, group: BaseFactor) -> Optional[str]:
        metas = list(group.factor_metas() or [])
        if not any(meta.requires_market_data for meta in metas):
            return None

        adjusts = set()
        for meta in metas:
            if not meta.requires_market_data:
                continue
            resolved = self._market_adjust_for_factor(meta)
            adjusts.add(resolved)

        if len(adjusts) != 1:
            raise ValueError(f"mixed market_adjust_policy detected in factor group: {sorted(adjusts)}")
        return next(iter(adjusts))

    def _market_adjust_for_factor(self, meta) -> str:
        catalog_policy = get_factor_market_adjust_policy(meta.name)
        factor_policy_adjust = self._normalize_market_adjust(catalog_policy.get("adjust"))
        if not factor_policy_adjust:
            raise ValueError(f"factor {meta.name} requires market data but has no explicit market_adjust_policy.adjust in factor catalog")
        return factor_policy_adjust


    @classmethod
    def _normalize_market_adjust(cls, value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip().lower()
        if normalized in cls._SUPPORTED_MARKET_ADJUSTS:
            return normalized
        return None

    @staticmethod
    def _apply_factor_policies(
        factor_values: Dict[str, Optional[float]],
        financial_data: Dict[str, pd.DataFrame],
        industry_context: Optional[Dict[str, Any]],
    ) -> None:
        company_kind = FactorPipeline._financial_company_kind(financial_data, industry_context)
        if company_kind is None:
            return
        for factor_name, meta in FACTOR_REGISTRY.items():
            if meta.exclude_financial and factor_name in factor_values:
                factor_values[factor_name] = None

    @staticmethod
    def _financial_company_kind(
        financial_data: Dict[str, pd.DataFrame],
        industry_context: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        for df in financial_data.values():
            if df is None or df.empty or "comp_type_code" not in df.columns:
                continue
            series = df["comp_type_code"].dropna()
            if not series.empty:
                try:
                    comp_type_code = int(series.iloc[0])
                    if comp_type_code in FactorPipeline._FINANCIAL_COMPANY_TYPES:
                        return FactorPipeline._FINANCIAL_COMPANY_TYPES[comp_type_code]
                except (TypeError, ValueError):
                    pass

        flags = (industry_context or {}).get("derived_flags") or {}
        if not isinstance(flags, dict):
            flags = {}
        if not flags.get("financial_sector"):
            return None
        return "financial"

    @staticmethod
    def _is_financial_company(
        financial_data: Dict[str, pd.DataFrame],
        industry_context: Optional[Dict[str, Any]],
    ) -> bool:
        return FactorPipeline._financial_company_kind(financial_data, industry_context) is not None

    @staticmethod
    def _build_snapshot_meta(
        factor_values: Dict[str, Optional[float]],
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame],
        current_period: Optional[str],
        as_of_date: str,
        industry_code: Optional[str],
        industry_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        company_kind = FactorPipeline._financial_company_kind(financial_data, industry_context)
        latest_ann_date = FactorPipeline._latest_ann_date(financial_data)
        period = current_period or ""
        freshness = FactorFreshness.from_dates(
            latest_reporting_period=period,
            latest_ann_date=latest_ann_date,
            as_of_date=as_of_date,
        ).to_dict()
        missing_reasons = FactorPipeline._build_missing_reasons(
            factor_values,
            financial_data,
            market_data,
            period,
            company_kind,
        )
        return {
            "version": FACTOR_VERSION,
            "industry_code": industry_code or "unknown",
            "industry_flags": ((industry_context or {}).get("derived_flags") or {}),
            "company_kind": company_kind or "non_financial",
            "reporting_period": period,
            "latest_ann_date": latest_ann_date,
            "freshness": freshness,
            "missing_reasons": missing_reasons,
        }

    @staticmethod
    def _latest_ann_date(financial_data: Dict[str, pd.DataFrame]) -> str:
        latest = ""
        for df in financial_data.values():
            if df is None or df.empty or "ann_date" not in df.columns:
                continue
            series = df["ann_date"].dropna().astype(str)
            if series.empty:
                continue
            latest = max(latest, max(series))
        return latest

    @staticmethod
    def _build_missing_reasons(
        factor_values: Dict[str, Optional[float]],
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame],
        current_period: str,
        company_kind: Optional[str],
    ) -> Dict[str, str]:
        reasons: Dict[str, str] = {}
        market_missing = market_data is None or market_data.empty
        available_quarters = {
            source: int(len(df.index))
            for source, df in financial_data.items()
            if df is not None
        }

        for factor_name, meta in FACTOR_REGISTRY.items():
            if factor_values.get(factor_name) is not None:
                continue
            factor_def = get_factor_definition(factor_name) or {}
            if company_kind and meta.exclude_financial:
                reasons[factor_name] = f"excluded_for_{company_kind}"
                continue
            if meta.requires_market_data and market_missing:
                reasons[factor_name] = "missing_market_data_frame"
                continue
            if not current_period:
                reasons[factor_name] = "missing_reporting_period"
                continue

            required_data_sources = factor_def.get("required_data_sources") or list(meta.data_sources)
            missing_sources = [
                source
                for source in required_data_sources
                if source in financial_data and (financial_data.get(source) is None or financial_data.get(source).empty)
            ]
            if missing_sources:
                reasons[factor_name] = f"missing_required_sources:{','.join(missing_sources)}"
                continue

            field_reason = FactorPipeline._detect_required_field_gap(
                factor_def,
                financial_data,
                market_data,
            )
            if field_reason:
                reasons[factor_name] = field_reason
                continue

            source_history = [available_quarters.get(source, 0) for source in meta.data_sources] or [0]
            if min(source_history) < meta.min_history_quarters:
                reasons[factor_name] = f"insufficient_history_quarters:{min(source_history)}/{meta.min_history_quarters}"
                continue

            if meta.ttm_required:
                reasons[factor_name] = "ttm_formula_unavailable"
            else:
                reasons[factor_name] = "formula_returned_none"

        return reasons

    @staticmethod
    def _detect_required_field_gap(
        factor_def: Dict[str, Any],
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame],
    ) -> Optional[str]:
        for field in factor_def.get("required_fields") or []:
            field = str(field)
            if field.startswith("financial."):
                parts = field.split(".")
                if len(parts) < 4:
                    continue
                statement_type = parts[1]
                column = parts[-1]
                df = financial_data.get(statement_type)
                if df is None or df.empty:
                    return f"missing_required_source:{statement_type}"
                if column not in df.columns:
                    return f"missing_required_field:{statement_type}.{column}"
            elif field.startswith("bars."):
                column = field.split(".")[-1]
                if market_data is None or market_data.empty:
                    return "missing_market_data_frame"
                if column not in market_data.columns:
                    return f"missing_required_field:bars.{column}"
            elif field.startswith("corporate_action."):
                if market_data is None or market_data.empty:
                    return "missing_market_enrichment:dividend"
                if "dps" not in market_data.columns:
                    return "missing_market_enrichment:dps"
        return None

