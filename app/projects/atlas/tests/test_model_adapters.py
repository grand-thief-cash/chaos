import json

import httpx
import pytest

from atlas.core.clients import OpenAICompatiblePDFClient, StructuredChatClient
from atlas.intelligence import StructuredQueryModelAdapter
from atlas.models import (
    ModelEndpointCfg,
    ModelProvider,
    QueryPlan,
    StructuredOutputMode,
)


@pytest.mark.asyncio
async def test_ollama_adapter_sends_json_schema_and_validates_response():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        content = {
            "question": "英伟达的供应链关系？",
            "calls": [{"tool": "search_entities", "arguments": {"query": "英伟达"}}],
            "answer_instruction": "Use grounded claims only",
        }
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(content, ensure_ascii=False)},
                }]
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = ModelEndpointCfg(
        provider=ModelProvider.OLLAMA,
        base_url="http://ollama.test/v1",
        model="qwen3:14b",
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
    )
    client = StructuredChatClient(config, client=http)
    plan = await client.complete_model(
        QueryPlan, system_prompt="system", user_prompt="user"
    )
    assert plan.calls[0].tool == "search_entities"
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_paid_provider_json_object_rejects_empty_output():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
        )

    config = ModelEndpointCfg(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        base_url="https://provider.test/v1",
        model="paid-model",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
    )
    client = StructuredChatClient(
        config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError, match="empty"):
        await client.complete_model(QueryPlan, system_prompt="system", user_prompt="JSON")


@pytest.mark.asyncio
async def test_structured_adapter_regenerates_invalid_json():
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = (
            "not-json"
            if calls == 1
            else json.dumps({
                "question": "q",
                "calls": [],
                "answer_instruction": "grounded",
            })
        )
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": content},
                }]
            },
        )

    config = ModelEndpointCfg(
        provider=ModelProvider.OLLAMA,
        base_url="http://ollama.test/v1",
        model="qwen3:14b",
    )
    client = StructuredChatClient(
        config,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_model(
        QueryPlan, system_prompt="system", user_prompt="user"
    )
    assert result.question == "q"
    assert calls == 2


@pytest.mark.asyncio
async def test_query_model_adapter_never_offers_cypher():
    class CapturingClient:
        prompt = ""

        async def complete_model(self, model, *, system_prompt, user_prompt):
            self.prompt = system_prompt + user_prompt
            return QueryPlan(
                question="q",
                calls=[],
                answer_instruction="grounded",
            )

    client = CapturingClient()
    adapter = StructuredQueryModelAdapter(client)  # type: ignore[arg-type]
    await adapter.plan("q", ["search_entities", "get_claims"])
    assert "run_cypher" not in client.prompt
    assert "search_entities" in client.prompt


@pytest.mark.asyncio
async def test_pdf_adapter_sends_an_in_memory_file_without_temp_path():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {"content": '{"document_assessment":{}}'},
                }]
            },
        )

    client = OpenAICompatiblePDFClient(
        "http://pdf.test/v1",
        "qwen",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.complete_pdf(
        prompt="extract",
        pdf=b"%PDF-test",
        filename="report.pdf",
    )
    file_part = captured["messages"][0]["content"][1]["file"]
    assert file_part["filename"] == "report.pdf"
    assert file_part["file_data"].startswith(
        "data:application/pdf;base64,"
    )
