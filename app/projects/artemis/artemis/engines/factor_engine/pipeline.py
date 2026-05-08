"""因子计算 Pipeline 协调器。"""

from __future__ import annotations

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
from artemis.engines.factor_engine.storage.factor_store import FactorStore
from artemis.engines.factor_engine.models import FACTOR_VERSION


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
        for sym in symbols:
            fin_data = self.provider.get_financial_data(sym, as_of_date)
            mkt_data = self.provider.get_market_data(sym, as_of_date)
            period = self.provider.get_current_period(sym, as_of_date)

            sym_factors: dict = {}
            for group in self.factor_groups:
                result = group.compute(sym, fin_data, mkt_data, period)
                sym_factors.update(result)
            raw_rows[sym] = sym_factors

        raw_factors = pd.DataFrame.from_dict(raw_rows, orient="index")

        # 5. 去极值
        winsorized = raw_factors.apply(self.normalizer.winsorize_mad)

        # 6. 行业 Z‑Score
        normalized = self.normalizer.zscore_by_industry(winsorized, industry_map)

        # 7. 存储
        self.store.save_factor_snapshot(as_of_date, market, raw_factors, normalized)
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

            ind_code = industry_map.get(sym, "unknown")
            norm = self.normalizer.zscore_incremental(raw, ind_code, industry_stats)

            self.store.save_single_factor(
                symbol=sym,
                as_of_date=as_of_date,
                raw_factors=raw,
                norm_factors=norm,
                meta={"incremental": True, "version": FACTOR_VERSION, "industry_code": ind_code},
                market=market,
            )

