"""TTM (Trailing Twelve Months) 与单季度推导。

中国上市公司利润表/现金流量表报告的是年初至期末的 **累计值**：
  Q1 = Jan–Mar 累计
  Q2 = Jan–Jun 累计（半年报）
  Q3 = Jan–Sep 累计（三季报）
  Q4 = Jan–Dec 累计（年报）

TTM 公式：
  TTM = 当期累计 + 上年年报 − 上年同期累计
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def get_quarter(reporting_period: str) -> int:
    """Derive quarter (1-4) from period string like '20250930'. Returns 0 on bad input."""
    if not reporting_period or len(reporting_period) < 6:
        return 0
    try:
        month = int(reporting_period[4:6])
    except ValueError:
        return 0
    return {3: 1, 6: 2, 9: 3, 12: 4}.get(month, 0)


def get_year(reporting_period: str) -> int:
    if not reporting_period or len(reporting_period) < 4:
        return 0
    try:
        return int(reporting_period[:4])
    except ValueError:
        return 0


def get_prev_quarter_period(year: int, quarter: int) -> Optional[str]:
    """当前期的前一期 (Q3→Q2, Q1→上年Q4)。"""
    if quarter == 1:
        return f"{year - 1}1231"
    month_map = {2: "0331", 3: "0630", 4: "0930"}
    return f"{year}{month_map[quarter]}"


def make_period(year: int, quarter: int) -> str:
    month_map = {1: "0331", 2: "0630", 3: "0930", 4: "1231"}
    return f"{year}{month_map[quarter]}"


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _val(df: Optional[pd.DataFrame], period: str, field: str) -> Optional[float]:
    """Extract a single value from *df* for the given *period* and *field*.

    Returns ``None`` if the DataFrame is empty, the field/period is missing, or
    the value is NaN.
    """
    if df is None or df.empty or not period:
        return None
    if field not in df.columns:
        return None
    if "reporting_period" not in df.columns:
        return None
    # Ensure type-consistent comparison (int vs str mismatch guard)
    rp = df["reporting_period"].astype(str)
    mask = rp == str(period)
    rows = df.loc[mask, field]
    if rows.empty:
        return None
    v = rows.iloc[0]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def compute_ttm(
    reports: pd.DataFrame,
    field: str,
    current_period: str,
) -> Optional[float]:
    """计算 TTM 值。

    Args:
        reports: 含 ``reporting_period`` 列和目标 ``field`` 列的 DataFrame
        field: 要计算 TTM 的字段名
        current_period: 当前最新报告期, e.g. ``"20250930"``

    Returns:
        TTM 值, 数据不足时返回 ``None``
    """
    quarter = get_quarter(current_period)
    year = get_year(current_period)

    if quarter == 0:
        return None

    # Q4(年报) → 值就是全年
    if quarter == 4:
        return _val(reports, current_period, field)

    cur_cum = _val(reports, current_period, field)
    prev_annual = _val(reports, f"{year - 1}1231", field)
    prev_same = _val(reports, f"{year - 1}{current_period[4:]}", field)

    if cur_cum is None or prev_annual is None or prev_same is None:
        return None

    return cur_cum + prev_annual - prev_same


def compute_single_quarter(
    reports: pd.DataFrame,
    field: str,
    report_period: str,
) -> Optional[float]:
    """从累计值推导单季度值。

    Q1 = Q1累计值
    Qn = Qn累计 − Q(n−1)累计  (n=2,3,4)
    """
    quarter = get_quarter(report_period)
    year = get_year(report_period)

    if quarter == 0:
        return None

    cur_cum = _val(reports, report_period, field)
    if cur_cum is None:
        return None

    if quarter == 1:
        return cur_cum

    prev_period = get_prev_quarter_period(year, quarter)
    if prev_period is None:
        return None

    prev_cum = _val(reports, prev_period, field)
    if prev_cum is None:
        return None

    return cur_cum - prev_cum

