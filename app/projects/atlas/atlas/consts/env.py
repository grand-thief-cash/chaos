class Env:
    CONFIG_PATH_VAR = "ATLAS_CONFIG"
    CONFIG_ENV_VAR = "ATLAS_ENV"
    OVERRIDE_FILENAME_PATTERN = "config-{env}.yaml"


DEFAULT_ENV = "development"
ALLOWED_ENVS = ("development", "test", "production")
