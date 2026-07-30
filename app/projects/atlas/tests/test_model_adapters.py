import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from atlas.core.clients import (
    OpenAICompatiblePDFClient,
    StructuredChatClient,
    ZhipuTextPDFClient,
)
from atlas.core.errors import ModelPDFUnreadableError, ModelTimeoutError
from atlas.intelligence import StructuredQueryModelAdapter
from atlas.models import (
    ModelEndpointCfg,
    ModelProvider,
    QueryPlan,
    StructuredOutputMode,
    ThinkingMode,
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
async def test_zhipu_text_adapter_sends_page_markers_json_mode_and_disabled_thinking(
    monkeypatch,
):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": '{"ok":true}'},
                }]
            },
        )

    monkeypatch.setattr(
        ZhipuTextPDFClient,
        "extract_page_delimited_text",
        staticmethod(lambda _: '<atlas_pdf_page number="1">\n正文\n</atlas_pdf_page>'),
    )
    client = ZhipuTextPDFClient(
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4.7-flash",
        api_key="secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_pdf(
        prompt="extract",
        pdf=b"pdf",
        filename="report.pdf",
    )
    assert result == '{"ok":true}'
    assert captured["model"] == "glm-4.7-flash"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["response_format"] == {"type": "json_object"}
    assert [item["role"] for item in captured["messages"]] == ["system", "user"]
    assert '<atlas_pdf_page number="1">' in captured["messages"][1]["content"]
    assert "不要复述任务配置" in captured["messages"][1]["content"]


def test_zhipu_text_adapter_extracts_every_page_and_rejects_image_only_pdf(
    monkeypatch,
):
    class Document:
        def __init__(self, texts):
            self.pages = [SimpleNamespace(extract_text=lambda text=text: text) for text in texts]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    documents = iter([Document(["第一页", "第二页"]), Document([None, ""])])
    monkeypatch.setitem(
        sys.modules,
        "pdfplumber",
        SimpleNamespace(open=lambda _: next(documents)),
    )
    text = ZhipuTextPDFClient.extract_page_delimited_text(b"pdf")
    assert '<atlas_pdf_page number="1">\n第一页' in text
    assert '<atlas_pdf_page number="2">\n第二页' in text
    with pytest.raises(ModelPDFUnreadableError, match="extracted no text"):
        ZhipuTextPDFClient.extract_page_delimited_text(b"image-only")


def test_api_key_environment_overrides_configured_fallback(monkeypatch):
    config = ModelEndpointCfg(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        api_key="fallback",
        api_key_env="ZHIPU_API_KEY_TEST",
        thinking_mode=ThinkingMode.DISABLED,
    )
    monkeypatch.delenv("ZHIPU_API_KEY_TEST", raising=False)
    assert config.resolved_api_key == "fallback"
    monkeypatch.setenv("ZHIPU_API_KEY_TEST", "from-env")
    assert config.resolved_api_key == "from-env"


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
async def test_model_http_retries_rate_limit_before_validating_output():
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({
                        "question": "q",
                        "calls": [],
                        "answer_instruction": "grounded",
                    })},
                }]
            },
        )

    config = ModelEndpointCfg(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        base_url="https://provider.test/v1",
        model="model",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
    )
    client = StructuredChatClient(
        config,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        retry_base_seconds=0,
    )
    result = await client.complete_model(
        QueryPlan, system_prompt="system", user_prompt="user"
    )
    assert result.question == "q"
    assert calls == 2


@pytest.mark.asyncio
async def test_zhipu_read_timeout_is_not_multiplied_by_transport_retries(monkeypatch):
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow model", request=request)

    monkeypatch.setattr(
        ZhipuTextPDFClient,
        "extract_page_delimited_text",
        staticmethod(lambda _: '<atlas_pdf_page number="1">正文</atlas_pdf_page>'),
    )
    client = ZhipuTextPDFClient(
        "https://provider.test/v1",
        "glm-4.7-flash",
        api_key="secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        request_maximum_attempts=4,
        retry_base_seconds=0,
    )
    with pytest.raises(ModelTimeoutError, match="exceeded timeout"):
        await client.complete_pdf(prompt="extract", pdf=b"pdf", filename="a.pdf")
    assert calls == 1


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
