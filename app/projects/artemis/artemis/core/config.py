import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_CONFIG: Dict[str, Any] = {}
_CONFIG_PATH: Optional[Path] = None
_ENV: Optional[str] = None

_TASK_VARIANTS_CACHE: Dict[str, Any] = {}

_DEF_PATH_PRIMARY = Path(__file__).parent.parent / 'config' / 'config.yaml'
_DEF_PATH_SECONDARY = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'

ENV_CONFIG_ENV_VAR = 'ARTEMIS_ENV'
ENV_CONFIG_PATH_VAR = 'ARTEMIS_CONFIG'

ENV_OVERRIDE_FILENAME_PATTERN = 'config.{env}.yaml'


def _needs_reload(new_path: Optional[str], new_env: Optional[str]) -> bool:
    if not _CONFIG_PATH:
        return True
    if new_path:
        try:
            if Path(new_path).resolve() != _CONFIG_PATH:
                return True
        except Exception:
            return True
    if new_env and new_env != _ENV:
        return True
    return False


def init_config(path: str | None = None, env: str | None = None, force: bool = False) -> Dict[str, Any]:
    """Initialize or reload configuration.
    Reload triggers if:
      - force=True
      - first load
      - path/env differ from currently cached values
    Merge order: base -> optional environment override (shallow top-level merge).
    Environment variables ARTEMIS_CONFIG / ARTEMIS_ENV act as fallback selectors.
    """
    global _CONFIG, _CONFIG_PATH, _ENV

    if _CONFIG and not force and not _needs_reload(path, env):
        return _CONFIG

    cfg_path = Path(path or os.getenv(ENV_CONFIG_PATH_VAR, '')).resolve() if (path or os.getenv(ENV_CONFIG_PATH_VAR)) else None
    if not cfg_path or not cfg_path.exists():
        # attempt primary then secondary
        if _DEF_PATH_PRIMARY.exists():
            cfg_path = _DEF_PATH_PRIMARY
        elif _DEF_PATH_SECONDARY.exists():
            cfg_path = _DEF_PATH_SECONDARY
        else:
            # fallback: empty config; do not raise to allow early imports
            _CONFIG = {}
            _CONFIG_PATH = None
            _ENV = env or os.getenv(ENV_CONFIG_ENV_VAR) or 'development'
            return _CONFIG

    with open(cfg_path, 'r', encoding='utf-8') as f:
        base_cfg = yaml.safe_load(f) or {}

    env_name = env or os.getenv(ENV_CONFIG_ENV_VAR) or base_cfg.get('env') or 'development'

    override_file = cfg_path.parent / ENV_OVERRIDE_FILENAME_PATTERN.format(env=env_name)
    if override_file.exists():
        with open(override_file, 'r', encoding='utf-8') as f:
            override_cfg = yaml.safe_load(f) or {}
        merged = {**base_cfg, **override_cfg}
    else:
        merged = base_cfg

    _CONFIG = merged
    _CONFIG_PATH = cfg_path
    _ENV = env_name
    return _CONFIG


def load_config(path: str | None = None) -> Dict[str, Any]:
    return init_config(path=path)


def get_config() -> Dict[str, Any]:
    return _CONFIG or init_config()


def environment() -> str:
    return _ENV or 'development'


def task_default(task_code: str) -> Dict[str, Any]:
    return (get_config().get('task_defaults', {}) or {}).get(task_code, {})


def output_default(task_code: str) -> Dict[str, Any]:
    return (get_config().get('output_defaults', {}) or {}).get(task_code, {})


def logging_config() -> Dict[str, Any]:
    return get_config().get('logging', {}) or {}


def telemetry_config() -> Dict[str, Any]:
    return get_config().get('telemetry', {}) or {}


def http_client_config() -> Dict[str, Any]:
    return get_config().get('http_client', {}) or {}


def callback_config() -> Dict[str, Any]:
    return get_config().get('callback', {}) or {}


_TASK_YAML_PATHS = [
    Path(__file__).parent.parent / 'config' / 'task.yaml',
    Path(__file__).parent.parent.parent / 'config' / 'task.yaml',
]


def _load_task_yaml() -> Dict[str, Any]:
    global _TASK_VARIANTS_CACHE
    if _TASK_VARIANTS_CACHE:
        return _TASK_VARIANTS_CACHE
    for p in _TASK_YAML_PATHS:
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
                    _TASK_VARIANTS_CACHE = norm
                    return _TASK_VARIANTS_CACHE
        except Exception:
            continue
    _TASK_VARIANTS_CACHE = {}
    return _TASK_VARIANTS_CACHE


def task_variant(task_code: str, incoming_params: Dict[str, Any]) -> Dict[str, Any]:
    variants_root = _load_task_yaml()
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
