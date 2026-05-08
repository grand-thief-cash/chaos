"""因子注册表 — 所有因子的元数据中心。"""

from __future__ import annotations

from typing import Dict, List

from artemis.engines.factor_engine.models import FactorMeta

# Global factor registry: name → FactorMeta
FACTOR_REGISTRY: Dict[str, FactorMeta] = {}


def register_factor(meta: FactorMeta) -> None:
    """注册一个因子到全局注册表。"""
    FACTOR_REGISTRY[meta.name] = meta


def list_factors() -> List[Dict]:
    """以 JSON-friendly 格式返回所有已注册因子。"""
    return [
        {
            "name": m.name,
            "cn_name": m.cn_name,
            "category": m.category.value,
            "formula": m.formula,
            "unit": m.unit,
            "higher_is_better": m.higher_is_better,
            "requires_market_data": m.requires_market_data,
            "exclude_financial": m.exclude_financial,
        }
        for m in FACTOR_REGISTRY.values()
    ]

