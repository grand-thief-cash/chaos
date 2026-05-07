"""指标计算入口，调 ta 库计算指标并转为 JSON。"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from artemis.engines.indicator_engine.registry import INDICATOR_REGISTRY
from artemis.log.logger import get_logger

logger = get_logger("indicator_engine.calculator")


def compute_indicators(
    df: pd.DataFrame,
    indicator_requests: List[Dict[str, Any]],
) -> tuple[Dict[str, list], Dict[str, Dict[str, Any]]]:
    """批量计算指标。

    Args:
        df: OHLCV 数据（至少含 open/high/low/close/volume 列）
        indicator_requests: [{"name": "sma", "params": {"period": 10}}, ...]

    Returns:
        (indicator_series, indicator_meta)
        - indicator_series: {series_key: [values]}，values 长度与 df 一致
        - indicator_meta: {series_key: {type, color, overlay, y_axis?}}
    """
    all_series: Dict[str, list] = {}
    all_meta: Dict[str, Dict[str, Any]] = {}

    for req in indicator_requests:
        name = req.get("name", "")
        spec = INDICATOR_REGISTRY.get(name)
        if spec is None:
            logger.warning({"event": "unknown_indicator", "name": name})
            continue

        # 合并默认参数和用户参数
        params = {**spec.default_params, **req.get("params", {})}

        try:
            result = spec.calculate(df, **params)
        except Exception as e:
            logger.error({"event": "indicator_calc_failed", "name": name, "error": str(e)}, exc_info=True)
            continue

        # 为每个输出序列生成渲染元信息
        for series_key in result:
            meta: Dict[str, Any] = {
                "overlay": spec.overlay,
            }
            # 匹配 series_meta 模板
            for pattern, template_meta in spec.series_meta.items():
                # pattern 如 "sma_{period}"，尝试格式化看是否匹配
                try:
                    expected_key = pattern.format(**params)
                    if expected_key == series_key:
                        meta.update(template_meta)
                        break
                except KeyError:
                    continue

            if spec.y_axis:
                meta["y_axis"] = spec.y_axis

            all_series[series_key] = result[series_key]
            all_meta[series_key] = meta

    return all_series, all_meta
