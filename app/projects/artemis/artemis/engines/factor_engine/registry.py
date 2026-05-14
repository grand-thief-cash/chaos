"""因子注册表 — 所有因子的元数据中心。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import yaml

from artemis.engines.factor_engine.models import FactorMeta

# Global factor registry: name → FactorMeta
FACTOR_REGISTRY: Dict[str, FactorMeta] = {}


def _catalog_root() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "factor_catalog"


@lru_cache(maxsize=1)
def _load_factor_catalog() -> tuple[str, Dict[str, dict]]:
    root = _catalog_root()
    manifest_path = root / "manifest.yaml"
    if not manifest_path.exists():
        return "", {}

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    factor_files = manifest.get("factor_files") or []
    defaults = manifest.get("defaults") or {}
    version = str(manifest.get("catalog_version") or "")
    catalog: Dict[str, dict] = {}

    for rel_path in factor_files:
        factor_file = root / str(rel_path)
        if not factor_file.exists():
            continue
        payload = yaml.safe_load(factor_file.read_text(encoding="utf-8")) or {}
        items = payload.get("factors") if isinstance(payload, dict) else None
        if items is None and isinstance(payload, dict) and payload.get("name"):
            items = [payload]
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            merged = dict(defaults)
            merged.update(item)
            catalog[name] = merged

    return version, catalog


def register_factor(meta: FactorMeta) -> None:
    """注册一个因子到全局注册表。"""
    FACTOR_REGISTRY[meta.name] = meta


def get_factor_meta(name: str) -> FactorMeta | None:
    """按名称获取单个因子元数据。"""
    return FACTOR_REGISTRY.get(name)


def _required_data_sources(meta: FactorMeta, catalog_item: dict) -> List[str]:
    required = list(catalog_item.get("required_data_sources") or meta.data_sources)
    if meta.requires_market_data and "bars" not in required:
        required.append("bars")
    return required


def _serialize_factor_meta(meta: FactorMeta, catalog_version: str, catalog_item: dict) -> Dict:
    source_fields = list(catalog_item.get("source_fields") or [])
    required_fields = list(catalog_item.get("required_fields") or source_fields)
    provenance = catalog_item.get("provenance") or {
        "source_fields": source_fields,
        "phoenix_queries": list(catalog_item.get("phoenix_queries") or []),
        "required_data_sources": _required_data_sources(meta, catalog_item),
    }
    return {
        "name": meta.name,
        "cn_name": meta.cn_name,
        "category": meta.category.value,
        "formula": meta.formula,
        "unit": meta.unit,
        "data_sources": list(meta.data_sources),
        "higher_is_better": meta.higher_is_better,
        "requires_market_data": meta.requires_market_data,
        "exclude_financial": meta.exclude_financial,
        "ttm_required": meta.ttm_required,
        "min_history_quarters": meta.min_history_quarters,
        "required_data_sources": _required_data_sources(meta, catalog_item),
        "required_fields": required_fields,
        "provenance": provenance,
        "catalog_version": catalog_version,
        "catalog_seeded": meta.name in _load_factor_catalog()[1],
        **{k: v for k, v in catalog_item.items() if k != "name"},
    }


def get_factor_definition(name: str) -> Dict | None:
    meta = FACTOR_REGISTRY.get(name)
    if meta is None:
        return None
    catalog_version, catalog = _load_factor_catalog()
    item = catalog.get(name, {})
    return _serialize_factor_meta(meta, catalog_version, item)


def list_factors() -> List[Dict]:
    """以 JSON-friendly 格式返回所有已注册因子。"""
    catalog_version, catalog = _load_factor_catalog()
    return [
        _serialize_factor_meta(m, catalog_version, catalog.get(m.name, {}))
        for m in FACTOR_REGISTRY.values()
    ]

