from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import (
    FeatureBackfillRequest,
    FeatureComputeRequest,
    FeatureComputeResponse,
    FeaturePreviewRequest,
    FeatureScopeRequest,
    ManifestCatalogResponse,
    ManifestSelectionRequest,
    ManifestValidateRequest,
    RegistrySyncPreviewResponse,
    RegistrySyncRequest,
)
from artemis.services.feature_service import FeatureService


router = APIRouter(prefix="/features", tags=["features"])


def get_feature_service() -> FeatureService:
    # Imported lazily to avoid a routes <-> feature_routes import cycle while
    # retaining the gateway's process-wide TaskEngine cancellation registry.
    from artemis.api.http_gateway.routes import engine

    return FeatureService(engine)


def _raise_http(exc: FeaturePlatformError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.as_dict()) from exc


@router.post(
    "/compute",
    response_model=FeatureComputeResponse,
    status_code=202,
    summary="Submit a governed feature computation",
    responses={
        200: {"description": "An idempotent request reused an existing run."},
        409: {"description": "The requested run conflicts with persisted state."},
        422: {"description": "The manifest, dependency plan, or request is not executable."},
    },
)
def compute_feature(
    request: FeatureComputeRequest,
    response: Response,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        result = service.compute(request)
        response.status_code = 200 if result.reused else 202
        return result
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.get("/executions/{run_id}", summary="Get persisted feature execution evidence")
def get_feature_execution(
    run_id: str,
    source_profile: str = "default",
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.get_execution(run_id, source_profile)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/scope:resolve", summary="Resolve and estimate a Feature execution scope")
def resolve_feature_scope(
    request: FeatureScopeRequest,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.resolve_scope(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/preview", summary="Compute Feature values without persistence")
def preview_features(
    request: FeaturePreviewRequest,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.preview(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/backfills:preview", summary="Preview and sign a persisted range backfill")
def preview_backfill(
    request: FeatureBackfillRequest,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.preview_backfill(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/backfills", status_code=202, summary="Create and dispatch a confirmed backfill")
def create_backfill(
    request: FeatureBackfillRequest,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.create_backfill(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.get("/backfills", summary="List persisted backfill jobs")
def list_backfills(
    source_profile: str = "default",
    status: str = "",
    market: str = "",
    limit: int = 100,
    offset: int = 0,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.list_backfills(
            source_profile, status=status, market=market, limit=limit, offset=offset
        )
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.get("/backfills/{backfill_id}", summary="Get backfill progress and Run evidence")
def get_backfill(
    backfill_id: str,
    source_profile: str = "default",
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.get_backfill(backfill_id, source_profile)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/backfills/{backfill_id}:cancel", summary="Cancel remaining backfill work")
def cancel_backfill(
    backfill_id: str,
    source_profile: str = "default",
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.cancel_backfill(backfill_id, source_profile)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/backfills/{backfill_id}:retry-failed", status_code=202, summary="Retry failed backfill dates")
def retry_failed_backfill(
    backfill_id: str,
    source_profile: str = "default",
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.retry_failed_backfill(backfill_id, source_profile)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/maintenance/reconcile-stale", summary="Abort stale feature runs")
def reconcile_stale_feature_runs(
    source_profile: str = "default",
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.reconcile_stale_runs(source_profile)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/manifests/validate", summary="Validate feature manifests without persistence")
def validate_feature_manifests(
    request: ManifestValidateRequest = ManifestValidateRequest(),
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.validate_manifests(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.get(
    "/manifests/catalog",
    response_model=ManifestCatalogResponse,
    summary="Inspect the local manifest catalog and Registry alignment",
)
def list_feature_manifest_catalog(
    source_profile: str = "default",
    check_entrypoints: bool = True,
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.list_manifest_catalog(
            source_profile=source_profile,
            check_entrypoints=check_entrypoints,
        )
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post(
    "/registry/sync:preview",
    response_model=RegistrySyncPreviewResponse,
    summary="Preview manifest changes without mutating the Registry",
)
def preview_feature_registry_sync(
    request: ManifestSelectionRequest = ManifestSelectionRequest(),
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.preview_registry_sync(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)


@router.post("/registry/sync", summary="Synchronize selected manifests into PhoenixA")
def sync_feature_registry(
    request: RegistrySyncRequest = RegistrySyncRequest(),
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.sync_registry(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)
