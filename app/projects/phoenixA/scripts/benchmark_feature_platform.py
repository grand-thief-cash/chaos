#!/usr/bin/env python3
"""Run a repeatable read-only benchmark against PhoenixA Feature Platform APIs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile + 0.5)))
    return ordered[index]


def latency_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min_ms": round(min(values), 3),
        "mean_ms": round(statistics.fmean(values), 3),
        "p50_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "p99_ms": round(percentile(values, 0.99), 3),
        "max_ms": round(max(values), 3),
    }


def memory_bytes() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024
    return None


class FeatureBenchmark:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.base_url = args.base_url.rstrip("/")
        code = quote(args.feature_code, safe="")
        common = {"feature_code": args.feature_code, "limit": args.value_limit}
        if args.security_ids:
            common["security_ids"] = args.security_ids
        self.endpoints = [
            ("definition", f"/api/v2/features/definitions/{code}"),
            ("lineage", f"/api/v2/features/lineage/{code}"),
            (
                "availability",
                f"/api/v2/features/availability/{code}?{urlencode({'source_profile': args.source_profile})}",
            ),
            ("runs", "/api/v2/features/runs?status=succeeded&limit=100"),
            ("latest_values", f"/api/v2/features/values/numeric/latest?{urlencode(common)}"),
        ]
        if args.run_id:
            run_id = quote(args.run_id, safe="")
            run_query = dict(common)
            run_query["run_id"] = args.run_id
            self.endpoints.extend(
                [
                    ("run_detail", f"/api/v2/features/runs/{run_id}?include_subjects=true"),
                    ("run_values", f"/api/v2/features/values/numeric?{urlencode(run_query)}"),
                ]
            )

    def request(self, name: str, path: str) -> tuple[str, float, str | None]:
        started = time.perf_counter()
        try:
            request = Request(
                self.base_url + path,
                headers={"Accept": "application/json", "User-Agent": "feature-platform-benchmark/1"},
            )
            with urlopen(request, timeout=self.args.timeout_seconds) as response:
                body = response.read()
                if response.status != 200:
                    return name, (time.perf_counter() - started) * 1000, f"HTTP {response.status}"
                json.loads(body)
            return name, (time.perf_counter() - started) * 1000, None
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return name, (time.perf_counter() - started) * 1000, str(exc)

    def run(self) -> dict[str, Any]:
        for name, path in self.endpoints:
            _, _, error = self.request(name, path)
            if error:
                raise RuntimeError(f"preflight failed for {name}: {error}")

        for index in range(self.args.warmup_requests):
            self.request(*self.endpoints[index % len(self.endpoints)])

        samples: dict[str, list[float]] = defaultdict(list)
        errors: list[dict[str, str]] = []
        started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.concurrency) as executor:
            futures = [
                executor.submit(self.request, *self.endpoints[index % len(self.endpoints)])
                for index in range(self.args.requests)
            ]
            for future in concurrent.futures.as_completed(futures):
                name, latency_ms, error = future.result()
                if error:
                    errors.append({"endpoint": name, "error": error})
                else:
                    samples[name].append(latency_ms)
        elapsed = time.perf_counter() - started
        successful = sum(len(values) for values in samples.values())
        all_latencies = [latency for values in samples.values() for latency in values]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "target": self.base_url,
            "feature_code": self.args.feature_code,
            "run_id": self.args.run_id or None,
            "configuration": {
                "requests": self.args.requests,
                "concurrency": self.args.concurrency,
                "warmup_requests": self.args.warmup_requests,
                "timeout_seconds": self.args.timeout_seconds,
                "endpoints": [name for name, _ in self.endpoints],
            },
            "system": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "cpu_count": os.cpu_count(),
                "memory_bytes": memory_bytes(),
            },
            "result": {
                "elapsed_seconds": round(elapsed, 3),
                "successful_requests": successful,
                "failed_requests": len(errors),
                "requests_per_second": round(successful / elapsed, 3) if elapsed else 0,
                "latency": latency_summary(all_latencies),
                "by_endpoint": {name: latency_summary(samples[name]) for name, _ in self.endpoints},
                "errors": errors[:20],
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8085")
    parser.add_argument("--feature-code", default="platform.security.constant_one")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--security-ids", default="", help="optional comma-separated security IDs")
    parser.add_argument("--source-profile", default="default")
    parser.add_argument("--value-limit", type=int, default=100)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--warmup-requests", type=int, default=25)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--report-json", default="")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1 or args.warmup_requests < 0:
        parser.error("requests/concurrency must be positive and warmup-requests cannot be negative")
    return args


def main() -> int:
    args = parse_args()
    try:
        report = FeatureBenchmark(args).run()
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.report_json:
        path = Path(args.report_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["result"]["failed_requests"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
