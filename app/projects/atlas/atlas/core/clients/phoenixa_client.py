from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from atlas.models import (
    AnalystView,
    ExtractionRun,
    KnowledgeEntity,
    KnowledgeEntityAlias,
    QuantifiedClaim,
    RelationClaim,
    ResearchReport,
    TaxonomyNode,
    TaxonomySchemeCfg,
)


class ExtractionRunStore(Protocol):
    async def create_extraction_run(self, run: ExtractionRun) -> None: ...
    async def update_extraction_run(self, run: ExtractionRun) -> None: ...
    async def save_extraction_result(self, run: ExtractionRun, result: dict[str, Any]) -> None: ...
    async def find_reusable_extraction(
        self,
        source_document_id: str,
        semantic_version: str,
        pipeline_version: str,
        prompt_signature: str,
    ) -> tuple[ExtractionRun, dict[str, Any]] | None: ...


class PhoenixAClient:
    def __init__(
        self,
        base_url: str,
        *,
        research_report_source: str = "eastmoney",
        timeout_seconds: float = 30,
        verify_ssl: bool = True,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.source = research_report_source
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            verify=verify_ssl,
            headers=headers,
        )

    async def list_research_reports(
        self,
        *,
        report_types: list[str],
        published_from: str | None = None,
        published_to: str | None = None,
        limit: int = 100,
    ) -> list[ResearchReport]:
        reports: list[ResearchReport] = []
        per_type = max(1, limit // max(1, len(report_types)))
        for report_type in report_types:
            params = {
                "report_type": report_type,
                "status": "downloaded",
                "start_date": published_from,
                "end_date": published_to,
                "page_size": per_type,
                "page": 1,
            }
            response = await self._client.get(
                f"{self.base_url}/api/v2/research-report/{self.source}/",
                params={key: value for key, value in params.items() if value not in (None, "")},
            )
            response.raise_for_status()
            body = response.json()
            rows = body.get("data", []) if isinstance(body, dict) else body
            if isinstance(rows, dict):
                rows = rows.get("list", [])
            reports.extend(
                ResearchReport(
                    source=row["source"],
                    resource_id=row["resource_id"],
                    report_type=row["report_type"],
                    subject_id=row.get("subject_id"),
                    subject_source_code=row.get("subject_source_code", ""),
                    publish_date=row["publish_date"],
                    title=row.get("title", ""),
                    org_name=row.get("org_name", ""),
                    pdf_object_key=row["pdf_object_key"],
                    status=row["status"],
                    extra=row.get("extra") or {},
                )
                for row in rows
            )
        reports.sort(key=lambda item: (item.publish_date, item.resource_id))
        return reports[:limit]

    async def create_extraction_run(self, run: ExtractionRun) -> None:
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs",
            json=run.model_dump(mode="json"),
        )
        response.raise_for_status()

    async def update_extraction_run(self, run: ExtractionRun) -> None:
        response = await self._client.put(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs/{run.id}",
            json=run.model_dump(mode="json"),
        )
        response.raise_for_status()

    async def save_extraction_result(self, run: ExtractionRun, result: dict[str, Any]) -> None:
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs/{run.id}/result",
            json=result,
        )
        response.raise_for_status()

    async def get_extraction_run(self, run_id: str) -> dict[str, Any]:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs/{run_id}"
        )
        response.raise_for_status()
        return response.json()

    async def find_completed_extraction_run(
        self,
        source_document_id: str,
        semantic_version: str,
        pipeline_version: str,
    ) -> ExtractionRun | None:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs:completed",
            params={
                "source_document_id": source_document_id,
                "semantic_version": semantic_version,
                "pipeline_version": pipeline_version,
            },
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        body = response.json()
        return ExtractionRun.model_validate(body.get("payload", body))

    async def find_reusable_extraction(
        self,
        source_document_id: str,
        semantic_version: str,
        pipeline_version: str,
        prompt_signature: str,
    ) -> tuple[ExtractionRun, dict[str, Any]] | None:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/extraction-runs:reusable",
            params={
                "source_document_id": source_document_id,
                "semantic_version": semantic_version,
                "pipeline_version": pipeline_version,
                "prompt_signature": prompt_signature,
            },
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        body = response.json()
        return (
            ExtractionRun.model_validate(body["payload"]),
            body["result"],
        )

    async def search_graph_entities(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-graph/search",
            params={"q": query, "limit": limit},
        )
        response.raise_for_status()
        return response.json().get("data", [])

    async def get_graph_neighborhood(
        self, entity_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-graph/entities/{entity_id}/neighborhood",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json().get("data", [])

    async def list_claims(
        self, entity_id: str, predicate: str = "", limit: int = 100
    ) -> list[dict[str, Any]]:
        params = {"entity_id": entity_id, "limit": limit}
        if predicate:
            params["predicate"] = predicate
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/claims", params=params
        )
        response.raise_for_status()
        return response.json().get("data", [])

    async def search_securities(self, query: str, limit: int = 20) -> Any:
        response = await self._client.get(
            f"{self.base_url}/api/v2/securities/search",
            params={"q": query, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    async def query_financial_metrics(
        self,
        *,
        source: str,
        statement_type: str,
        security_id: int,
        start_date: str = "",
        end_date: str = "",
    ) -> Any:
        params: dict[str, Any] = {"security_id": security_id}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        response = await self._client.get(
            f"{self.base_url}/api/v2/financial/{source}/{statement_type}/",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def list_taxonomy_nodes(
        self, scheme_name: str, scheme: TaxonomySchemeCfg
    ) -> list[TaxonomyNode]:
        page = 1
        result: list[TaxonomyNode] = []
        while True:
            response = await self._client.get(
                f"{self.base_url}/api/v2/taxonomy/"
                f"{scheme.source}/{scheme.taxonomy}/{scheme.market}/categories",
                params={"page": page, "page_size": 1000},
            )
            response.raise_for_status()
            body = response.json()
            rows = body.get("list", [])
            for row in rows:
                attributes = row.get("attrs") or {}
                if isinstance(attributes, str):
                    try:
                        attributes = json.loads(attributes)
                    except json.JSONDecodeError:
                        attributes = {}
                result.append(TaxonomyNode(
                    scheme=scheme_name,
                    code=row["code"],
                    name=row["name"],
                    level=max(1, int(row.get("level") or 1)),
                    parent_code=row.get("parent_code"),
                    description=(
                        attributes.get("description")
                        or attributes.get("definition")
                    ),
                ))
            if len(result) >= int(body.get("total", len(result))) or not rows:
                return result
            page += 1

    async def save_governance_record(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/governance/{kind}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def list_governance_records(
        self, kind: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/governance/{kind}",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json().get("data", [])

    async def search_knowledge_entities(
        self,
        query: str,
        entity_type: str = "",
        limit: int = 20,
        *,
        exact: bool = True,
    ) -> list[dict[str, Any]]:
        params = {"q": query, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        response = await self._client.get(
            f"{self.base_url}/api/v1/atlas-kg/entities",
            params={**params, **({"match": "exact"} if exact else {})},
        )
        response.raise_for_status()
        return response.json().get("data", [])

    async def upsert_knowledge_entities(
        self, entities: list[KnowledgeEntity]
    ) -> None:
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/entities:batch",
            json=[item.model_dump(mode="json") for item in entities],
        )
        response.raise_for_status()

    async def upsert_entity_aliases(
        self, aliases: list[KnowledgeEntityAlias]
    ) -> None:
        if not aliases:
            return
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/entity-aliases:batch",
            json=[item.model_dump(mode="json") for item in aliases],
        )
        response.raise_for_status()

    async def upsert_security_entity_links(self, links: list[dict[str, Any]]) -> None:
        if not links:
            return
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/security-entity-links:batch",
            json=links,
        )
        response.raise_for_status()

    async def upsert_claims(
        self,
        relations: list[RelationClaim],
        quantified: list[QuantifiedClaim],
        views: list[AnalystView],
    ) -> None:
        payload: list[dict[str, Any]] = []
        for claim in relations:
            body = claim.model_dump(mode="json")
            payload.append({
                "id": str(claim.id),
                "claim_type": "RELATION",
                "source_document_id": claim.source_document_id,
                "subject_entity_id": str(claim.subject_entity_id),
                "object_entity_id": str(claim.object_entity_id),
                "canonical_predicate": claim.canonical_predicate,
                "assertion_type": claim.assertion_type.value,
                "status": claim.status,
                "payload": body,
            })
        for claim in quantified:
            body = claim.model_dump(mode="json")
            payload.append({
                "id": str(claim.id),
                "claim_type": "QUANTIFIED",
                "source_document_id": claim.source_document_id,
                "subject_entity_id": str(claim.subject_entity_id),
                "canonical_predicate": "",
                "assertion_type": claim.assertion_type.value,
                "status": claim.status,
                "payload": body,
            })
        for view in views:
            body = view.model_dump(mode="json")
            payload.append({
                "id": str(view.id),
                "claim_type": "ANALYST_VIEW",
                "source_document_id": view.source_document_id,
                "subject_entity_id": str(view.subject_entity_id) if view.subject_entity_id else None,
                "canonical_predicate": "",
                "assertion_type": view.assertion_type.value,
                "status": view.status,
                "payload": body,
            })
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-kg/claims:batch", json=payload
        )
        response.raise_for_status()

    async def project_graph(
        self, entities: list[KnowledgeEntity], claims: list[RelationClaim]
    ) -> None:
        response = await self._client.post(
            f"{self.base_url}/api/v1/atlas-graph/projection:batch",
            json={
                "entities": [item.model_dump(mode="json") for item in entities],
                "claims": [{
                    **item.model_dump(mode="json"),
                    "subject_entity_id": str(item.subject_entity_id),
                    "object_entity_id": str(item.object_entity_id),
                } for item in claims],
            },
        )
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
