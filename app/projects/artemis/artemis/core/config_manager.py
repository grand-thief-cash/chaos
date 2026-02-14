import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from artemis.consts import Env
from artemis.models import CallbackCfg, Config, DeptServicesCfg, HttpClientCfg, LoggingCfg, TelemetryCfg


class ConfigManager:
    """
    Manages configuration loading, caching, and access.
    """

    def __init__(self):
        self._config: Optional[Config] = None
        self._config_path: Optional[Path] = None
        self._env: Optional[str] = None
        self._task_variants_cache: Dict[str, Any] = {}

        self._def_path_primary = Path(__file__).parent.parent / 'config' / 'config.yaml'
        self._def_path_secondary = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
        self._task_yaml_paths = [
            Path(__file__).parent.parent / 'config' / 'task.yaml',
            Path(__file__).parent.parent.parent / 'config' / 'task.yaml',
        ]

    def _needs_reload(self, new_path: Optional[str], new_env: Optional[str]) -> bool:
        if not self._config_path:
            return True
        if new_path:
            try:
                if Path(new_path).resolve() != self._config_path:
                    return True
            except Exception:
                return True
        if new_env and new_env != self._env:
            return True
        return False

    def init_config(self, path: str | None = None, env: str | None = None, force: bool = False) -> Optional[Config]:
        """Initialize or reload configuration.
        Reload triggers if:
          - force=True
          - first load
          - path/env differ from currently cached values
        Merge order: base -> optional environment override (shallow top-level merge).
        Environment variables ARTEMIS_CONFIG / ARTEMIS_ENV act as fallback selectors.
        """
        if self._config and not force and not self._needs_reload(path, env):
            return self._config

        cfg_path = Path(path or os.getenv(Env.CONFIG_PATH_VAR, '')).resolve() if (
                    path or os.getenv(Env.CONFIG_PATH_VAR)) else None
        if not cfg_path or not cfg_path.exists():
            # attempt primary then secondary
            if self._def_path_primary.exists():
                cfg_path = self._def_path_primary
            elif self._def_path_secondary.exists():
                cfg_path = self._def_path_secondary
            else:
                # fallback: empty config; do not raise to allow early imports
                self._config = Config()
                self._config_path = None
                self._env = env or os.getenv(Env.CONFIG_ENV_VAR) or 'development'
                self._config.env = self._env
                return self._config

        with open(cfg_path, 'r', encoding='utf-8') as f:
            base_cfg = yaml.safe_load(f) or {}

        env_name = env or os.getenv(Env.CONFIG_ENV_VAR) or base_cfg.get('env') or 'development'

        override_file = cfg_path.parent / Env.OVERRIDE_FILENAME_PATTERN.format(env=env_name)
        if override_file.exists():
            with open(override_file, 'r', encoding='utf-8') as f:
                override_cfg = yaml.safe_load(f) or {}
            merged = {**base_cfg, **override_cfg}
        else:
            merged = base_cfg

        # ensure env is correct
        merged['env'] = env_name

        # Backward-compat: map legacy callback.* into dept_services.cronjob when dept_services isn't configured.
        # Supported legacy shapes:
        #   callback: { host, port }
        #   callback: { override_host, override_port }
        if 'dept_services' not in merged or not merged.get('dept_services'):
            cb = merged.get('callback') or {}
            if isinstance(cb, dict):
                host = cb.get('host') or cb.get('override_host')
                port = cb.get('port') or cb.get('override_port')
                if host is not None or port is not None:
                    merged['dept_services'] = {
                        'cronjob': {
                            'host': host,
                            'port': port,
                        }
                    }

        self._config = Config(**merged)
        self._config_path = cfg_path
        self._env = env_name
        return self._config

    def get_config(self) -> Optional[Config]:
        return self._config or self.init_config()

    def environment(self) -> str:
        return self._env or 'development'

    def task_default(self, task_code: str) -> Dict[str, Any]:
        return self.get_config().task_defaults.get(task_code, {})

    def output_default(self, task_code: str) -> Dict[str, Any]:
        return self.get_config().output_defaults.get(task_code, {})

    def logging_config(self) -> Optional[LoggingCfg]:
        return self.get_config().logging

    def telemetry_config(self) -> Optional[TelemetryCfg]:
        return self.get_config().telemetry

    @property
    def http_client_config(self) -> Optional[HttpClientCfg]:
        return self.get_config().http_client

    def callback_config(self) -> Optional[CallbackCfg]:
        return self.get_config().callback

    def dept_services_config(self) -> Optional[DeptServicesCfg]:
        return self.get_config().dept_services

    def _load_task_yaml(self) -> Dict[str, Any]:
        if self._task_variants_cache:
            return self._task_variants_cache
        for p in self._task_yaml_paths:
            try:
                if p.exists():
                    with open(p, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        # expect structure: { tasks: { <task_code>: { variants: [ { match: {...}, config: {...} } ] } } }
                        tasks = (data.get('tasks') or {})
                        norm: Dict[str, Any] = {}
                        for code, node in tasks.items():
                            variants = []
                            if isinstance(node, dict):
                                variants = node.get('variants') or []
                            elif isinstance(node, list):
                                # backward-compat: list of entries with 'when' or 'match'
                                variants = node
                            norm[code] = variants
                        self._task_variants_cache = norm
                        return self._task_variants_cache
            except Exception:
                continue
        self._task_variants_cache = {}
        return self._task_variants_cache

    def task_variant(self, task_code: str, incoming_params: Dict[str, Any]) -> Dict[str, Any]:
        variants_root = self._load_task_yaml()
        candidates = (variants_root.get(task_code) or [])
        if not candidates:
            return {}
        # Policy: if only one variant exists, accept it without strict match
        if len(candidates) == 1:
            return candidates[0].get('config') or {}
        matches = []
        for v in candidates:
            cond = v.get('match') or v.get('when') or {}
            # require full match of all keys when multiple variants exist
            if all(incoming_params.get(k) == val for k, val in cond.items()):
                matches.append(v)
        if len(matches) == 1:
            return matches[0].get('config') or {}
        elif len(matches) == 0:
            raise ValueError(f"No variant matched for task '{task_code}'")
        else:
            raise ValueError(f"Multiple variants matched for task '{task_code}'")

    def read_task_yaml_content(self) -> Dict[str, Any]:
        for p in self._task_yaml_paths:
            try:
                if p.exists():
                    return {
                        'path': str(p),
                        'content': p.read_text(encoding='utf-8'),
                    }
            except Exception:
                continue
        # fallback to primary path
        return {
            'path': str(self._task_yaml_paths[0]),
            'content': '',
        }

    def write_task_yaml_content(self, content: str) -> Dict[str, Any]:
        # validate yaml first
        yaml.safe_load(content)
        target = None
        for p in self._task_yaml_paths:
            if p.exists():
                target = p
                break
        if not target:
            target = self._task_yaml_paths[0]
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        # clear cached variants so next access reloads
        self._task_variants_cache = {}
        return {
            'path': str(target),
            'content': content,
        }


cfg_mgr = ConfigManager()
