from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import ValidationError

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureManifest
from artemis.feature_platform.manifests.validator import validate_manifest


@dataclass(frozen=True)
class LoadedCatalog:
    root: Path
    manifests: tuple[FeatureManifest, ...]
    source_paths: dict[str, Path]

    def get(self, feature_code: str, version: int) -> FeatureManifest:
        key = f"{feature_code}@{version}"
        for manifest in self.manifests:
            if manifest.identity == key:
                return manifest
        raise FeaturePlatformError(
            "MANIFEST_NOT_FOUND",
            f"local manifest {key} was not found",
            status_code=404,
        )


class FeatureManifestLoader:
    def __init__(self, manifest_root: str | Path) -> None:
        root = Path(manifest_root).expanduser()
        if not root.is_absolute():
            cwd_candidate = (Path.cwd() / root).resolve()
            project_root = Path(__file__).resolve().parents[3]
            project_candidate = (project_root / root).resolve()
            root = cwd_candidate if cwd_candidate.exists() else project_candidate
        self.root = root.resolve()

    def _inside_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise FeaturePlatformError(
                "MANIFEST_PATH_INVALID",
                f"manifest path escapes catalog root: {path}",
                status_code=400,
            )
        return resolved

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            raise FeaturePlatformError(
                "MANIFEST_READ_FAILED",
                f"cannot read manifest {path}: {exc}",
                status_code=400,
            ) from exc

    def _catalog_paths(self) -> list[Path]:
        index = self.root / "manifest.yaml"
        if not index.is_file():
            raise FeaturePlatformError(
                "MANIFEST_CATALOG_NOT_FOUND",
                f"feature catalog index was not found: {index}",
                status_code=404,
            )
        data = self._read_yaml(index) or {}
        if not isinstance(data, dict) or data.get("api_version") != "chaos.feature.catalog/v1":
            raise FeaturePlatformError(
                "MANIFEST_CATALOG_INVALID",
                "feature catalog api_version must be chaos.feature.catalog/v1",
                status_code=400,
            )
        entries = data.get("features")
        if not isinstance(entries, list) or not entries:
            raise FeaturePlatformError(
                "MANIFEST_CATALOG_INVALID",
                "feature catalog must contain a non-empty features list",
                status_code=400,
            )
        paths: list[Path] = []
        for entry in entries:
            if not isinstance(entry, str) or not entry.strip():
                raise FeaturePlatformError(
                    "MANIFEST_CATALOG_INVALID",
                    "catalog feature paths must be non-empty strings",
                    status_code=400,
                )
            paths.append(self._inside_root(self.root / entry))
        return paths

    def _selected_paths(self, paths: Iterable[str] | None) -> list[Path]:
        requested = list(paths or [])
        if not requested:
            return self._catalog_paths()
        return [self._inside_root(self.root / item) for item in requested]

    @staticmethod
    def _parse(data: Any, label: str) -> FeatureManifest:
        if not isinstance(data, dict):
            raise FeaturePlatformError(
                "MANIFEST_INVALID",
                f"manifest {label} must be a YAML/JSON object",
                status_code=400,
            )
        try:
            return FeatureManifest.model_validate(data)
        except ValidationError as exc:
            raise FeaturePlatformError(
                "MANIFEST_INVALID",
                f"manifest {label} failed validation: {exc}",
                status_code=400,
            ) from exc

    def load(
        self,
        paths: Iterable[str] | None = None,
        *,
        check_entrypoints: bool = True,
    ) -> LoadedCatalog:
        manifests: list[FeatureManifest] = []
        source_paths: dict[str, Path] = {}
        for path in self._selected_paths(paths):
            if not path.is_file():
                raise FeaturePlatformError(
                    "MANIFEST_NOT_FOUND",
                    f"manifest file was not found: {path}",
                    status_code=404,
                )
            manifest = self._parse(self._read_yaml(path), str(path))
            if manifest.identity in source_paths:
                raise FeaturePlatformError(
                    "MANIFEST_DUPLICATE",
                    f"duplicate local manifest {manifest.identity}",
                    status_code=400,
                )
            validate_manifest(manifest, check_entrypoint=check_entrypoints)
            manifests.append(manifest)
            source_paths[manifest.identity] = path
        return LoadedCatalog(self.root, tuple(manifests), source_paths)

    def load_inline(
        self,
        values: Iterable[dict[str, Any]],
        *,
        check_entrypoints: bool = True,
    ) -> tuple[FeatureManifest, ...]:
        manifests: list[FeatureManifest] = []
        seen: set[str] = set()
        for index, value in enumerate(values):
            manifest = self._parse(value, f"inline[{index}]")
            if manifest.identity in seen:
                raise FeaturePlatformError(
                    "MANIFEST_DUPLICATE",
                    f"duplicate inline manifest {manifest.identity}",
                    status_code=400,
                )
            validate_manifest(manifest, check_entrypoint=check_entrypoints)
            manifests.append(manifest)
            seen.add(manifest.identity)
        return tuple(manifests)
