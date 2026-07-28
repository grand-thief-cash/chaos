from __future__ import annotations

from pathlib import Path

import yaml

from atlas.models import SemanticVersion


class SemanticRegistry:
    def __init__(self, active_path: str | Path) -> None:
        self.active_path = Path(active_path)
        self._cache: dict[str, SemanticVersion] = {}

    def get(self, version: str | None = None) -> SemanticVersion:
        if version is None:
            return self._load(self.active_path)
        for path in self.active_path.parent.glob("*.yaml"):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if payload.get("version") == version:
                return self._load(path)
        raise KeyError(f"semantic version not found: {version}")

    def _load(self, path: Path) -> SemanticVersion:
        cache_key = str(path.resolve())
        if cache_key not in self._cache:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self._cache[cache_key] = SemanticVersion.model_validate(payload)
        return self._cache[cache_key]

    def invalidate(self) -> None:
        self._cache.clear()
