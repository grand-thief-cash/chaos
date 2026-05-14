"""因子计算 Pipeline 协调器。"""

from __future__ import annotations

from typing import Any
from typing import Dict, List, Optional, Protocol

import pandas as pd

from artemis.engines.factor_engine.factors.base import BaseFactor
from artemis.engines.factor_engine.factors.profitability import ProfitabilityFactors
from artemis.engines.factor_engine.factors.growth import GrowthFactors
from artemis.engines.factor_engine.factors.quality import QualityFactors
from artemis.engines.factor_engine.factors.solvency import SolvencyFactors
from artemis.engines.factor_engine.factors.valuation import ValuationFactors
from artemis.engines.factor_engine.factors.efficiency import EfficiencyFactors
from artemis.engines.factor_engine.factors.per_share import PerShareFactors
from artemis.engines.factor_engine.normalizer import FactorNormalizer
from artemis.engines.factor_engine.registry import FACTOR_REGISTRY, get_factor_definition
from artemis.engines.factor_engine.storage.factor_store import FactorStore
from artemis.engines.factor_engine.models import FACTOR_VERSION, FactorFreshness


# ---------------------------------------------------------------------------
# Data provider protocol — 可替换为 PhoenixA 实现
# ---------------------------------------------------------------------------

class FactorDataProvider(Protocol):
    """因子数据源协议，MVP 可用 Mock 实现。"""

    def get_active_symbols(self, market: str, as_of_date: str) -> List[str]: ...

    def get_industry_map(self, taxonomy: str, market: str) -> Dict[str, str]: ...

    def get_financial_data(
        self, symbol: str, as_of_date: str,
    ) -> Dict[str, pd.DataFrame]:
        """返回 {statement_type: DataFrame}，已做 PIT 过滤。"""
        ...

    def get_market_data(self, symbol: str, as_of_date: str) -> Optional[pd.DataFrame]: ...

    def get_current_period(self, symbol: str, as_of_date: str) -> Optional[str]: ...


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
    _FINANCIAL_INDUSTRY_PREFIXES = ("80178", "80179", "80101", "80100")

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

        # 1. 获取活跃股票列表
        symbols = self.provider.get_active_symbols(market, as_of_date)
        if not symbols:
            return pd.DataFrame()

        # 2. 行业映射
        industry_map = self.provider.get_industry_map("sw_l1", market)

        # 3‑4. 计算原始因子
        raw_rows: Dict[str, dict] = {}
        snapshot_meta: Dict[str, dict] = {}
        for sym in symbols:
            fin_data = self.provider.get_financial_data(sym, as_of_date)
            mkt_data = self.provider.get_market_data(sym, as_of_date)
            period = self.provider.get_current_period(sym, as_of_date)

            sym_factors: dict = {}
            for group in self.factor_groups:
                result = group.compute(sym, fin_data, mkt_data, period)
                sym_factors.update(result)
            self._apply_factor_policies(sym_factors, fin_data, industry_map.get(sym))
            raw_rows[sym] = sym_factors
            snapshot_meta[sym] = self._build_snapshot_meta(sym_factors, fin_data, mkt_data, period, as_of_date, industry_map.get(sym))

        raw_factors = pd.DataFrame.from_dict(raw_rows, orient="index")

        # 5. 去极值
        winsorized = raw_factors.apply(self.normalizer.winsorize_mad)

        # 6. 行业 Z‑Score
        normalized = self.normalizer.zscore_by_industry(winsorized, industry_map)

        # 7. 存储
        self.store.save_factor_snapshot(as_of_date, market, raw_factors, normalized, snapshot_meta)
        self.store.save_industry_stats(
            as_of_date, market, self.normalizer.get_industry_stats(),
        )

        return normalized

    def run_incremental(
        self,
        symbols: List[str],
        as_of_date: str,
        market: str = "zh_a",
    ) -> None:
        """增量计算指定股票。"""
        industry_stats = self.store.load_industry_stats(as_of_date, market)
        if industry_stats is None:
            # 没有历史统计量 → 降级全量
            self.run_full(as_of_date, market)
            return

        industry_map = self.provider.get_industry_map("sw_l1", market)

        for sym in symbols:
            fin_data = self.provider.get_financial_data(sym, as_of_date)
            mkt_data = self.provider.get_market_data(sym, as_of_date)
            period = self.provider.get_current_period(sym, as_of_date)

            raw: dict = {}
            for group in self.factor_groups:
                raw.update(group.compute(sym, fin_data, mkt_data, period))
            self._apply_factor_policies(raw, fin_data, industry_map.get(sym))

            ind_code = industry_map.get(sym, "unknown")
            norm = self.normalizer.zscore_incremental(raw, ind_code, industry_stats)
            snapshot_meta = self._build_snapshot_meta(raw, fin_data, mkt_data, period, as_of_date, ind_code)

            self.store.save_single_factor(
                symbol=sym,
                as_of_date=as_of_date,
                raw_factors=raw,
                norm_factors=norm,
                meta={**snapshot_meta, "incremental": True},
                market=market,
            )

    @staticmethod
    def _apply_factor_policies(
        factor_values: Dict[str, Optional[float]],
        financial_data: Dict[str, pd.DataFrame],
        industry_code: Optional[str],
    ) -> None:
        company_kind = FactorPipeline._financial_company_kind(financial_data, industry_code)
        if company_kind is None:
            return
        for factor_name, meta in FACTOR_REGISTRY.items():
            if meta.exclude_financial and factor_name in factor_values:
                factor_values[factor_name] = None

    @staticmethod
    def _financial_company_kind(
        financial_data: Dict[str, pd.DataFrame],
        industry_code: Optional[str],
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

        if not industry_code:
            return None
        if str(industry_code).startswith(FactorPipeline._FINANCIAL_INDUSTRY_PREFIXES):
            return "financial"
        return None

    @staticmethod
    def _is_financial_company(
        financial_data: Dict[str, pd.DataFrame],
        industry_code: Optional[str],
    ) -> bool:
        return FactorPipeline._financial_company_kind(financial_data, industry_code) is not None

    @staticmethod
    def _build_snapshot_meta(
        factor_values: Dict[str, Optional[float]],
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame],
        current_period: Optional[str],
        as_of_date: str,
        industry_code: Optional[str],
    ) -> Dict[str, Any]:
        company_kind = FactorPipeline._financial_company_kind(financial_data, industry_code)
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

