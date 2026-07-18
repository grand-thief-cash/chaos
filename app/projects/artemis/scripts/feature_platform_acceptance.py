#!/usr/bin/env python3
"""Repeatable Phase 5 Feature Platform acceptance harness.

Managed mode builds and starts isolated PhoenixA/Artemis processes on temporary
ports, exercises the full persisted workflow, restarts both services, and then
verifies persistence and idempotency against the same database.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

from artemis.feature_platform.domain.models import FeatureManifest
from artemis.feature_platform.manifests.checksum import registry_projection
from artemis.feature_platform.manifests.loader import FeatureManifestLoader


ARTEMIS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
PHOENIXA_ROOT = REPO_ROOT / "app" / "projects" / "phoenixA"
CATALOG_ROOT = ARTEMIS_ROOT / "config" / "feature_catalog"
FEATURE_CODE = "platform.security.constant_one"
PIT_FEATURE_CODE = "platform.security.datafield_pit_probe"
TERMINAL_STATUSES = {"succeeded", "failed", "aborted", "cancelled"}


class AcceptanceError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


class JsonClient:
    def __init__(self, base_url: str, timeout: float = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any | None = None,
        params: dict[str, Any] | None = None,
        expected: set[int] | None = None,
    ) -> tuple[int, Any]:
        url = self.base_url + path
        if params:
            normalized = {key: value for key, value in params.items() if value is not None}
            url += "?" + urlencode(normalized, doseq=True)
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = Request(url, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
        except (OSError, URLError) as exc:
            raise AcceptanceError(f"{method} {url} failed: {exc}") from exc
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", errors="replace")
        allowed = expected or set(range(200, 300))
        if status not in allowed:
            raise AcceptanceError(f"{method} {url} returned {status}: {payload}")
        return status, payload

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)[1]

    def post(self, path: str, body: Any, **kwargs) -> tuple[int, Any]:
        return self.request("POST", path, body=body, **kwargs)

    def patch(self, path: str, body: Any, **kwargs) -> tuple[int, Any]:
        return self.request("PATCH", path, body=body, **kwargs)


class FeaturePlatformAcceptance:
    def __init__(
        self,
        phoenixa_url: str,
        artemis_url: str,
        *,
        source_profile: str,
        timeout_seconds: int,
        security_count: int,
        scenario_id: str,
    ) -> None:
        self.phoenixa = JsonClient(phoenixa_url)
        self.artemis = JsonClient(artemis_url)
        self.source_profile = source_profile
        self.timeout_seconds = timeout_seconds
        self.security_count = security_count
        self.scenario_id = scenario_id

    @staticmethod
    def _step(message: str) -> None:
        print(f"[phase5] {message}", flush=True)

    def _verify_openapi(self) -> None:
        phoenix_spec = self.phoenixa.request("GET", "/openapi.yaml")[1]
        require(
            isinstance(phoenix_spec, str) and "/api/v2/features/registry/sync" in phoenix_spec,
            "PhoenixA OpenAPI does not expose Feature Platform routes",
        )
        artemis_spec = self.artemis.get("/openapi.json")
        paths = artemis_spec.get("paths", {})
        required_paths = {
            "/features/compute",
            "/features/executions/{run_id}",
            "/features/maintenance/reconcile-stale",
            "/features/manifests/validate",
            "/features/registry/sync",
        }
        require(required_paths <= set(paths), "Artemis OpenAPI is missing Feature Platform paths")

    def _sync_registry(self) -> dict[str, Any]:
        validate = self.artemis.post(
            "/features/manifests/validate",
            {"source_profile": self.source_profile, "check_entrypoints": True},
        )[1]
        require(validate.get("valid") is True and int(validate.get("count", 0)) >= 3, "manifest validation failed")

        identities = {f"{FEATURE_CODE}@1", f"{FEATURE_CODE}@2"}
        first = self.artemis.post(
            "/features/registry/sync",
            {"source_profile": self.source_profile, "check_entrypoints": True},
        )[1]
        require(not first.get("rejected"), f"first registry sync rejected manifests: {first.get('rejected')}")
        first_seen = set(first.get("created", [])) | set(first.get("unchanged", []))
        require(identities <= first_seen, "first registry sync did not account for both smoke versions")

        second = self.artemis.post(
            "/features/registry/sync",
            {"source_profile": self.source_profile, "check_entrypoints": True},
        )[1]
        require(not second.get("rejected"), f"second registry sync rejected manifests: {second.get('rejected')}")
        require(identities <= set(second.get("unchanged", [])), "second registry sync was not idempotent")
        return {"first": first, "second": second}

    def _definition_versions(self) -> tuple[dict[str, Any], dict[int, int]]:
        detail = self.phoenixa.get(f"/api/v2/features/definitions/{FEATURE_CODE}")
        versions: dict[int, int] = {}
        for summary in detail.get("versions", []):
            version = summary.get("version", {})
            number = int(version.get("version_number", 0))
            if number in {1, 2}:
                require(version.get("status") == "published", f"{FEATURE_CODE}@{number} is not published")
                versions[number] = int(version["id"])
        require(set(versions) == {1, 2}, "registry does not contain published smoke V1 and V2")
        return detail, versions

    def _pit_version_id(self) -> int:
        detail = self.phoenixa.get(f"/api/v2/features/definitions/{PIT_FEATURE_CODE}")
        for summary in detail.get("versions", []):
            version = summary.get("version", {})
            if int(version.get("version_number", 0)) == 1:
                require(version.get("status") == "published", f"{PIT_FEATURE_CODE}@1 is not published")
                return int(version["id"])
        raise AcceptanceError(f"registry does not contain {PIT_FEATURE_CODE}@1")

    def _security_ids(self) -> list[int]:
        response = self.phoenixa.get("/api/v2/securities", params={"limit": self.security_count})
        security_ids = [int(item["security_id"]) for item in response.get("data", [])]
        require(len(security_ids) == self.security_count, f"expected {self.security_count} active securities")
        require(len(set(security_ids)) == len(security_ids), "security registry returned duplicate IDs")
        return security_ids

    def _compute_payload(self, version: int, security_ids: list[int], as_of: str) -> dict[str, Any]:
        return {
            "features": [{"code": FEATURE_CODE, "version": version}],
            "security_ids": security_ids,
            "as_of_time": as_of,
            "data_cutoff_time": as_of,
            "market": "zh_a",
            "source_profile": self.source_profile,
            "trigger_type": "manual",
            "idempotency_key": f"{self.scenario_id}-v{version}",
            "parameters": {"acceptance_scenario": self.scenario_id},
        }

    def _wait_for_run(self, run_id: str) -> tuple[dict[str, Any], list[str]]:
        deadline = time.monotonic() + self.timeout_seconds
        observed: list[str] = []
        while time.monotonic() < deadline:
            detail = self.artemis.get(
                f"/features/executions/{run_id}",
                params={"source_profile": self.source_profile},
            )
            status = str(detail.get("run", {}).get("status", "unknown"))
            if not observed or observed[-1] != status:
                observed.append(status)
            if status in TERMINAL_STATUSES:
                require(status == "succeeded", f"run {run_id} terminated as {status}: {detail.get('run')}")
                return detail, observed
            time.sleep(0.2)
        raise AcceptanceError(f"run {run_id} did not finish within {self.timeout_seconds}s; observed={observed}")

    def _compute_and_assert(
        self,
        version: int,
        expected_value: float,
        security_ids: list[int],
        as_of: str,
    ) -> dict[str, Any]:
        payload = self._compute_payload(version, security_ids, as_of)
        status, submitted = self.artemis.post("/features/compute", payload, expected={200, 202})
        require(status in {200, 202}, "compute returned an unexpected status")
        run_id = str(submitted.get("run_id", ""))
        require(run_id, "compute response omitted run_id")
        detail, observed = self._wait_for_run(run_id)
        run = detail["run"]
        require(run.get("started_at") and run.get("finished_at"), f"run {run_id} lacks persisted timing evidence")
        require(len(detail.get("subjects", [])) == len(security_ids), f"run {run_id} subject snapshot mismatch")
        require(len(detail.get("items", [])) == 1, f"run {run_id} expected exactly one RunItem")
        item = detail["items"][0]
        require(item.get("status") == "succeeded", f"run {run_id} item did not succeed")
        require(int(item.get("valid_count", 0)) == len(security_ids), f"run {run_id} quality count mismatch")

        values = self.phoenixa.get(
            "/api/v2/features/values/numeric",
            params={
                "feature_code": FEATURE_CODE,
                "version": version,
                "run_id": run_id,
                "limit": len(security_ids) + 5,
            },
        )
        rows = values.get("items", [])
        require(len(rows) == len(security_ids), f"run {run_id} value count mismatch")
        require({int(row["security_id"]) for row in rows} == set(security_ids), f"run {run_id} value universe mismatch")
        require(all(float(row["value"]) == expected_value for row in rows), f"run {run_id} value mismatch")
        require(all(row.get("value_status") == "valid" for row in rows), f"run {run_id} has non-valid smoke rows")

        reused_status, reused = self.artemis.post("/features/compute", payload, expected={200, 202})
        require(reused_status == 200 and reused.get("reused") is True, f"run {run_id} was not reused")
        require(reused.get("run_id") == run_id, "idempotent compute returned a different run")
        return {
            "run_id": run_id,
            "request": payload,
            "observed_statuses": observed,
            "code_revision": run.get("code_revision"),
        }

    def _assert_latest_and_history(
        self,
        security_ids: list[int],
        version_ids: dict[int, int],
        run_ids: dict[int, str],
    ) -> None:
        common = {"feature_code": FEATURE_CODE, "security_ids": ",".join(map(str, security_ids)), "limit": 100}
        latest = self.phoenixa.get("/api/v2/features/values/numeric/latest", params=common)
        latest_rows = latest.get("items", [])
        require(len(latest_rows) == len(security_ids), "latest query did not return the full V2 universe")
        require(all(int(row["feature_version_id"]) == version_ids[2] for row in latest_rows), "latest did not select V2")
        require(all(row["run_id"] == run_ids[2] and float(row["value"]) == 2.0 for row in latest_rows), "latest V2 evidence mismatch")

        v1 = self.phoenixa.get(
            "/api/v2/features/values/numeric",
            params={**common, "version": 1, "run_id": run_ids[1]},
        )
        v1_rows = v1.get("items", [])
        require(len(v1_rows) == len(security_ids), "explicit V1 query did not return the full universe")
        require(all(int(row["feature_version_id"]) == version_ids[1] for row in v1_rows), "explicit V1 selected a different version")
        require(all(row["run_id"] == run_ids[1] for row in v1_rows), "explicit V1 cannot recover the acceptance run")
        require(all(float(row["value"]) == 1.0 for row in v1_rows), "explicit V1 value mismatch")

    def _assert_governance(self, version_ids: dict[int, int]) -> None:
        lineage = self.phoenixa.get(f"/api/v2/features/lineage/{FEATURE_CODE}")
        lineage_ids = {int(item["feature_version_id"]) for item in lineage.get("versions", [])}
        require(set(version_ids.values()) <= lineage_ids, "lineage does not include both smoke versions")
        availability = self.phoenixa.get(
            f"/api/v2/features/availability/{FEATURE_CODE}",
            params={"source_profile": self.source_profile},
        )
        require(availability.get("latest_published_version_id") == version_ids[2], "availability does not identify V2")
        require(availability.get("latest_succeeded_run"), "availability omits latest succeeded materialization")

    def _assert_published_immutability(self) -> None:
        manifest = FeatureManifestLoader(CATALOG_ROOT).load().get(FEATURE_CODE, 1)
        raw = copy.deepcopy(manifest.model_dump(mode="json"))
        raw["feature"]["description"] += " mutation probe"
        mutated = FeatureManifest.model_validate(raw)
        response = self.phoenixa.post(
            "/api/v2/features/registry/sync",
            {"manifests": [registry_projection(mutated)]},
        )[1]
        rejected = response.get("rejected", [])
        require(len(rejected) == 1, "published mutation was not rejected")
        require(rejected[0].get("code") == "MANIFEST_CHECKSUM_CONFLICT", f"unexpected mutation rejection: {rejected}")

    def _compute_pit(
        self,
        version_id: int,
        security_ids: list[int],
        as_of: str,
    ) -> dict[str, Any]:
        payload = {
            "features": [{"code": PIT_FEATURE_CODE, "version": 1}],
            "security_ids": security_ids,
            "as_of_time": as_of,
            "data_cutoff_time": as_of,
            "market": "zh_a",
            "source_profile": self.source_profile,
            "trigger_type": "manual",
            "idempotency_key": f"{self.scenario_id}-pit-v1",
            "parameters": {"acceptance_scenario": self.scenario_id},
        }
        _, submitted = self.artemis.post("/features/compute", payload, expected={200, 202})
        run_id = str(submitted.get("run_id", ""))
        require(run_id, "PIT compute response omitted run_id")
        detail, observed = self._wait_for_run(run_id)
        require(len(detail.get("subjects", [])) == len(security_ids), "PIT subject snapshot mismatch")
        require(len(detail.get("items", [])) == 1, "PIT run expected exactly one RunItem")
        item = detail["items"][0]
        require(item.get("status") == "succeeded", "PIT RunItem did not succeed")
        require(
            sum(int(item.get(key, 0)) for key in ("valid_count", "missing_count", "invalid_count"))
            == len(security_ids),
            "PIT quality counters do not cover the frozen universe",
        )

        values = self.phoenixa.get(
            "/api/v2/features/values/numeric",
            params={
                "feature_code": PIT_FEATURE_CODE,
                "version": 1,
                "run_id": run_id,
                "limit": len(security_ids) + 5,
            },
        )
        rows = values.get("items", [])
        require(len(rows) == len(security_ids), "PIT value count mismatch")
        cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        for row in rows:
            available_at = row.get("source_max_available_at")
            require(available_at, f"PIT row {row.get('security_id')} lacks source availability evidence")
            parsed = datetime.fromisoformat(str(available_at).replace("Z", "+00:00"))
            require(parsed <= cutoff, f"PIT row {row.get('security_id')} crossed the data cutoff")

        lineage = self.phoenixa.get(f"/api/v2/features/lineage/{PIT_FEATURE_CODE}")
        current = next(
            (version for version in lineage.get("versions", []) if int(version.get("feature_version_id", 0)) == version_id),
            None,
        )
        require(current is not None, "PIT lineage omitted the published version")
        fields = current.get("upstream_data_fields", [])
        require(
            any(
                field.get("source") == "amazing_data"
                and field.get("dataset") == "financial_statement"
                and field.get("data_type") == "income"
                and field.get("raw_field") == "NET_PRO_EXCL_MIN_INT_INC"
                and field.get("contract_version") == "2026-06-27"
                for field in fields
            ),
            "PIT lineage does not preserve the exact DataField contract",
        )
        return {
            "run_id": run_id,
            "request": payload,
            "observed_statuses": observed,
            "quality": {
                "valid": int(item.get("valid_count", 0)),
                "missing": int(item.get("missing_count", 0)),
                "invalid": int(item.get("invalid_count", 0)),
            },
        }

    def _assert_cutoff_violation(
        self,
        version_id: int,
        security_id: int,
        as_of: str,
    ) -> dict[str, Any]:
        universe_hash = hashlib.sha256(json.dumps([security_id], separators=(",", ":")).encode("utf-8")).hexdigest()
        request = {
            "request_fingerprint": "",
            "producer_service": "phase5-acceptance",
            "producer_run_ref": f"{self.scenario_id}-cutoff-violation",
            "trigger_type": "manual",
            "as_of_time": as_of,
            "data_cutoff_time": as_of,
            "source_profile": self.source_profile,
            "market": "zh_a",
            "universe_hash": universe_hash,
            "code_revision": "phase5-cutoff-probe",
            "root_feature_version_ids": [version_id],
            "parameters": {"acceptance_scenario": self.scenario_id, "probe": "cutoff_violation"},
            "force": True,
        }
        _, created = self.phoenixa.post("/api/v2/features/runs", request, expected={200, 202})
        run_id = str(created["run_id"])
        self.phoenixa.post(
            f"/api/v2/features/runs/{run_id}/subjects:batch",
            {"security_ids": [security_id], "included_reason": "phase5_cutoff_probe"},
        )
        self.phoenixa.post(
            f"/api/v2/features/runs/{run_id}/items:batch",
            {"feature_version_ids": [version_id]},
        )
        self.phoenixa.patch(
            f"/api/v2/features/runs/{run_id}",
            {"expected_status": "queued", "new_status": "planning"},
        )
        self.phoenixa.patch(
            f"/api/v2/features/runs/{run_id}",
            {"expected_status": "planning", "new_status": "running"},
        )
        self.phoenixa.patch(
            f"/api/v2/features/runs/{run_id}/items/{version_id}",
            {
                "expected_status": "queued",
                "new_status": "running",
                "input_count": 1,
                "output_count": 1,
                "valid_count": 1,
                "missing_count": 0,
                "invalid_count": 0,
                "duration_ms": 0,
            },
        )
        cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        after_cutoff = cutoff.replace(microsecond=1).isoformat().replace("+00:00", "Z")
        status, rejected = self.phoenixa.post(
            f"/api/v2/features/runs/{run_id}/values/numeric:batch",
            {
                "feature_version_id": version_id,
                "observed_at": as_of,
                "values": [
                    {
                        "security_id": security_id,
                        "value": 1.0,
                        "value_status": "valid",
                        "quality_flags": {"probe": "cutoff_violation"},
                        "source_max_available_at": after_cutoff,
                    }
                ],
            },
            expected={422},
        )
        require(status == 422 and rejected.get("code") == "DATA_CUTOFF_VIOLATION", f"unexpected cutoff result: {rejected}")
        self.phoenixa.post(
            f"/api/v2/features/runs/{run_id}:fail",
            {"error_code": "EXPECTED_CUTOFF_PROBE", "error_message": "Phase 5 negative acceptance probe"},
        )
        return {"run_id": run_id, "status": status, "error_code": rejected.get("code")}

    def exercise(self) -> dict[str, Any]:
        self._step("verify OpenAPI contracts")
        self._verify_openapi()
        self._step("validate and idempotently sync manifests")
        sync = self._sync_registry()
        _, version_ids = self._definition_versions()
        pit_version_id = self._pit_version_id()
        security_ids = self._security_ids()
        as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._step(f"compute V1 for {len(security_ids)} securities")
        v1 = self._compute_and_assert(1, 1.0, security_ids, as_of)
        self._step(f"compute V2 for {len(security_ids)} securities")
        v2 = self._compute_and_assert(2, 2.0, security_ids, as_of)
        self._step(f"compute DataField PIT probe for {len(security_ids)} securities")
        pit = self._compute_pit(pit_version_id, security_ids, as_of)
        cutoff_violation = self._assert_cutoff_violation(pit_version_id, security_ids[0], as_of)
        run_ids = {1: v1["run_id"], 2: v2["run_id"]}
        self._assert_latest_and_history(security_ids, version_ids, run_ids)
        self._assert_governance(version_ids)
        self._assert_published_immutability()
        return {
            "scenario_id": self.scenario_id,
            "as_of_time": as_of,
            "source_profile": self.source_profile,
            "security_ids": security_ids,
            "version_ids": {str(key): value for key, value in version_ids.items()},
            "runs": {"1": v1, "2": v2},
            "pit": {"version_id": pit_version_id, "run": pit, "cutoff_violation": cutoff_violation},
            "sync": sync,
        }

    def verify_after_restart(self, state: dict[str, Any]) -> None:
        self._step("verify persisted runs and values after service restart")
        security_ids = [int(item) for item in state["security_ids"]]
        version_ids = {int(key): int(value) for key, value in state["version_ids"].items()}
        run_ids: dict[int, str] = {}
        for version in (1, 2):
            expected_value = float(version)
            run = state["runs"][str(version)]
            run_id = str(run["run_id"])
            run_ids[version] = run_id
            detail = self.phoenixa.get(
                f"/api/v2/features/runs/{run_id}",
                params={"include_subjects": "true"},
            )
            require(detail.get("run", {}).get("status") == "succeeded", f"run {run_id} was not persisted")
            values = self.phoenixa.get(
                "/api/v2/features/values/numeric",
                params={
                    "feature_code": FEATURE_CODE,
                    "version": version,
                    "run_id": run_id,
                    "limit": len(security_ids) + 5,
                },
            )
            rows = values.get("items", [])
            evidence = [
                {
                    "run_id": row.get("run_id"),
                    "feature_version_id": row.get("feature_version_id"),
                    "security_id": row.get("security_id"),
                    "value": row.get("value"),
                }
                for row in rows
            ]
            require(
                len(rows) == len(security_ids)
                and all(float(row["value"]) == expected_value for row in rows),
                f"run {run_id} values were not persisted: {evidence}",
            )
            status, reused = self.artemis.post("/features/compute", run["request"], expected={200, 202})
            require(status == 200 and reused.get("reused") is True, f"run {run_id} was not reused after restart")
            require(reused.get("run_id") == run_id, f"run {run_id} idempotency changed after restart")
        self._assert_latest_and_history(security_ids, version_ids, run_ids)
        self._assert_governance(version_ids)
        pit = state["pit"]
        pit_run_id = str(pit["run"]["run_id"])
        pit_values = self.phoenixa.get(
            "/api/v2/features/values/numeric",
            params={
                "feature_code": PIT_FEATURE_CODE,
                "version": 1,
                "run_id": pit_run_id,
                "limit": len(security_ids) + 5,
            },
        )
        require(len(pit_values.get("items", [])) == len(security_ids), "PIT values were not persisted after restart")


class ManagedServices:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.tmp = Path(tempfile.mkdtemp(prefix="feature-platform-phase5-"))
        self.phoenixa_process: subprocess.Popen | None = None
        self.artemis_process: subprocess.Popen | None = None
        self.phoenixa_log = self.tmp / "phoenixa.log"
        self.artemis_log = self.tmp / "artemis.log"
        self.phoenixa_config = self.tmp / "phoenixa.yaml"
        self.artemis_config = self.tmp / "artemis.yaml"
        self.phoenixa_binary = self.tmp / "phoenixa"

    @property
    def phoenixa_url(self) -> str:
        return f"http://127.0.0.1:{self.args.phoenixa_port}"

    @property
    def artemis_url(self) -> str:
        return f"http://127.0.0.1:{self.args.artemis_port}"

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    @staticmethod
    def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
        path.chmod(0o600)

    def prepare(self) -> None:
        phoenix_cfg = self._load_yaml(Path(self.args.phoenixa_config))
        phoenix_cfg.setdefault("http_server", {})["address"] = f"127.0.0.1:{self.args.phoenixa_port}"
        data_source = phoenix_cfg["postgres_gorm"]["data_sources"]["security"]
        data_source["migrate_enabled"] = bool(self.args.run_migrations)
        phoenix_cfg.setdefault("logging", {})["output"] = "stdout"
        phoenix_cfg.setdefault("telemetry", {})["enabled"] = False
        self._write_yaml(self.phoenixa_config, phoenix_cfg)

        artemis_cfg = self._load_yaml(Path(self.args.artemis_config))
        artemis_cfg.setdefault("server", {}).update({"host": "127.0.0.1", "port": self.args.artemis_port})
        artemis_cfg.setdefault("dept_services", {}).setdefault("phoenixA", {}).update(
            {"host": "127.0.0.1", "port": self.args.phoenixa_port}
        )
        artemis_cfg.setdefault("logging", {})["output"] = "stdout"
        artemis_cfg.setdefault("telemetry", {})["enabled"] = False
        artemis_cfg.setdefault("engine", {})["feature_platform"] = {
            "enabled": True,
            "manifest_root": str(CATALOG_ROOT),
            "max_parallel_features": 2,
            "write_batch_size": 5000,
            "heartbeat_interval_seconds": 1,
            "stale_run_timeout_seconds": 31536000,
            "plugin_timeout_seconds": 180,
        }
        self._write_yaml(self.artemis_config, artemis_cfg)

        go_bin = self.args.go_bin or shutil.which("go") or "/usr/local/go/bin/go"
        print("[phase5] build isolated PhoenixA binary", flush=True)
        subprocess.run(
            [go_bin, "build", "-o", str(self.phoenixa_binary), "./cmd"],
            cwd=PHOENIXA_ROOT,
            check=True,
        )

    def _revision(self) -> str:
        scope = ["--", "app/projects/artemis", "app/projects/phoenixA"]
        head = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--binary", "HEAD", *scope],
            check=True,
            capture_output=True,
        ).stdout
        status = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "status",
                "--porcelain",
                "--untracked-files=all",
                *scope,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if not status:
            return head

        digest = hashlib.sha256(diff)
        digest.update(status.encode("utf-8"))
        for line in status.splitlines():
            if not line.startswith("?? "):
                continue
            path = REPO_ROOT / line[3:]
            if path.is_file():
                digest.update(path.read_bytes())
        return f"{head}-worktree-{digest.hexdigest()[:12]}"

    def _start_phoenixa(self) -> None:
        log = self.phoenixa_log.open("ab")
        self.phoenixa_process = subprocess.Popen(
            [str(self.phoenixa_binary), f"--config={self.phoenixa_config}"],
            cwd=PHOENIXA_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        self._wait_http(self.phoenixa_url + "/openapi.yaml", self.phoenixa_process, self.phoenixa_log)

    def _start_artemis(self) -> None:
        log = self.artemis_log.open("ab")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ARTEMIS_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        env["ARTEMIS_CODE_REVISION"] = self._revision()
        self.artemis_process = subprocess.Popen(
            [sys.executable, "-m", "artemis.main", f"--config={self.artemis_config}"],
            cwd=ARTEMIS_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        self._wait_http(self.artemis_url + "/openapi.json", self.artemis_process, self.artemis_log)

    @staticmethod
    def _wait_http(url: str, process: subprocess.Popen, log_path: Path, timeout: int = 90) -> None:
        deadline = time.monotonic() + timeout
        last_error = ""
        while time.monotonic() < deadline:
            if process.poll() is not None:
                tail = log_path.read_text("utf-8", errors="replace")[-6000:]
                raise AcceptanceError(f"service exited with {process.returncode}:\n{tail}")
            try:
                with urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.25)
        tail = log_path.read_text("utf-8", errors="replace")[-6000:]
        raise AcceptanceError(f"service did not become ready at {url}: {last_error}\n{tail}")

    @staticmethod
    def _stop(process: subprocess.Popen | None) -> None:
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def start(self) -> None:
        self._start_phoenixa()
        self._start_artemis()

    def restart(self) -> None:
        print("[phase5] restart Artemis and PhoenixA", flush=True)
        self._stop(self.artemis_process)
        self._stop(self.phoenixa_process)
        self._start_phoenixa()
        self._start_artemis()

    def close(self) -> None:
        self._stop(self.artemis_process)
        self._stop(self.phoenixa_process)
        if self.args.keep_runtime:
            print(f"[phase5] retained runtime files at {self.tmp}", flush=True)
        else:
            shutil.rmtree(self.tmp, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Feature Platform Phase 5 acceptance gate")
    parser.add_argument("--managed", action="store_true", help="build and manage isolated local service processes")
    parser.add_argument("--phoenixa-url", default="http://127.0.0.1:8085")
    parser.add_argument("--artemis-url", default="http://127.0.0.1:8084")
    parser.add_argument("--phoenixa-port", type=int, default=18085)
    parser.add_argument("--artemis-port", type=int, default=18084)
    parser.add_argument("--phoenixa-config", default=str(PHOENIXA_ROOT / "config" / "config-home.yaml"))
    parser.add_argument("--artemis-config", default=str(ARTEMIS_ROOT / "config" / "config-home.yaml"))
    parser.add_argument("--go-bin", default="")
    parser.add_argument("--run-migrations", action="store_true")
    parser.add_argument("--source-profile", default="default")
    parser.add_argument("--security-count", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--scenario-id", default=f"phase5-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--report-json", default="", help="optional path for the machine-readable acceptance evidence")
    parser.add_argument("--benchmark-report-json", default="", help="optional PhoenixA read benchmark evidence path")
    parser.add_argument("--benchmark-requests", type=int, default=500)
    parser.add_argument("--benchmark-concurrency", type=int, default=8)
    parser.add_argument("--keep-runtime", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    harness: ManagedServices | None = None
    try:
        phoenixa_url = args.phoenixa_url
        artemis_url = args.artemis_url
        if args.managed:
            harness = ManagedServices(args)
            harness.prepare()
            harness.start()
            phoenixa_url = harness.phoenixa_url
            artemis_url = harness.artemis_url
        acceptance = FeaturePlatformAcceptance(
            phoenixa_url,
            artemis_url,
            source_profile=args.source_profile,
            timeout_seconds=args.timeout_seconds,
            security_count=args.security_count,
            scenario_id=args.scenario_id,
        )
        state = acceptance.exercise()
        restart_verified = False
        if harness:
            harness.restart()
            acceptance = FeaturePlatformAcceptance(
                harness.phoenixa_url,
                harness.artemis_url,
                source_profile=args.source_profile,
                timeout_seconds=args.timeout_seconds,
                security_count=args.security_count,
                scenario_id=args.scenario_id,
            )
            acceptance.verify_after_restart(state)
            restart_verified = True
        state["restart_persistence_verified"] = restart_verified
        if args.benchmark_report_json:
            benchmark = PHOENIXA_ROOT / "scripts" / "benchmark_feature_platform.py"
            subprocess.run(
                [
                    sys.executable,
                    str(benchmark),
                    "--base-url",
                    phoenixa_url,
                    "--run-id",
                    state["runs"]["2"]["run_id"],
                    "--security-ids",
                    ",".join(map(str, state["security_ids"])),
                    "--requests",
                    str(args.benchmark_requests),
                    "--concurrency",
                    str(args.benchmark_concurrency),
                    "--report-json",
                    args.benchmark_report_json,
                ],
                check=True,
            )
            state["benchmark"] = json.loads(Path(args.benchmark_report_json).read_text(encoding="utf-8"))
        state["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if args.report_json:
            report = Path(args.report_json)
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("[phase5] PASS: Feature Platform acceptance gate", flush=True)
        print(json.dumps(state, indent=2, sort_keys=True), flush=True)
        return 0
    except (AcceptanceError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"[phase5] FAIL: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        if harness:
            harness.close()


if __name__ == "__main__":
    raise SystemExit(main())
