from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from artemis.feature_platform.domain.errors import FeaturePlatformError
from artemis.feature_platform.execution.context import FeatureExecutionContext
from artemis.feature_platform.providers.base import DataFieldBatch, DataFieldRecord
from artemis.feature_platform.registry.client import FeatureRegistryClient


class PhoenixAFeatureProvider:
    SUPPORTED_DATASET = "financial_statement"

    def __init__(
        self,
        client: FeatureRegistryClient,
        *,
        security_batch_size: int = 200,
        page_size: int = 1000,
        availability_timezone: str = "Asia/Shanghai",
    ) -> None:
        self.client = client
        self.security_batch_size = max(1, min(int(security_batch_size), 1000))
        self.page_size = max(1, min(int(page_size), 1000))
        self.availability_tz = ZoneInfo(availability_timezone)

    def _available_at(self, row: dict) -> datetime:
        raw = str(row.get("actual_ann_date") or row.get("ann_date") or "").strip()
        if not raw:
            raise FeaturePlatformError(
                "INPUT_SCHEMA_INVALID",
                "financial statement row lacks ann_date and actual_ann_date",
            )
        try:
            parsed = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError as exc:
            raise FeaturePlatformError(
                "INPUT_SCHEMA_INVALID",
                f"invalid financial availability date {raw!r}",
            ) from exc
        return parsed.replace(tzinfo=self.availability_tz)

    def load_data_field(self, ctx: FeatureExecutionContext, dependency: dict) -> DataFieldBatch:
        if dependency.get("dataset") != self.SUPPORTED_DATASET:
            raise FeaturePlatformError(
                "SOURCE_UNAVAILABLE",
                f"Phase 2 provider does not support dataset {dependency.get('dataset')!r}",
            )
        required = ("source", "dataset", "data_type", "raw_field", "contract_version")
        if any(not dependency.get(field) for field in required):
            raise FeaturePlatformError(
                "DATA_FIELD_DEPENDENCY_INVALID",
                "data field dependency is incomplete",
            )

        raw_field = str(dependency["raw_field"])
        fields = [
            "security_id",
            "reporting_period",
            "report_type",
            "statement_code",
            "ann_date",
            "actual_ann_date",
            raw_field,
        ]
        requested = list(ctx.security_ids)
        requested_set = set(requested)
        records: list[DataFieldRecord] = []
        for start in range(0, len(requested), self.security_batch_size):
            security_batch = requested[start : start + self.security_batch_size]
            page = 1
            while True:
                response = self.client.query_financial_flat(
                    source=str(dependency["source"]),
                    data_type=str(dependency["data_type"]),
                    security_ids=security_batch,
                    fields=fields,
                    page=page,
                    page_size=self.page_size,
                )
                if response.get("dataset") != dependency["dataset"]:
                    raise FeaturePlatformError(
                        "INPUT_SCHEMA_INVALID",
                        "PhoenixA financial response dataset does not match the frozen dependency",
                    )
                if response.get("source") != dependency["source"] or response.get("data_type") != dependency["data_type"]:
                    raise FeaturePlatformError(
                        "INPUT_SCHEMA_INVALID",
                        "PhoenixA financial response source/data_type does not match the frozen dependency",
                    )
                rows = response.get("rows") or []
                if not isinstance(rows, list):
                    raise FeaturePlatformError("INPUT_SCHEMA_INVALID", "PhoenixA financial rows must be a list")
                for row in rows:
                    security_id = int(row.get("security_id", 0) or 0)
                    if security_id not in requested_set:
                        raise FeaturePlatformError(
                            "INVALID_SUBJECT",
                            f"PhoenixA returned security_id {security_id} outside the requested universe",
                        )
                    available_at = self._available_at(row)
                    # This client-side gate is authoritative. The existing
                    # financial API's ann_date_before filter does not account
                    # for actual_ann_date and therefore is not used as a PIT gate.
                    if available_at > ctx.data_cutoff_time:
                        continue
                    records.append(
                        DataFieldRecord(
                            security_id=security_id,
                            value=row.get(raw_field),
                            available_at=available_at,
                            reporting_period=str(row.get("reporting_period") or ""),
                            metadata={
                                "ann_date": row.get("ann_date"),
                                "actual_ann_date": row.get("actual_ann_date"),
                                "report_type": row.get("report_type"),
                                "statement_code": row.get("statement_code"),
                            },
                        )
                    )
                total = int(response.get("total", len(rows)) or 0)
                if page * self.page_size >= total or not rows:
                    break
                page += 1
                if page > 10000:
                    raise FeaturePlatformError(
                        "SOURCE_UNAVAILABLE",
                        "PhoenixA financial pagination exceeded the safety limit",
                    )
        records.sort(key=lambda item: (item.security_id, item.available_at, item.reporting_period))
        return DataFieldBatch(dependency=dict(dependency), records=tuple(records))
