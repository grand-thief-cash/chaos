

from enum import Enum
class Env(str, Enum):
    CONFIG_ENV_VAR = 'ARTEMIS_ENV'
    CONFIG_PATH_VAR = 'ARTEMIS_CONFIG'
    OVERRIDE_FILENAME_PATTERN = 'config.{env}.yaml'