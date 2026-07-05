from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NormalizedDimensions(BaseModel):
    """归一化后的 Workbench 数据维度。"""

    asset_type: str
    market: str
    period: str
    adjust: str


def normalize_dimensions(
    *,
    asset_type: str,
    market: str,
    period: str,
    adjust: str | None,
) -> NormalizedDimensions:
    """归一化 Workbench 查询维度。

    规则：
    - 内部统一使用 period
    - index 不展示 adjust，但内部固定归一化为 nf
    - 非 index 场景 adjust 不能为空
    """

    normalized_asset_type = (asset_type or "").strip()
    normalized_market = (market or "").strip()
    normalized_period = (period or "").strip()
    normalized_adjust = (adjust or "").strip()

    if not normalized_asset_type:
        raise ValueError("asset_type is required")
    if not normalized_market:
        raise ValueError("market is required")
    if not normalized_period:
        raise ValueError("period is required")

    if normalized_asset_type == "index":
        normalized_adjust = "nf"
    elif not normalized_adjust:
        raise ValueError(f"adjust is required for asset_type={normalized_asset_type}")

    return NormalizedDimensions(
        asset_type=normalized_asset_type,
        market=normalized_market,
        period=normalized_period,
        adjust=normalized_adjust,
    )


class MarketDataQuery(BaseModel):
    """Workbench 市场数据查询语义对象。"""

    security_id: int
    symbol: Optional[str] = None
    start_date: str
    end_date: str
    asset_type: str = "stock"
    market: str = "zh_a"
    period: str = "daily"
    adjust: str = "nf"
    source: Optional[str] = None
    use_cache: bool = True


class IndicatorReq(BaseModel):
    """单个指标请求。"""

    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class IndicatorsRequest(BaseModel):
    """指标计算请求。"""

    security_id: int
    start_date: str
    end_date: str
    period: str = "daily"
    adjust: str = "nf"
    asset_type: str = "stock"
    market: str = "zh_a"
    indicators: List[IndicatorReq]
    source: Optional[str] = None


class CompactRequest(BaseModel):
    """缓存 Compaction 请求（cache_engine 物理 symbol-keyed，§3.2 永久存储特例）。"""

    symbol: str
    period: str = "daily"
    asset_type: str = "stock"
    market: str = "zh_a"
    adjust: str = "nf"
