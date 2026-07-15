from enum import Enum


class FeatureKind(str, Enum):
    RAW = "raw"
    METRIC = "metric"
    FACTOR = "factor"
    SIGNAL = "signal"
    PREDICTION = "prediction"
    LABEL = "label"


class EntityType(str, Enum):
    SECURITY = "security"


class ValueType(str, Enum):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    STRING = "string"
    JSON = "json"
    VECTOR = "vector"
    DISTRIBUTION = "distribution"


class VersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ImplementationKind(str, Enum):
    PYTHON = "python"
    EXPRESSION = "expression"
    VENDOR = "vendor"
    MODEL = "model"
    LLM = "llm"
    EXTERNAL = "external"


class ImplementationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class DependencyKind(str, Enum):
    FEATURE = "feature"
    DATA_FIELD = "data_field"


class ValueStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    INVALID = "invalid"
