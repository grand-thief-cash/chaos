"""Application service for the Feature Platform bounded context."""

from __future__ import annotations

import calendar
import base64
import hashlib
import hmac
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from artemis.consts import TaskCode, TaskMode
from artemis.core import cfg_mgr
from artemis.core.task_engine import TaskEngine
from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import (
    FeatureComputeRequest,
    FeatureComputeResponse,
    FeatureBackfillRequest,
    FeatureManifest,
    FeaturePreviewRequest,
    FeatureScopeRequest,
    ManifestCatalogError,
    ManifestCatalogItem,
    ManifestCatalogResponse,
    ManifestSelectionRequest,
    ManifestValidateRequest,
    RegistrySyncChange,
    RegistrySyncPreviewResponse,
    RegistrySyncRequest,
)
from artemis.feature_platform.execution.engine import FeatureExecutionEngine
from artemis.feature_platform.backfill_dispatcher import BackfillDispatcher
from artemis.feature_platform.manifests.checksum import (
    manifest_registry_checksum,
    registry_projection,
)
from artemis.feature_platform.manifests.loader import FeatureManifestLoader
from artemis.feature_platform.manifests.validator import validate_manifest
from artemis.feature_platform.planning import DependencyPlanner
from artemis.feature_platform.providers.phoenixa import PhoenixAFeatureProvider
from artemis.feature_platform.registry.client import FeatureRegistryClient
from artemis.feature_platform.registry.factory import build_registry_client
from artemis.models import TaskRunReq
from artemis.telemetry.otel import record_feature_stale_runs


RegistryFactory = Callable[[str], FeatureRegistryClient]
_PREVIEW_SEMAPHORE = threading.BoundedSemaphore(2)
_BACKFILL_DISPATCHERS: dict[int, BackfillDispatcher] = {}
_BACKFILL_DISPATCHERS_LOCK = threading.Lock()


def _code_revision() -> str:
    configured = os.getenv("ARTEMIS_CODE_REVISION", "").strip()
    if configured:
        return configured
    repository = Path(__file__).resolve().parents[5]
    try:
        revision = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        if revision:
            return revision + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        pass
    return "artemis-0.1.0-unknown"


def _universe_hash(security_ids: list[int]) -> str:
    canonical = json.dumps(sorted(security_ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _rfc3339z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _expand_evaluations(request: FeatureScopeRequest) -> list[datetime]:
    scope = request.evaluation
    if scope.mode == "point":
        return [scope.as_of_time]  # type: ignore[list-item]
    start = scope.start_as_of
    end = scope.end_as_of
    if start is None or end is None:
        raise FeaturePlatformError("EVALUATION_SCOPE_INVALID", "range bounds are required")
    if scope.step == "explicit":
        return list(scope.explicit_times)
    evaluations: list[datetime] = []
    current = start
    index = 0
    while current <= end:
        evaluations.append(current)
        index += 1
        if scope.step == "daily":
            current = start + timedelta(days=index)
        elif scope.step == "weekly":
            current = start + timedelta(weeks=index)
        elif scope.step == "monthly":
            current = _add_months(start, index)
        elif scope.step == "quarterly":
            current = _add_months(start, index * 3)
        else:
            raise FeaturePlatformError("EVALUATION_STEP_INVALID", f"unsupported step {scope.step}")
        if len(evaluations) > 10000:
            raise FeaturePlatformError(
                "EVALUATION_LIMIT_EXCEEDED",
                "evaluation range expands beyond 10,000 points",
                status_code=422,
            )
    return evaluations


def _cutoff_for(request: FeatureScopeRequest, as_of_time: datetime) -> datetime:
    policy = request.data_cutoff_policy
    if policy.mode == "same_as_as_of":
        return as_of_time
    if policy.mode == "lag_seconds":
        return as_of_time - timedelta(seconds=int(policy.seconds or 0))
    candidates = (
        as_of_time.isoformat(),
        as_of_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    for key in candidates:
        if key in policy.explicit:
            cutoff = policy.explicit[key]
            if cutoff > as_of_time:
                raise FeaturePlatformError(
                    "DATA_CUTOFF_INVALID",
                    f"explicit cutoff for {as_of_time.isoformat()} is later than as-of",
                )
            return cutoff
    raise FeaturePlatformError(
        "DATA_CUTOFF_MISSING",
        f"explicit cutoff is missing for {as_of_time.isoformat()}",
    )


def _registry_change(
    manifest: FeatureManifest,
    detail: dict[str, Any] | None,
) -> RegistrySyncChange:
    desired = registry_projection(manifest)
    desired_status = str(desired["version"]["status"])
    desired_checksum = str(desired["version"]["manifest_checksum"])
    base = {
        "feature_code": manifest.feature.code,
        "version": manifest.version.number,
        "identity": manifest.identity,
        "desired_status": desired_status,
        "desired_checksum": desired_checksum,
    }
    if detail is None:
        return RegistrySyncChange(
            **base,
            action="create",
            changed_fields=["definition", "version", "implementation", "dependencies"],
        )

    definition = detail.get("definition") or {}
    identity_fields = {
        "kind": manifest.feature.kind.value,
        "entity_type": manifest.feature.entity_type.value,
        "value_type": manifest.feature.value_type.value,
    }
    identity_conflicts = [
        field for field, value in identity_fields.items() if definition.get(field) != value
    ]
    if identity_conflicts:
        return RegistrySyncChange(
            **base,
            action="blocked",
            changed_fields=[f"feature.{field}" for field in identity_conflicts],
            code="FEATURE_DEFINITION_IDENTITY_CONFLICT",
            message="registered kind, entity_type, or value_type differs from the manifest",
        )

    desired_definition = desired["feature"]
    definition_fields = {
        "display_name": "display_name",
        "description": "description",
        "unit": "unit",
        "category": "category",
        "owner": "owner",
        "tags": "tags",
    }
    changed_fields = [
        f"feature.{manifest_field}"
        for manifest_field, registry_field in definition_fields.items()
        if definition.get(registry_field) != desired_definition.get(manifest_field)
    ]

    versions = detail.get("versions") or []
    current = next(
        (
            item.get("version") or {}
            for item in versions
            if int((item.get("version") or {}).get("version_number", 0))
            == manifest.version.number
        ),
        None,
    )
    if current is None:
        max_version = max(
            (int((item.get("version") or {}).get("version_number", 0)) for item in versions),
            default=0,
        )
        if manifest.version.number <= max_version:
            return RegistrySyncChange(
                **base,
                action="blocked",
                changed_fields=changed_fields + ["version.number"],
                code="FEATURE_VERSION_NOT_MONOTONIC",
                message=(
                    f"version {manifest.version.number} must be greater than "
                    f"the registered maximum {max_version}"
                ),
            )
        return RegistrySyncChange(
            **base,
            action="create",
            changed_fields=changed_fields
            + ["version", "implementation", "dependencies"],
        )

    current_status = str(current.get("status", ""))
    current_checksum = str(current.get("manifest_checksum", ""))
    if current_checksum != desired_checksum:
        changed_fields.append("version.manifest_checksum")
        if current_status != "draft":
            return RegistrySyncChange(
                **base,
                action="blocked",
                changed_fields=changed_fields,
                current_status=current_status,
                current_checksum=current_checksum,
                code="MANIFEST_CHECKSUM_CONFLICT",
                message=(
                    f"registered {manifest.identity} is {current_status} and immutable"
                ),
            )
        action = "update_draft"
    elif desired_status == "published" and current_status == "draft":
        changed_fields.append("version.status")
        action = "update_draft"
    elif changed_fields:
        action = "update_metadata"
    else:
        action = "unchanged"

    return RegistrySyncChange(
        **base,
        action=action,
        changed_fields=changed_fields,
        current_status=current_status,
        current_checksum=current_checksum,
    )


class FeatureService:
    def __init__(
        self,
        task_engine: TaskEngine,
        *,
        registry_factory: RegistryFactory | None = None,
        code_revision: str | None = None,
    ) -> None:
        self.task_engine = task_engine
        self.registry_factory = registry_factory or (lambda profile: build_registry_client(profile))
        self.code_revision = code_revision

    @staticmethod
    def _settings():
        return cfg_mgr.engine_config().feature_platform

    def _ensure_enabled(self) -> None:
        if not self._settings().enabled:
            raise FeaturePlatformError(
                "FEATURE_PLATFORM_DISABLED",
                "Feature Platform execution is disabled",
                status_code=503,
            )

    def _loader(self) -> FeatureManifestLoader:
        return FeatureManifestLoader(self._settings().manifest_root)

    def _backfill_dispatcher(self) -> BackfillDispatcher:
        key = id(self.task_engine)
        with _BACKFILL_DISPATCHERS_LOCK:
            dispatcher = _BACKFILL_DISPATCHERS.get(key)
            if dispatcher is None:
                dispatcher = BackfillDispatcher(
                    self.task_engine,
                    self.registry_factory,
                    self._settings,
                )
                _BACKFILL_DISPATCHERS[key] = dispatcher
            return dispatcher

    def start_backfill_dispatcher(self) -> None:
        self._ensure_enabled()
        self._backfill_dispatcher().start()

    def stop_backfill_dispatcher(self) -> None:
        dispatcher = _BACKFILL_DISPATCHERS.get(id(self.task_engine))
        if dispatcher is not None:
            dispatcher.stop()

    def validate_manifests(self, request: ManifestValidateRequest) -> dict[str, Any]:
        loader = self._loader()
        if request.manifests:
            manifests = loader.load_inline(
                request.manifests,
                check_entrypoints=request.check_entrypoints,
            )
        else:
            manifests = loader.load(
                request.paths,
                check_entrypoints=request.check_entrypoints,
            ).manifests
        return {
            "valid": True,
            "count": len(manifests),
            "manifests": [
                validate_manifest(manifest, check_entrypoint=request.check_entrypoints)
                for manifest in manifests
            ],
        }

    @staticmethod
    def _registry_detail(
        client: FeatureRegistryClient,
        feature_code: str,
        cache: dict[str, dict[str, Any] | FeaturePlatformError | None],
    ) -> dict[str, Any] | None:
        if feature_code not in cache:
            try:
                cache[feature_code] = client.get_definition(feature_code)
            except FeaturePlatformError as exc:
                cache[feature_code] = None if exc.status_code == 404 else exc
        result = cache[feature_code]
        if isinstance(result, FeaturePlatformError):
            raise result
        return result

    def list_manifest_catalog(
        self,
        *,
        source_profile: str = "default",
        check_entrypoints: bool = True,
    ) -> ManifestCatalogResponse:
        inspections = self._loader().inspect(check_entrypoints=check_entrypoints)
        client = self.registry_factory(source_profile)
        registry_cache: dict[str, dict[str, Any] | FeaturePlatformError | None] = {}
        items: list[ManifestCatalogItem] = []
        warnings: set[str] = set()
        for inspection in inspections:
            manifest = inspection.manifest
            errors: list[ManifestCatalogError] = []
            if inspection.error is not None:
                errors.append(
                    ManifestCatalogError(
                        code=inspection.error.code,
                        message=inspection.error.message,
                    )
                )
            registry_status = "unknown"
            registry_action = "unknown"
            registry_checksum: str | None = None
            changed_fields: list[str] = []
            manifest_checksum: str | None = None
            if manifest is not None and inspection.error is None:
                manifest_checksum = manifest_registry_checksum(manifest)
                try:
                    detail = self._registry_detail(
                        client,
                        manifest.feature.code,
                        registry_cache,
                    )
                    change = _registry_change(manifest, detail)
                    registry_action = change.action
                    registry_checksum = change.current_checksum
                    changed_fields = change.changed_fields
                    if change.action == "unchanged":
                        registry_status = "in_sync"
                    elif change.action == "create":
                        registry_status = "missing"
                    elif change.action == "blocked":
                        registry_status = "blocked"
                        errors.append(
                            ManifestCatalogError(
                                code=change.code or "REGISTRY_SYNC_BLOCKED",
                                message=change.message or "registry sync is blocked",
                            )
                        )
                    else:
                        registry_status = "drift"
                except FeaturePlatformError as exc:
                    registry_status = "unavailable"
                    errors.append(ManifestCatalogError(code=exc.code, message=exc.message))
                    warnings.add("PhoenixA Registry is unavailable for one or more manifests.")
            plugin_status = (
                "unchecked"
                if not check_entrypoints
                else "loadable"
                if inspection.error is None
                else "unloadable"
                if inspection.error.code.startswith("PLUGIN_")
                else "unknown"
            )
            items.append(
                ManifestCatalogItem(
                    path=inspection.relative_path,
                    feature_code=manifest.feature.code if manifest is not None else None,
                    version=manifest.version.number if manifest is not None else None,
                    identity=manifest.identity if manifest is not None else None,
                    validation_status="valid" if inspection.error is None else "invalid",
                    content_checksum=inspection.content_checksum,
                    manifest_checksum=manifest_checksum,
                    plugin_status=plugin_status,
                    registry_status=registry_status,
                    registry_action=registry_action,
                    registry_checksum=registry_checksum,
                    changed_fields=changed_fields,
                    errors=errors,
                )
            )
        return ManifestCatalogResponse(
            catalog_checksum=FeatureManifestLoader.inspection_checksum(inspections),
            loaded_at=datetime.now(timezone.utc),
            source_profile=source_profile,
            count=len(items),
            items=items,
            warnings=sorted(warnings),
        )

    def preview_registry_sync(
        self,
        request: ManifestSelectionRequest,
    ) -> RegistrySyncPreviewResponse:
        self._ensure_enabled()
        catalog = self._loader().load(
            request.paths,
            check_entrypoints=request.check_entrypoints,
        )
        client = self.registry_factory(request.source_profile)
        registry_cache: dict[str, dict[str, Any] | FeaturePlatformError | None] = {}
        changes: list[RegistrySyncChange] = []
        blocked: list[RegistrySyncChange] = []
        unchanged: list[str] = []
        for manifest in catalog.manifests:
            detail = self._registry_detail(client, manifest.feature.code, registry_cache)
            change = _registry_change(manifest, detail)
            if change.action == "blocked":
                blocked.append(change)
            elif change.action == "unchanged":
                unchanged.append(change.identity)
            else:
                changes.append(change)
        return RegistrySyncPreviewResponse(
            catalog_checksum=catalog.checksum,
            source_profile=request.source_profile,
            changes=changes,
            blocked=blocked,
            unchanged=unchanged,
        )

    def sync_registry(self, request: RegistrySyncRequest) -> dict[str, Any]:
        self._ensure_enabled()
        catalog = self._loader().load(
            request.paths,
            check_entrypoints=request.check_entrypoints,
        )
        if (
            request.expected_catalog_checksum is not None
            and request.expected_catalog_checksum != catalog.checksum
        ):
            raise FeaturePlatformError(
                "CATALOG_CHECKSUM_CONFLICT",
                "feature catalog changed after sync preview; preview again before syncing",
                status_code=409,
            )
        result = self.registry_factory(request.source_profile).sync_manifests(catalog.manifests)
        result["catalog_checksum"] = catalog.checksum
        return result

    def _resolve_scope(
        self,
        request: FeatureScopeRequest,
        *,
        enforce_preview_limits: bool,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        client = self.registry_factory(request.source_profile)
        plan = DependencyPlanner(client.resolve_version).build(request.feature_refs)
        plan.ensure_executable()
        catalog = self._loader().load(check_entrypoints=True)
        FeatureExecutionEngine.validate_plan(plan, catalog)

        warnings: list[str] = []
        securities: list[dict[str, Any]]
        if request.universe.mode == "explicit":
            security_ids = sorted(request.universe.security_ids)
            securities = [{"security_id": security_id} for security_id in security_ids]
        else:
            securities = client.list_active_securities(request.market)
            security_ids = sorted(int(item["security_id"]) for item in securities)
            warnings.append(
                "All Active is frozen at resolution time and is not a point-in-time historical universe."
            )

        evaluations = _expand_evaluations(request)
        cutoffs = [_cutoff_for(request, as_of) for as_of in evaluations]
        settings = self._settings()
        execution_cells = len(security_ids) * len(evaluations) * len(plan.ordered_nodes)
        root_cells = len(security_ids) * len(evaluations) * len(plan.root_version_ids)
        violations: list[str] = []
        preview_limits = (
            ("security_count", len(security_ids), settings.preview_max_securities),
            ("evaluation_count", len(evaluations), settings.preview_max_evaluations),
            ("root_feature_count", len(plan.root_version_ids), settings.preview_max_root_features),
            ("dag_node_count", len(plan.ordered_nodes), settings.preview_max_dag_nodes),
            ("execution_cells", execution_cells, settings.preview_max_execution_cells),
        )
        for name, actual, limit in preview_limits:
            if actual > limit:
                violations.append(f"{name} {actual} exceeds preview limit {limit}")
        if enforce_preview_limits and violations:
            raise FeaturePlatformError(
                "PREVIEW_LIMIT_EXCEEDED",
                "; ".join(violations),
                status_code=422,
            )
        return {
            "plan": plan,
            "catalog": catalog,
            "client": client,
            "security_ids": security_ids,
            "securities": securities,
            "evaluations": evaluations,
            "cutoffs": cutoffs,
            "scope": {
                "universe_mode": request.universe.mode,
                "security_count": len(security_ids),
                "evaluation_count": len(evaluations),
                "root_feature_count": len(plan.root_version_ids),
                "dag_node_count": len(plan.ordered_nodes),
                "estimated_root_cells": root_cells,
                "estimated_execution_cells": execution_cells,
                "universe_hash": _universe_hash(security_ids),
            },
            "warnings": warnings,
            "violations": violations,
        }

    def resolve_scope(self, request: FeatureScopeRequest) -> dict[str, Any]:
        resolved = self._resolve_scope(request, enforce_preview_limits=False)
        securities = resolved["securities"]
        return {
            "allowed_for_preview": not resolved["violations"],
            "violations": resolved["violations"],
            "warnings": resolved["warnings"],
            "scope": resolved["scope"],
            "security_ids": resolved["security_ids"]
            if len(resolved["security_ids"]) <= self._settings().preview_max_securities
            else [],
            "security_sample": securities[:10],
            "evaluations": [
                {
                    "as_of_time": as_of,
                    "data_cutoff_time": cutoff,
                }
                for as_of, cutoff in zip(resolved["evaluations"], resolved["cutoffs"])
            ],
            "plan": resolved["plan"].summary(),
        }

    @staticmethod
    def _preview_overrides(
        request: FeaturePreviewRequest,
        resolved: dict[str, Any],
    ) -> dict[int, dict[str, object]]:
        if not request.preview_overrides:
            return {}
        plan = resolved["plan"]
        if len(plan.root_version_ids) != 1:
            raise FeaturePlatformError(
                "PREVIEW_OVERRIDE_AMBIGUOUS",
                "preview overrides require exactly one root feature",
            )
        root_id = plan.root_version_ids[0]
        root_node = plan.nodes_by_id[root_id]
        manifest = resolved["catalog"].get(
            root_node.registry_version.feature_code,
            root_node.registry_version.version_number,
        )
        if not manifest.implementation.preview_supported:
            raise FeaturePlatformError(
                "PREVIEW_NOT_SUPPORTED",
                f"{manifest.identity} does not support preview execution",
            )
        declared = manifest.preview_parameters
        unknown = sorted(set(request.preview_overrides) - set(declared))
        if unknown:
            raise FeaturePlatformError(
                "PREVIEW_PARAMETER_UNDECLARED",
                "undeclared preview parameters: " + ", ".join(unknown),
            )
        validated: dict[str, object] = {}
        try:
            for name, value in request.preview_overrides.items():
                validated[name] = declared[name].validate_value(name, value)
        except ValueError as exc:
            raise FeaturePlatformError("PREVIEW_PARAMETER_INVALID", str(exc)) from exc
        return {root_id: validated}

    def preview(self, request: FeaturePreviewRequest) -> dict[str, Any]:
        if not _PREVIEW_SEMAPHORE.acquire(blocking=False):
            raise FeaturePlatformError(
                "PREVIEW_CAPACITY_EXCEEDED",
                "all preview execution slots are busy; retry later",
                status_code=429,
            )
        try:
            resolved = self._resolve_scope(request, enforce_preview_limits=True)
            overrides = self._preview_overrides(request, resolved)
            settings = self._settings()
            engine = FeatureExecutionEngine(
                min(settings.plugin_timeout_seconds, settings.preview_timeout_seconds)
            )
            provider = PhoenixAFeatureProvider(resolved["client"])
            preview_id = str(uuid4())
            started = time.monotonic()
            evaluations: list[dict[str, Any]] = []
            total_rows = 0
            plan = resolved["plan"]
            for node in plan.ordered_nodes:
                manifest = resolved["catalog"].get(
                    node.registry_version.feature_code,
                    node.registry_version.version_number,
                )
                if not manifest.implementation.preview_supported:
                    raise FeaturePlatformError(
                        "PREVIEW_NOT_SUPPORTED",
                        f"{manifest.identity} does not support preview execution",
                    )

            for as_of, cutoff in zip(resolved["evaluations"], resolved["cutoffs"]):
                if time.monotonic() - started >= settings.preview_timeout_seconds:
                    raise FeaturePlatformError(
                        "PREVIEW_TIMEOUT",
                        f"preview exceeded {settings.preview_timeout_seconds}s",
                        status_code=422,
                    )
                execution = engine.execute(
                    execution_id=preview_id,
                    plan=plan,
                    catalog=resolved["catalog"],
                    provider=provider,
                    security_ids=tuple(resolved["security_ids"]),
                    as_of_time=as_of,
                    data_cutoff_time=cutoff,
                    source_profile=request.source_profile,
                    market=request.market,
                    implementation_overrides=overrides,
                )
                rows: list[dict[str, Any]] = []
                quality = {"valid": 0, "missing": 0, "invalid": 0}
                for version_id in plan.root_version_ids:
                    node = plan.nodes_by_id[version_id]
                    validated = execution.validated[version_id]
                    quality["valid"] += validated.valid_count
                    quality["missing"] += validated.missing_count
                    quality["invalid"] += validated.invalid_count
                    for row in validated.output.rows:
                        rows.append(
                            {
                                "feature_code": node.registry_version.feature_code,
                                "version": node.registry_version.version_number,
                                "feature_version_id": version_id,
                                "security_id": row.security_id,
                                "value": row.value,
                                "value_status": row.value_status.value,
                                "quality_flags": row.quality_flags,
                                "source_max_available_at": row.source_max_available_at,
                            }
                        )
                total_rows += len(rows)
                if total_rows > settings.preview_max_rows:
                    raise FeaturePlatformError(
                        "PREVIEW_ROW_LIMIT_EXCEEDED",
                        f"preview returned more than {settings.preview_max_rows} rows",
                    )
                evaluations.append(
                    {
                        "as_of_time": as_of,
                        "data_cutoff_time": cutoff,
                        "rows": rows,
                        "quality_summary": quality,
                    }
                )

            return {
                "preview_id": preview_id,
                "persisted": False,
                "non_canonical": bool(request.preview_overrides),
                "code_revision": self.code_revision or _code_revision(),
                "plan_checksum": plan.plan_checksum,
                "scope": resolved["scope"],
                "features": [
                    {
                        "feature_code": plan.nodes_by_id[version_id].registry_version.feature_code,
                        "version": plan.nodes_by_id[version_id].registry_version.version_number,
                        "manifest_checksum": plan.nodes_by_id[
                            version_id
                        ].registry_version.manifest_checksum,
                    }
                    for version_id in plan.root_version_ids
                ],
                "standard_config": {
                    name: spec.default
                    for version_id in plan.root_version_ids
                    for name, spec in resolved["catalog"]
                    .get(
                        plan.nodes_by_id[version_id].registry_version.feature_code,
                        plan.nodes_by_id[version_id].registry_version.version_number,
                    )
                    .preview_parameters.items()
                },
                "preview_overrides": request.preview_overrides,
                "evaluations": evaluations,
                "warnings": resolved["warnings"],
            }
        finally:
            _PREVIEW_SEMAPHORE.release()

    def preview_backfill(self, request: FeatureBackfillRequest) -> dict[str, Any]:
        resolved = self._resolve_scope(request, enforce_preview_limits=False)
        settings = self._settings()
        scope = resolved["scope"]
        violations: list[str] = []
        limits = (
            ("security_count", scope["security_count"], settings.backfill_max_securities),
            ("evaluation_count", scope["evaluation_count"], settings.backfill_max_evaluations),
            ("execution_cells", scope["estimated_execution_cells"], settings.backfill_max_execution_cells),
            ("max_concurrency", request.max_concurrency, settings.backfill_max_concurrency_per_job),
        )
        for name, actual, limit in limits:
            if actual > limit:
                violations.append(f"{name} {actual} exceeds backfill limit {limit}")
        if violations:
            raise FeaturePlatformError("BACKFILL_LIMIT_EXCEEDED", "; ".join(sorted(set(violations))))
        canonical = self._backfill_confirmation_payload(request, resolved)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.backfill_confirmation_ttl_seconds
        )
        token = self._sign_backfill_confirmation(canonical, expires_at)
        return {
            "run_count": len(resolved["evaluations"]),
            "subject_count": len(resolved["security_ids"]),
            "estimated_execution_cells": scope["estimated_execution_cells"],
            "max_concurrency": request.max_concurrency,
            "scope": scope,
            "plan": resolved["plan"].snapshot(),
            "security_sample": resolved["securities"][:10],
            "evaluations": [
                {"as_of_time": as_of, "data_cutoff_time": cutoff}
                for as_of, cutoff in zip(resolved["evaluations"], resolved["cutoffs"])
            ],
            "warnings": resolved["warnings"],
            "confirmation_token": token,
            "confirmation_expires_at": expires_at,
        }

    def create_backfill(self, request: FeatureBackfillRequest) -> dict[str, Any]:
        if not request.confirmation_token:
            raise FeaturePlatformError(
                "BACKFILL_CONFIRMATION_REQUIRED",
                "preview the backfill and provide its confirmation token",
                status_code=409,
            )
        resolved = self._resolve_scope(request, enforce_preview_limits=False)
        canonical = self._backfill_confirmation_payload(request, resolved)
        self._verify_backfill_confirmation(request.confirmation_token, canonical)
        settings = self._settings()
        if request.max_concurrency > settings.backfill_max_concurrency_per_job:
            raise FeaturePlatformError(
                "BACKFILL_CONCURRENCY_EXCEEDED",
                f"max_concurrency exceeds {settings.backfill_max_concurrency_per_job}",
            )
        plan = resolved["plan"]
        evaluations = resolved["evaluations"]
        cutoffs = resolved["cutoffs"]
        cutoff_values = {
            _rfc3339z(as_of): _rfc3339z(cutoff)
            for as_of, cutoff in zip(evaluations, cutoffs)
        }
        payload = {
            "root_feature_version_ids": list(plan.root_version_ids),
            "start_as_of": _rfc3339z(evaluations[0]),
            "end_as_of": _rfc3339z(evaluations[-1]),
            "step": "explicit",
            "explicit_as_of_times": [_rfc3339z(value) for value in evaluations],
            "data_cutoff_policy": {"mode": "explicit", "values": cutoff_values},
            "source_profile": request.source_profile,
            "market": request.market,
            "universe_request": {
                "requested_mode": request.universe.mode,
                "security_ids": resolved["security_ids"],
                "universe_hash": resolved["scope"]["universe_hash"],
            },
            "universe_hash": resolved["scope"]["universe_hash"],
            "security_ids": resolved["security_ids"],
            "max_concurrency": request.max_concurrency,
            "producer_service": "artemis",
            "code_revision": self.code_revision or _code_revision(),
            "dependency_plan_checksum": plan.plan_checksum,
            "dependency_plan_snapshot": plan.snapshot(),
        }
        result = self.registry_factory(request.source_profile).create_backfill(payload)
        self._backfill_dispatcher().wake(request.source_profile)
        return result

    def list_backfills(
        self,
        source_profile: str = "default",
        *,
        status: str = "",
        market: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        return self.registry_factory(source_profile).list_backfills(
            status=status,
            source_profile=source_profile,
            market=market,
            limit=limit,
            offset=offset,
        )

    def get_backfill(self, backfill_id: str, source_profile: str = "default") -> dict[str, Any]:
        self._ensure_enabled()
        return self.registry_factory(source_profile).get_backfill(backfill_id)

    def cancel_backfill(
        self,
        backfill_id: str,
        source_profile: str = "default",
    ) -> dict[str, Any]:
        self._ensure_enabled()
        return self._backfill_dispatcher().cancel(source_profile, backfill_id)

    def retry_failed_backfill(
        self,
        backfill_id: str,
        source_profile: str = "default",
    ) -> dict[str, Any]:
        self._ensure_enabled()
        result = self.registry_factory(source_profile).retry_failed_backfill(backfill_id)
        self._backfill_dispatcher().wake(source_profile)
        return result

    def _backfill_confirmation_payload(
        self,
        request: FeatureBackfillRequest,
        resolved: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "request": request.model_dump(
                mode="json",
                exclude={"confirmation_token"},
            ),
            "security_ids": resolved["security_ids"],
            "evaluations": [_rfc3339z(value) for value in resolved["evaluations"]],
            "cutoffs": [_rfc3339z(value) for value in resolved["cutoffs"]],
            "plan_checksum": resolved["plan"].plan_checksum,
            "code_revision": self.code_revision or _code_revision(),
        }

    def _sign_backfill_confirmation(
        self,
        canonical: dict[str, Any],
        expires_at: datetime,
    ) -> str:
        payload = {
            "scope_checksum": hashlib.sha256(
                json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "expires_at": int(expires_at.timestamp()),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")
        signature = hmac.new(
            self._settings().backfill_confirmation_secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        return f"{encoded}.{signature}"

    def _verify_backfill_confirmation(
        self,
        token: str,
        canonical: dict[str, Any],
    ) -> None:
        try:
            encoded, provided = token.split(".", 1)
            expected = hmac.new(
                self._settings().backfill_confirmation_secret.encode("utf-8"),
                encoded.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(provided, expected):
                raise ValueError("signature mismatch")
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        except Exception as exc:
            raise FeaturePlatformError(
                "BACKFILL_CONFIRMATION_INVALID",
                "backfill confirmation token is invalid",
                status_code=409,
            ) from exc
        if int(payload.get("expires_at", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise FeaturePlatformError(
                "BACKFILL_CONFIRMATION_EXPIRED",
                "backfill confirmation token expired; preview again",
                status_code=409,
            )
        checksum = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if not hmac.compare_digest(str(payload.get("scope_checksum", "")), checksum):
            raise FeaturePlatformError(
                "BACKFILL_SCOPE_CHANGED",
                "backfill scope changed after preview; preview again",
                status_code=409,
            )

    def compute(self, request: FeatureComputeRequest) -> FeatureComputeResponse:
        self._ensure_enabled()
        catalog = self._loader().load(check_entrypoints=True)
        client = self.registry_factory(request.source_profile)
        plan = DependencyPlanner(client.resolve_version).build(request.features)
        plan.ensure_executable()

        for node in plan.ordered_nodes:
            manifest = catalog.get(
                node.registry_version.feature_code,
                node.registry_version.version_number,
            )
            local_checksum = manifest_registry_checksum(manifest)
            if local_checksum != node.registry_version.manifest_checksum:
                raise FeaturePlatformError(
                    "MANIFEST_CHECKSUM_CONFLICT",
                    (
                        f"local manifest {manifest.identity} checksum {local_checksum} does not match "
                        f"published registry checksum {node.registry_version.manifest_checksum}"
                    ),
                    status_code=409,
                )

        parameters = dict(request.parameters)
        create_payload: dict[str, Any] = {
            "request_fingerprint": "",
            "producer_service": "artemis",
            "trigger_type": request.trigger_type,
            "as_of_time": request.as_of_time.isoformat(),
            "data_cutoff_time": request.data_cutoff_time.isoformat(),
            "source_profile": request.source_profile,
            "market": request.market,
            "universe_hash": _universe_hash(request.security_ids),
            "code_revision": self.code_revision or _code_revision(),
            "root_feature_version_ids": list(plan.root_version_ids),
            "dependency_plan_checksum": plan.plan_checksum,
            "dependency_plan_snapshot": plan.snapshot(),
            "parameters": parameters,
            "force": request.force or bool(request.retry_of_run_id),
        }
        if request.idempotency_key:
            create_payload["producer_run_ref"] = request.idempotency_key
        if request.retry_of_run_id:
            create_payload["retry_of_run_id"] = request.retry_of_run_id

        created = client.create_run(create_payload)
        response = FeatureComputeResponse.model_validate(created)
        if response.reused:
            return response

        try:
            client.batch_subjects(response.run_id, request.security_ids, "feature_compute_request")
            task_request = TaskRunReq.model_validate(
                {
                    "meta": {
                        "run_id": response.run_id,
                        "task_id": response.run_id,
                        "exec_type": TaskMode.ASYNC.value,
                        "task_code": TaskCode.FEATURE_PLATFORM_COMPUTE.value,
                    },
                    "body": {
                        "run_id": response.run_id,
                        "root_features": [item.model_dump(mode="json") for item in request.features],
                        "root_feature_version_ids": list(plan.root_version_ids),
                        "expected_plan_checksum": plan.plan_checksum,
                        "security_ids": request.security_ids,
                        "as_of_time": request.as_of_time.isoformat(),
                        "data_cutoff_time": request.data_cutoff_time.isoformat(),
                        "source_profile": request.source_profile,
                        "market": request.market,
                        # Legacy request parameters are run metadata only. Persisted
                        # feature semantics must come from the versioned manifest.
                        "parameters": {},
                    },
                }
            )
            self.task_engine.run(task_request)
        except Exception:
            try:
                client.cancel_run(response.run_id)
            except Exception:
                pass
            raise
        return response

    def get_execution(self, run_id: str, source_profile: str = "default") -> dict[str, Any]:
        self._ensure_enabled()
        return self.registry_factory(source_profile).get_run(run_id, include_subjects=True)

    def reconcile_stale_runs(
        self,
        source_profile: str = "default",
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self._ensure_enabled()
        timeout = self._settings().stale_run_timeout_seconds
        current = now or datetime.now(timezone.utc)
        stale_before = current.astimezone(timezone.utc) - timedelta(seconds=timeout)
        result = self.registry_factory(source_profile).reconcile_stale_runs(stale_before)
        record_feature_stale_runs(int(result.get("aborted_count", 0)))
        return result
