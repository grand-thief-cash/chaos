"""Global configuration loader."""
import os
from pathlib import Path
from typing import Any

import yaml

_config: dict[str, Any] = {}


def load_config(path: str | None = None) -> dict[str, Any]:
    global _config
    if path is None:
        path = os.getenv("ATLAS_CONFIG", "config/atlas.yaml")
    raw = Path(path).read_text(encoding="utf-8")
    # 简单环境变量替换：${VAR_NAME}
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    _config = yaml.safe_load(raw)
    return _config


def get_config() -> dict[str, Any]:
    if not _config:
        load_config()
    return _config

