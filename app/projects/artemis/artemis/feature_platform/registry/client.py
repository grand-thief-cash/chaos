from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.domain.models import FeatureManifest, RegistryFeatureVersion
from artemis.feature_platform.manifests.checksum import registry_projection


class FeatureRegistryClient:
    """Typed adapter over PhoenixA's strict Phase 1 Feature Platform API."""

    BASE_PATH = "/api/v2/features"

    def __init__(self, transport: Any) -> None:
        if not all(hasattr(transport, method) for method in ("get", "post")):
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                "PhoenixA HTTP transport is not configured",
                status_code=503,
            )
        self.transport = transport

    @staticmethod
    def _json(response: Any) -> Any:
        status = int(getattr(response, "status_code", 500))
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if not 200 <= status < 300:
            code = payload.get("code") if isinstance(payload, dict) else None
            message = payload.get("error") if isinstance(payload, dict) else None
            if not message:
                message = str(getattr(response, "text", "PhoenixA request failed"))[:500]
            raise FeaturePlatformError(
                str(code or "PHOENIXA_REQUEST_FAILED"),
                str(message or "PhoenixA request failed"),
                status_code=status,
            )
        return payload

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return self._json(self.transport.get(path, params=params))
        except FeaturePlatformError:
            raise
        except Exception as exc:
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                f"PhoenixA GET {path} failed: {exc}",
                status_code=503,
            ) from exc

    def _post(self, path: str, payload: Any) -> Any:
        try:
            return self._json(self.transport.post(path, payload))
        except FeaturePlatformError:
            raise
        except Exception as exc:
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                f"PhoenixA POST {path} failed: {exc}",
                status_code=503,
            ) from exc

    def _patch(self, path: str, payload: Any) -> Any:
        if not hasattr(self.transport, "patch"):
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                "PhoenixA HTTP transport does not support PATCH",
                status_code=503,
            )
        try:
            return self._json(self.transport.patch(path, payload))
        except FeaturePlatformError:
            raise
        except Exception as exc:
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                f"PhoenixA PATCH {path} failed: {exc}",
                status_code=503,
            ) from exc

    def sync_manifests(self, manifests: Iterable[FeatureManifest]) -> dict[str, Any]:
        payload = {"manifests": [registry_projection(manifest) for manifest in manifests]}
        return dict(self._post(f"{self.BASE_PATH}/registry/sync", payload))

    def get_definition(self, feature_code: str) -> dict[str, Any]:
        return dict(self._get(f"{self.BASE_PATH}/definitions/{feature_code}"))

    def get_version(self, version_id: int) -> dict[str, Any]:
        return dict(self._get(f"{self.BASE_PATH}/versions/{version_id}"))

    def resolve_version(self, feature_code: str, version_number: int) -> RegistryFeatureVersion:
        detail = self.get_definition(feature_code)
        definition = detail.get("definition") or {}
        matches = [
            item
            for item in detail.get("versions", [])
            if int((item.get("version") or {}).get("version_number", 0)) == version_number
        ]
        if not matches:
            raise FeaturePlatformError(
                "FEATURE_VERSION_NOT_FOUND",
                f"feature version {feature_code}@{version_number} was not found",
                status_code=404,
            )
        summary = matches[0]
        version = summary.get("version") or {}
        if version.get("status") != "published":
            raise FeaturePlatformError(
                "FEATURE_VERSION_NOT_PUBLISHED",
                f"feature version {feature_code}@{version_number} is {version.get('status', 'unknown')}",
                status_code=422,
            )
        implementations = summary.get("implementations") or []
        canonical = [
            item
            for item in implementations
            if item.get("is_canonical") is True and item.get("status") == "active"
        ]
        if len(canonical) != 1:
            raise FeaturePlatformError(
                "CANONICAL_IMPLEMENTATION_MISSING",
                f"feature version {feature_code}@{version_number} requires one active canonical implementation",
                status_code=422,
            )
        dependencies = sorted(summary.get("dependencies") or [], key=lambda item: int(item.get("ordinal", 0)))
        return RegistryFeatureVersion(
            feature_code=feature_code,
            definition=definition,
            version=version,
            implementation=canonical[0],
            dependencies=dependencies,
        )

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return dict(self._post(f"{self.BASE_PATH}/runs", payload))

    def batch_subjects(self, run_id: str, security_ids: list[int], included_reason: str) -> dict[str, Any]:
        return dict(
            self._post(
                f"{self.BASE_PATH}/runs/{run_id}/subjects:batch",
                {"security_ids": security_ids, "included_reason": included_reason},
            )
        )

    def batch_items(self, run_id: str, feature_version_ids: list[int]) -> dict[str, Any]:
        return dict(
            self._post(
                f"{self.BASE_PATH}/runs/{run_id}/items:batch",
                {"feature_version_ids": sorted(feature_version_ids)},
            )
        )

    def update_run(
        self,
        run_id: str,
        expected_status: str,
        new_status: str,
        *,
        worker_id: str = "",
        heartbeat_at: datetime | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "expected_status": expected_status,
            "new_status": new_status,
        }
        if worker_id:
            payload["worker_id"] = worker_id
        if heartbeat_at is not None:
            payload["heartbeat_at"] = heartbeat_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if error_code or error_message:
            payload["error_code"] = error_code
            payload["error_message"] = error_message[:2000]
        return dict(self._patch(f"{self.BASE_PATH}/runs/{run_id}", payload))

    def update_item(
        self,
        run_id: str,
        feature_version_id: int,
        expected_status: str,
        new_status: str,
        *,
        input_count: int = 0,
        output_count: int = 0,
        valid_count: int = 0,
        missing_count: int = 0,
        invalid_count: int = 0,
        duration_ms: int = 0,
        quality_summary: dict[str, Any] | None = None,
        error_code: str = "",
        error_message: str = "",
    ) -> dict[str, Any]:
        payload = {
            "expected_status": expected_status,
            "new_status": new_status,
            "input_count": input_count,
            "output_count": output_count,
            "valid_count": valid_count,
            "missing_count": missing_count,
            "invalid_count": invalid_count,
            "duration_ms": duration_ms,
            "quality_summary": quality_summary or {},
        }
        if error_code or error_message:
            payload["error_code"] = error_code
            payload["error_message"] = error_message[:2000]
        return dict(
            self._patch(
                f"{self.BASE_PATH}/runs/{run_id}/items/{feature_version_id}",
                payload,
            )
        )

    def write_numeric_values(
        self,
        run_id: str,
        feature_version_id: int,
        observed_at: datetime,
        values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "feature_version_id": feature_version_id,
            "observed_at": observed_at.isoformat(),
            "values": values,
        }
        return dict(self._post(f"{self.BASE_PATH}/runs/{run_id}/values/numeric:batch", payload))

    def complete_run(self, run_id: str) -> dict[str, Any]:
        return dict(self._post(f"{self.BASE_PATH}/runs/{run_id}:complete", {}))

    def fail_run(self, run_id: str, error_code: str, error_message: str) -> dict[str, Any]:
        return dict(
            self._post(
                f"{self.BASE_PATH}/runs/{run_id}:fail",
                {"error_code": error_code, "error_message": error_message[:2000]},
            )
        )

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return dict(self._post(f"{self.BASE_PATH}/runs/{run_id}:cancel", {}))

    def get_run(self, run_id: str, *, include_subjects: bool = True) -> dict[str, Any]:
        return dict(
            self._get(
                f"{self.BASE_PATH}/runs/{run_id}",
                params={"include_subjects": str(include_subjects).lower()},
            )
        )

    def reconcile_stale_runs(
        self,
        stale_before: datetime,
        *,
        producer_service: str = "artemis",
    ) -> dict[str, Any]:
        payload = {
            "stale_before": stale_before.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "producer_service": producer_service,
        }
        return dict(self._post(f"{self.BASE_PATH}/runs:reconcile-stale", payload))

    def query_financial_flat(
        self,
        *,
        source: str,
        data_type: str,
        security_ids: list[int],
        fields: list[str],
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        params = {
            "format": "flat",
            "security_ids": ",".join(str(item) for item in security_ids),
            "fields": ",".join(fields),
            "page": page,
            "page_size": page_size,
        }
        return dict(self._get(f"/api/v2/financial/{source}/{data_type}", params=params))
