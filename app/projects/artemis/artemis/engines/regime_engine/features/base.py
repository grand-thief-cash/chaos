"""特征计算基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseFeatureComputer(ABC):
    """Regime 特征计算器抽象基类。"""

    @abstractmethod
    def compute(self, data_bundle: Dict[str, Any]) -> Dict[str, float]:
        """从 data_bundle 计算特征子集，返回 {feature_name: value}。"""

