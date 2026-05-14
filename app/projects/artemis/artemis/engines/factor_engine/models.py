"""因子引擎数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class FactorCategory(str, Enum):
    """因子分类。"""
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    QUALITY = "quality"
    SOLVENCY = "solvency"
    VALUATION = "valuation"
    EFFICIENCY = "efficiency"
    PER_SHARE = "per_share"


@dataclass(frozen=True)
class FactorMeta:
    """因子元数据 — 描述一个因子的身份、公式和属性。"""
    name: str                                   # 英文标识 e.g. "roe"
    cn_name: str                                # 中文名 e.g. "净资产收益率"
    category: FactorCategory                    # 所属分类
    formula: str                                # 公式描述 (人类可读)
    data_sources: tuple[str, ...] = ()          # 依赖数据源 ("income", "balance_sheet", ...)
    requires_market_data: bool = False          # 是否需要行情数据
    higher_is_better: bool = True              # 排序方向 (因子评分用)
    ttm_required: bool = False                 # 利润表/现金流类是否需要 TTM
    unit: str = ""                             # 单位 "%", "倍", "天"
    exclude_financial: bool = False            # 是否排除金融行业
    min_history_quarters: int = 4              # 至少需要多少季度历史数据


@dataclass
class FactorFreshness:
    """因子数据新鲜度评估。"""
    latest_reporting_period: str               # 最新可用报告期 e.g. "20250630"
    latest_ann_date: str                        # 最新披露日期
    as_of_date: str                             # 因子计算基准日
    staleness_days: int = 0                     # as_of_date - latest_ann_date 的天数差

    @property
    def freshness_score(self) -> float:
        """新鲜度评分 (0.0–1.0)。"""
        if self.staleness_days <= 30:
            return 1.0
        elif self.staleness_days <= 120:
            return 0.8
        elif self.staleness_days <= 210:
            return 0.5
        return 0.3

    @property
    def freshness_label(self) -> str:
        if self.staleness_days <= 30:
            return "fresh"
        elif self.staleness_days <= 120:
            return "acceptable"
        elif self.staleness_days <= 210:
            return "stale"
        return "very_stale"

    def to_dict(self) -> Dict[str, object]:
        return {
            "latest_reporting_period": self.latest_reporting_period,
            "latest_ann_date": self.latest_ann_date,
            "as_of_date": self.as_of_date,
            "staleness_days": self.staleness_days,
            "freshness_score": self.freshness_score,
            "freshness_label": self.freshness_label,
        }

    @classmethod
    def from_dates(
        cls,
        *,
        latest_reporting_period: str,
        latest_ann_date: str,
        as_of_date: str,
    ) -> "FactorFreshness":
        staleness_days = 0
        try:
            if latest_ann_date and as_of_date:
                ann_dt = datetime.strptime(latest_ann_date, "%Y%m%d")
                as_of_dt = datetime.strptime(as_of_date, "%Y%m%d")
                staleness_days = max((as_of_dt - ann_dt).days, 0)
        except ValueError:
            staleness_days = 0
        return cls(
            latest_reporting_period=latest_reporting_period,
            latest_ann_date=latest_ann_date,
            as_of_date=as_of_date,
            staleness_days=staleness_days,
        )


# ---------------------------------------------------------------------------
# Version tracking
# ---------------------------------------------------------------------------
FACTOR_VERSION = "v1.0"

