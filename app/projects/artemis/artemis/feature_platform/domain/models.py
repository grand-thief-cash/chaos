from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from artemis.feature_platform.domain.enums import (
    DependencyKind,
    EntityType,
    FeatureKind,
    ImplementationKind,
    ImplementationStatus,
    ValueStatus,
    ValueType,
    VersionStatus,
)


FEATURE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$")
ENTRYPOINT_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*:[A-Za-z_][A-Za-z0-9_]*$"
)
SENSITIVE_CONFIG_MARKERS = ("password", "secret", "token", "api_key")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FeatureDefinitionSpec(StrictModel):
    code: str
    display_name: str = Field(min_length=1)
    description: str = ""
    kind: FeatureKind
    entity_type: EntityType = EntityType.SECURITY
    value_type: ValueType
    unit: str = ""
    category: str = ""
    owner: str = ""
    tags: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not FEATURE_CODE_RE.fullmatch(value):
            raise ValueError("must use at least three lowercase dot-separated segments")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("tags must not contain empty values")
        if len(set(normalized)) != len(normalized):
            raise ValueError("tags must be unique")
        return normalized


class FeatureVersionSpec(StrictModel):
    number: StrictInt = Field(gt=0)
    status: VersionStatus = VersionStatus.DRAFT
    frequency: str = "on_demand"
    as_of_semantics: str = "snapshot"
    missing_policy: str = "explicit_missing"
    description: str = ""
    manifest_checksum: str = ""

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str) -> str:
        if value not in {"on_demand", "daily", "weekly", "monthly", "quarterly"}:
            raise ValueError("unsupported frequency")
        return value

    @field_validator("as_of_semantics")
    @classmethod
    def validate_as_of_semantics(cls, value: str) -> str:
        if value != "snapshot":
            raise ValueError("Phase 2 supports snapshot as_of semantics only")
        return value

    @field_validator("missing_policy")
    @classmethod
    def validate_missing_policy(cls, value: str) -> str:
        if value != "explicit_missing":
            raise ValueError("Phase 2 supports explicit_missing only")
        return value

    @field_validator("manifest_checksum")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("manifest_checksum must be lowercase SHA-256")
        return value


def _find_sensitive_key(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            lower = key_text.lower()
            child_path = f"{path}.{key_text}" if path else key_text
            sensitive = lower == "dsn" or any(marker in lower for marker in SENSITIVE_CONFIG_MARKERS)
            if sensitive and not lower.endswith("_ref"):
                return child_path
            found = _find_sensitive_key(child, child_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_sensitive_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


class FeatureImplementationSpec(StrictModel):
    kind: ImplementationKind
    producer_service: str = Field(min_length=1)
    backend: str = "python"
    entrypoint: str = Field(min_length=1)
    implementation_revision: StrictInt = Field(default=1, gt=0)
    config: dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""
    status: ImplementationStatus = ImplementationStatus.ACTIVE

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        if not ENTRYPOINT_RE.fullmatch(value):
            raise ValueError("entrypoint must use module.path:ClassName")
        return value

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        sensitive = _find_sensitive_key(value)
        if sensitive:
            raise ValueError(f"sensitive config key is forbidden: {sensitive}")
        return value

    @field_validator("checksum")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("checksum must be lowercase SHA-256")
        return value


class FeatureDependencySpec(StrictModel):
    kind: DependencyKind
    feature_code: str | None = None
    feature_version: StrictInt | None = None
    source: str | None = None
    dataset: str | None = None
    data_type: str | None = None
    raw_field: str | None = None
    contract_version: str | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> "FeatureDependencySpec":
        if self.kind == DependencyKind.FEATURE:
            if not self.feature_code or not FEATURE_CODE_RE.fullmatch(self.feature_code):
                raise ValueError("feature dependency requires a valid feature_code")
            if not self.feature_version or self.feature_version <= 0:
                raise ValueError("feature dependency requires a positive explicit feature_version")
            forbidden = (self.source, self.dataset, self.data_type, self.raw_field, self.contract_version)
            if any(value is not None for value in forbidden):
                raise ValueError("feature dependency must not contain data_field attributes")
        else:
            required = (self.source, self.dataset, self.data_type, self.raw_field, self.contract_version)
            if any(not value for value in required):
                raise ValueError(
                    "data_field dependency requires source, dataset, data_type, raw_field and contract_version"
                )
            if self.feature_code is not None or self.feature_version is not None:
                raise ValueError("data_field dependency must not contain feature attributes")
        return self

    def identity_key(self) -> str:
        if self.kind == DependencyKind.FEATURE:
            return f"feature:{self.feature_code}@{self.feature_version}"
        return (
            f"field:{self.source}/{self.dataset}/{self.data_type}/"
            f"{self.raw_field}@{self.contract_version}"
        )


class MaterializationSpec(StrictModel):
    store: str = "numeric"
    mode: str = "snapshot"

    @model_validator(mode="after")
    def validate_phase_two_support(self) -> "MaterializationSpec":
        if self.store != "numeric" or self.mode != "snapshot":
            raise ValueError("Phase 2 supports numeric snapshot materialization only")
        return self


class QualitySpec(StrictModel):
    min_coverage_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    allow_nan: bool = False
    allow_infinite: bool = False
    allow_duplicates: bool = False


class FeatureManifest(StrictModel):
    api_version: str
    feature: FeatureDefinitionSpec
    version: FeatureVersionSpec
    implementation: FeatureImplementationSpec
    dependencies: list[FeatureDependencySpec] = Field(default_factory=list)
    materialization: MaterializationSpec = Field(default_factory=MaterializationSpec)
    quality: QualitySpec = Field(default_factory=QualitySpec)

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, value: str) -> str:
        if value != "chaos.feature/v1":
            raise ValueError("unsupported api_version")
        return value

    @model_validator(mode="after")
    def validate_manifest_contract(self) -> "FeatureManifest":
        if self.feature.value_type not in {ValueType.NUMBER, ValueType.INTEGER}:
            raise ValueError("numeric materialization requires number or integer value_type")
        if self.version.status == VersionStatus.PUBLISHED:
            if self.implementation.status != ImplementationStatus.ACTIVE:
                raise ValueError("published versions require an active implementation")
        keys = [dependency.identity_key() for dependency in self.dependencies]
        if len(keys) != len(set(keys)):
            raise ValueError("dependencies must be unique")
        own_key = f"feature:{self.feature.code}@{self.version.number}"
        if own_key in keys:
            raise ValueError("feature version cannot depend on itself")
        return self

    @property
    def identity(self) -> str:
        return f"{self.feature.code}@{self.version.number}"

    @property
    def requires_source_availability(self) -> bool:
        return any(dep.kind == DependencyKind.DATA_FIELD for dep in self.dependencies)


class FeatureReference(StrictModel):
    code: str
    version: StrictInt = Field(gt=0)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not FEATURE_CODE_RE.fullmatch(value):
            raise ValueError("invalid feature code")
        return value


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return value


class FeatureComputeRequest(StrictModel):
    features: list[FeatureReference] = Field(min_length=1)
    security_ids: list[StrictInt] = Field(min_length=1, max_length=20000)
    as_of_time: datetime
    data_cutoff_time: datetime
    market: str = Field(min_length=1)
    source_profile: str = Field(default="default", min_length=1)
    trigger_type: str = "manual"
    idempotency_key: str | None = Field(default=None, max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)
    force: bool = False
    retry_of_run_id: str | None = None

    @field_validator("as_of_time")
    @classmethod
    def validate_as_of(cls, value: datetime) -> datetime:
        return _aware(value, "as_of_time")

    @field_validator("data_cutoff_time")
    @classmethod
    def validate_cutoff(cls, value: datetime) -> datetime:
        return _aware(value, "data_cutoff_time")

    @field_validator("security_ids")
    @classmethod
    def validate_security_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("security_ids must contain positive integers")
        if len(value) != len(set(value)):
            raise ValueError("security_ids must be unique")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        sensitive = _find_sensitive_key(value)
        if sensitive:
            raise ValueError(f"sensitive runtime parameter is forbidden: {sensitive}")
        return value

    @field_validator("features")
    @classmethod
    def validate_features(cls, value: list[FeatureReference]) -> list[FeatureReference]:
        keys = {(item.code, item.version) for item in value}
        if len(keys) != len(value):
            raise ValueError("features must be unique")
        return value

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger(cls, value: str) -> str:
        if value not in {"manual", "cron", "api", "backfill"}:
            raise ValueError("unsupported trigger_type")
        return value

    @field_validator("retry_of_run_id")
    @classmethod
    def validate_retry_id(cls, value: str | None) -> str | None:
        if value is not None:
            UUID(value)
        return value

    @model_validator(mode="after")
    def validate_times(self) -> "FeatureComputeRequest":
        if self.data_cutoff_time > self.as_of_time:
            raise ValueError("data_cutoff_time must not be later than as_of_time")
        return self


class FeatureComputeResponse(StrictModel):
    accepted: bool
    reused: bool = False
    run_id: str
    status: str
    request_fingerprint: str


class ManifestSelectionRequest(StrictModel):
    paths: list[str] = Field(default_factory=list)
    check_entrypoints: bool = True
    source_profile: str = Field(default="default", min_length=1)


class ManifestValidateRequest(ManifestSelectionRequest):
    manifests: list[dict[str, Any]] = Field(default_factory=list)


class NumericValue(StrictModel):
    security_id: StrictInt = Field(gt=0)
    value: float | int | None = None
    value_status: ValueStatus
    quality_flags: dict[str, Any] = Field(default_factory=dict)
    source_max_available_at: datetime | None = None

    @field_validator("value", mode="before")
    @classmethod
    def validate_numeric_type(cls, value: Any) -> Any:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("value must be a JSON number or null")
        return value

    @model_validator(mode="after")
    def validate_value_status(self) -> "NumericValue":
        if self.value_status == ValueStatus.VALID and self.value is None:
            raise ValueError("valid rows require a value")
        if self.value_status != ValueStatus.VALID and self.value is not None:
            raise ValueError("missing or invalid rows require a null value")
        if self.source_max_available_at is not None:
            _aware(self.source_max_available_at, "source_max_available_at")
        return self


class FeatureNumericOutput(StrictModel):
    feature_version_id: StrictInt = Field(gt=0)
    observed_at: datetime
    rows: list[NumericValue]

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _aware(value, "observed_at")


class RegistryFeatureVersion(StrictModel):
    feature_code: str
    definition: dict[str, Any]
    version: dict[str, Any]
    implementation: dict[str, Any]
    dependencies: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def id(self) -> int:
        return int(self.version["id"])

    @property
    def version_number(self) -> int:
        return int(self.version["version_number"])

    @property
    def status(self) -> str:
        return str(self.version.get("status", ""))

    @property
    def manifest_checksum(self) -> str:
        return str(self.version.get("manifest_checksum", ""))

    def dependency_snapshot(self, dependency: dict[str, Any]) -> dict[str, Any]:
        snapshot = dependency.get("dependency_ref_snapshot") or {}
        if isinstance(snapshot, str):
            return json.loads(snapshot)
        return dict(snapshot)
