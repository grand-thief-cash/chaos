from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from atlas.consts import ALLOWED_ENVS, DEFAULT_ENV, Env
from atlas.models import Config


class ConfigManager:
    """Atlas configuration loader, following the Artemis config contract."""

    def __init__(self) -> None:
        self._config: Config | None = None
        self._config_path: Path | None = None
        self._env: str | None = None
        self._default_paths = (
            Path(__file__).parent.parent / "config" / "config.yaml",
            Path(__file__).parent.parent.parent / "config" / "config.yaml",
        )

    @staticmethod
    def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = ConfigManager._merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def init_config(
        self,
        path: str | None = None,
        env: str | None = None,
        *,
        force: bool = False,
    ) -> Config:
        requested_path = path or os.getenv(Env.CONFIG_PATH_VAR)
        requested_env = env or os.getenv(Env.CONFIG_ENV_VAR)
        if self._config is not None and not force:
            same_path = requested_path is None or Path(requested_path).resolve() == self._config_path
            same_env = requested_env is None or requested_env == self._env
            if same_path and same_env:
                return self._config

        config_path = Path(requested_path).resolve() if requested_path else None
        if config_path is None or not config_path.exists():
            config_path = next((candidate for candidate in self._default_paths if candidate.exists()), None)
        if config_path is None:
            self._config = Config(env=requested_env or DEFAULT_ENV)
            self._config_path = None
            self._env = self._config.env
            return self._config

        base = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        env_name = requested_env or base.get("env") or DEFAULT_ENV
        if env_name not in ALLOWED_ENVS:
            raise ValueError(
                f"Invalid environment '{env_name}'. Allowed values: {', '.join(ALLOWED_ENVS)}"
            )
        override_path = config_path.parent / Env.OVERRIDE_FILENAME_PATTERN.format(env=env_name)
        if override_path.exists():
            override = yaml.safe_load(override_path.read_text(encoding="utf-8")) or {}
            base = self._merge(base, override)
        base["env"] = env_name
        self._hydrate_minio_credentials(base, config_path.parent)
        self._config = Config.model_validate(base)
        project_root = config_path.parent.parent
        knowledge = self._config.engine.knowledge_engine
        knowledge.semantic_config_path = str(
            self._resolve_resource_path(
                knowledge.semantic_config_path,
                project_root,
            )
        )
        knowledge.prompt_mapping_path = str(
            self._resolve_resource_path(
                knowledge.prompt_mapping_path,
                project_root,
            )
        )
        self._config_path = config_path
        self._env = env_name
        return self._config

    @staticmethod
    def _hydrate_minio_credentials(base: dict[str, Any], config_dir: Path) -> None:
        """Import MinIO connection fields from a referenced service config.

        This is deliberately narrow: only the source config's top-level
        ``minio`` block is read, and only endpoint/access_key/secret_key/secure
        are copied. Atlas never modifies the source file.
        """
        endpoints = base.get("minio", {}).get("endpoints", {})
        if not isinstance(endpoints, dict):
            return
        for name, endpoint in endpoints.items():
            if not isinstance(endpoint, dict) or not endpoint.get("credential_source"):
                continue
            source_path = Path(str(endpoint["credential_source"]))
            if not source_path.is_absolute():
                source_path = (config_dir / source_path).resolve()
            source = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
            source_minio = source.get("minio")
            if not isinstance(source_minio, dict):
                raise ValueError(
                    f"MinIO credential source for '{name}' has no minio block: {source_path}"
                )
            for key in ("endpoint", "access_key", "secret_key", "secure"):
                if key in source_minio:
                    endpoint[key] = source_minio[key]

    @staticmethod
    def _resolve_resource_path(value: str, project_root: Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        working_candidate = (Path.cwd() / path).resolve()
        if working_candidate.exists():
            return working_candidate
        return (project_root / path).resolve()

    def get_config(self) -> Config:
        return self._config or self.init_config()

    def environment(self) -> str:
        return self._env or self.get_config().env


cfg_mgr = ConfigManager()
