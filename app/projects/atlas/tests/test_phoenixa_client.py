import httpx
import pytest

from atlas.core.clients import PhoenixAClient


@pytest.mark.asyncio
async def test_research_report_adapter_projects_only_its_strict_contract():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/research-report/eastmoney/"
        return httpx.Response(
            200,
            json={
                "data": [{
                    "id": 99,
                    "source": "eastmoney",
                    "resource_id": "r1",
                    "report_type": "stock",
                    "subject_id": 42,
                    "subject_source_code": "000001",
                    "publish_date": "2026-01-01",
                    "title": "Report",
                    "org_name": "Broker",
                    "pdf_object_key": "stock/r1.pdf",
                    "pdf_url": "ignored",
                    "detail_url": "ignored",
                    "status": "downloaded",
                    "extra": {"rating": "buy"},
                    "created_at": "ignored",
                    "updated_at": "ignored",
                }],
                "total": 1,
            },
        )

    client = PhoenixAClient(
        "http://phoenix.test",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    reports = await client.list_research_reports(
        report_types=["stock"],
        limit=1,
    )
    assert reports[0].document_id == "eastmoney:r1"
    assert reports[0].extra == {"rating": "buy"}


@pytest.mark.asyncio
async def test_entity_candidate_lookup_can_request_exact_alias_match():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"data": []})

    client = PhoenixAClient(
        "http://phoenix.test",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.search_knowledge_entities(
        "nvidia",
        "COMPANY",
        20,
    )
    assert captured == {
        "q": "nvidia",
        "limit": "20",
        "entity_type": "COMPANY",
        "match": "exact",
    }
