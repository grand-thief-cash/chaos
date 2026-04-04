from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WorkbenchRunReq(BaseModel):
    """Workbench 回测运行请求。"""
    strategy_code: str
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "daily"
    adjust: str = "nf"
    cash: float = 100000.0
    commission: float = 0.0
    strategy_params: Dict[str, Any] = {}


class IndicatorReq(BaseModel):
    """单个指标请求。"""
    name: str
    params: Dict[str, Any] = {}


class IndicatorsRequest(BaseModel):
    """指标计算请求。"""
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "daily"
    adjust: str = "nf"
    indicators: List[IndicatorReq]
