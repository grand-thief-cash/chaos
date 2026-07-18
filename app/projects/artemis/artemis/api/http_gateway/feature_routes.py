from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import (
    FeatureComputeRequest,
    FeatureComputeResponse,
    ManifestSelectionRequest,
    ManifestValidateRequest,
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


@router.post("/registry/sync", summary="Synchronize selected manifests into PhoenixA")
def sync_feature_registry(
    request: ManifestSelectionRequest = ManifestSelectionRequest(),
    service: FeatureService = Depends(get_feature_service),
):
    try:
        return service.sync_registry(request)
    except FeaturePlatformError as exc:
        _raise_http(exc)
