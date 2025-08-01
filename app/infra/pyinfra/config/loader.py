import os
import yaml
import json

def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, 'r') as f:
        if path.endswith('.yaml') or path.endswith('.yml'):
            return yaml.safe_load(f)
        elif path.endswith('.json'):
            return json.load(f)
        else:
            raise ValueError(f"Unsupported config file format: {path}")

def merge_env_vars(config: dict, prefix: str = "PYINFRA_") -> dict:
    """Override config values with environment variables that match."""
    for k, v in os.environ.items():
        if k.startswith(prefix):
            key = k[len(prefix):].lower()
            config[key] = v
    return config
