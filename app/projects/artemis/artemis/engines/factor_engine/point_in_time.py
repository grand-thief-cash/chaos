"""Point-in-Time (PIT) 时间对齐 — 避免未来函数。"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def get_latest_available_reports(
    all_reports: pd.DataFrame,
    as_of_date: str,
) -> pd.DataFrame:
    """获取截至 *as_of_date* 已公开披露的所有报表。

    Logic:
      1. 按 ``ann_date <= as_of_date`` 过滤（排除未来数据）
      2. 按 ``(reporting_period, statement_type)`` 去重，取 ``ann_date`` 最大（最新修订/更正）
      3. 按 ``reporting_period`` 降序排列

    Args:
        all_reports: 含 ``ann_date``, ``reporting_period`` 和可选 ``statement_type`` 列
        as_of_date: PIT 基准日 YYYYMMDD 格式

    Returns:
        过滤 + 去重后的报表 DataFrame
    """
    if all_reports is None or all_reports.empty:
        return pd.DataFrame()

    df = all_reports.copy()

    # 确保 ann_date 字段存在
    if "ann_date" not in df.columns:
        return df

    # 1. 排除尚未披露的数据
    df = df[df["ann_date"] <= as_of_date]
    if df.empty:
        return df

    # 2. 去重：同一期可能多次披露 (业绩预告→快报→正式→修订)
    group_cols = ["reporting_period"]
    if "statement_type" in df.columns:
        group_cols.append("statement_type")

    idx = df.groupby(group_cols)["ann_date"].idxmax()
    df = df.loc[idx]

    # 3. 排序
    df = df.sort_values("reporting_period", ascending=False).reset_index(drop=True)
    return df


def get_latest_period(reports: pd.DataFrame) -> Optional[str]:
    """从 PIT‑filtered 报表中取最新 reporting_period。"""
    if reports is None or reports.empty:
        return None
    return str(reports["reporting_period"].iloc[0])

