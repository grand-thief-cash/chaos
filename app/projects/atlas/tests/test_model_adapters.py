import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from atlas.core.clients import (
    OllamaChatClient,
    OpenAICompatibleTextPDFClient,
    OpenAICompatiblePDFClient,
    OpenRouterTextPDFClient,
    StructuredChatClient,
    ZhipuTextPDFClient,
)
from atlas.core.errors import ModelPDFUnreadableError, ModelTimeoutError
from atlas.core.llm import KeyPool
from atlas.intelligence import StructuredQueryModelAdapter
from atlas.models import (
    LLMAPIKeyCfg,
    LLMCapabilitiesCfg,
    LLMModelCfg,
    ModelProvider,
    QueryPlan,
    StructuredOutputMode,
    ThinkingMode,
)


def _model_cfg(
    *,
    provider=ModelProvider.OLLAMA,
    base_url="http://ollama.test/v1",
    model="qwen3:14b",
    structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
    capabilities: LLMCapabilitiesCfg | None = None,
    api_key: str = "secret",
    thinking_mode: ThinkingMode | None = None,
    temperature: float = 0,
    maximum_output_tokens: int = 16384,
    context_window_tokens: int = 4096,
) -> LLMModelCfg:
    return LLMModelCfg(
        provider=provider,
        base_url=base_url,
        model=model,
        capabilities=capabilities or LLMCapabilitiesCfg(structured_output=True),
        api_keys=[LLMAPIKeyCfg(key=api_key, max_concurrency=4)],
        structured_output_mode=structured_output_mode,
        thinking_mode=thinking_mode,
        temperature=temperature,
        maximum_output_tokens=maximum_output_tokens,
        context_window_tokens=context_window_tokens,
    )


def _pool(api_key: str = "secret") -> KeyPool:
    return KeyPool([LLMAPIKeyCfg(key=api_key, max_concurrency=4)])


@pytest.mark.asyncio
async def test_ollama_native_adapter_sets_explicit_context_and_json_schema(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"ok":true}'}})

    monkeypatch.setattr(
        ZhipuTextPDFClient,
        "extract_page_delimited_text",
        staticmethod(lambda _: '<atlas_pdf_page number="1">正文</atlas_pdf_page>'),
    )
    config = _model_cfg(
        capabilities=LLMCapabilitiesCfg(
            structured_output=True,
            text_extraction=True,
            response_format_api=True,
        ),
        context_window_tokens=8192,
    )
    client = OllamaChatClient(
        config,
        _pool(""),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    result = await client.complete_pdf(
        prompt="system\n\ntask",
        pdf=b"pdf",
        filename="report.pdf",
        max_tokens=2048,
        response_schema=schema,
    )
    assert result == '{"ok":true}'
    assert captured["think"] is False
    assert captured["format"] == schema
    assert captured["options"]["num_ctx"] == 8192
    assert captured["options"]["num_predict"] == 2048


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
    client = StructuredChatClient(_model_cfg(), _pool(), client=http)
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

    config = _model_cfg(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        base_url="https://provider.test/v1",
        model="paid-model",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
    )
    client = StructuredChatClient(
        config, _pool(), client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
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
        assert request.headers.get("Authorization") == "Bearer secret"
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
    config = _model_cfg(
        provider=ModelProvider.ZHIPU_TEXT,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4.7-flash",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
        capabilities=LLMCapabilitiesCfg(structured_output=True, text_extraction=True),
        thinking_mode=ThinkingMode.DISABLED,
        temperature=0.1,
    )
    client = ZhipuTextPDFClient(
        config, _pool("secret"),
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
    assert "顶层必须且只能包含" not in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_zhipu_text_adapter_supports_sampling_complete_text():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop", "message": {"content": '{"产业链":{"上游":"硅片"}}'}
        }]})

    config = _model_cfg(
        provider=ModelProvider.ZHIPU_TEXT,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4.7-flash",
        capabilities=LLMCapabilitiesCfg(structured_output=True, text_extraction=True),
        thinking_mode=ThinkingMode.DISABLED,
    )
    client = ZhipuTextPDFClient(
        config, _pool("secret"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_text(
        prompt="自由理解文档并返回 JSON", extracted_text="上游为硅片", filename="a.pdf"
    )
    assert result == '{"产业链":{"上游":"硅片"}}'
    assert "上游为硅片" in captured["messages"][1]["content"]


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
    key = LLMAPIKeyCfg(key="fallback", key_env="ZHIPU_API_KEY_TEST")
    monkeypatch.delenv("ZHIPU_API_KEY_TEST", raising=False)
    assert key.resolved_key == "fallback"
    monkeypatch.setenv("ZHIPU_API_KEY_TEST", "from-env")
    assert key.resolved_key == "from-env"


@pytest.mark.asyncio
async def test_nvidia_nim_adapter_uses_generic_extra_body_without_response_format():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers.get("Authorization") == "Bearer nv-secret"
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop",
            "message": {"content": '{"industry_chain":{"upstream":"chip"}}'},
        }]})

    config = _model_cfg(
        provider=ModelProvider.NVIDIA_NIM,
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3.5-lightning-30b-a3b",
        capabilities=LLMCapabilitiesCfg(
            structured_output=True,
            text_extraction=True,
            thinking=True,
            response_format_api=False,
        ),
        api_key="nv-secret",
        thinking_mode=ThinkingMode.DISABLED,
    ).model_copy(update={
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}
    })
    client = OpenAICompatibleTextPDFClient(
        config,
        _pool("nv-secret"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_text(
        prompt="system\n\nextract freely",
        extracted_text="upstream chip supplier",
        filename="a.pdf",
    )
    assert json.loads(result)["industry_chain"]["upstream"] == "chip"
    assert "response_format" not in captured
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["stream"] is False


@pytest.mark.asyncio
async def test_openrouter_free_router_sends_schema_and_reports_actual_model():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "model": "openai/gpt-oss-120b:free",
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": '{"ok":true}'},
            }],
        })

    config = _model_cfg(
        provider=ModelProvider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        structured_output_mode=StructuredOutputMode.JSON_SCHEMA,
        capabilities=LLMCapabilitiesCfg(
            structured_output=True,
            text_extraction=True,
            thinking=True,
            response_format_api=True,
        ),
        api_key="sk-or-test",
        thinking_mode=ThinkingMode.ENABLED,
    ).model_copy(update={"extra_body": {"provider": {"require_parameters": True}}})
    client = OpenRouterTextPDFClient(
        config, _pool("sk-or-test"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_text(
        prompt="system\n\nreturn JSON",
        extracted_text="document",
        filename="sample.pdf",
        response_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    )
    assert result == '{"ok":true}'
    assert captured["model"] == "openrouter/free"
    assert captured["reasoning"] == {"enabled": True}
    assert captured["provider"] == {"require_parameters": True}
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert client.consume_response_model() == "openai/gpt-oss-120b:free"
    assert client.consume_response_model() is None


def test_model_extra_body_cannot_override_core_request_fields():
    with pytest.raises(ValueError, match="protected fields"):
        LLMModelCfg.model_validate({
            **_model_cfg().model_dump(),
            "extra_body": {"model": "override"},
        })


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

    client = StructuredChatClient(
        _model_cfg(),
        _pool(),
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

    config = _model_cfg(
        provider=ModelProvider.OPENAI_COMPATIBLE,
        base_url="https://provider.test/v1",
        model="model",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
    )
    client = StructuredChatClient(
        config,
        _pool(),
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
    config = _model_cfg(
        provider=ModelProvider.ZHIPU_TEXT,
        base_url="https://provider.test/v1",
        model="glm-4.7-flash",
        capabilities=LLMCapabilitiesCfg(structured_output=True, text_extraction=True),
    )
    client = ZhipuTextPDFClient(
        config, _pool("secret"),
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

    config = _model_cfg(
        provider=ModelProvider.OPENAI_COMPATIBLE_PDF,
        base_url="http://pdf.test/v1",
        model="qwen",
        capabilities=LLMCapabilitiesCfg(structured_output=True, pdf_direct=True),
    )
    client = OpenAICompatiblePDFClient(
        config, _pool(),
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


@pytest.mark.asyncio
async def test_openrouter_text_adapter_sends_reasoning_not_thinking(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert request.headers.get("Authorization") == "Bearer sk-or-test"
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
    config = _model_cfg(
        provider=ModelProvider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        model="inclusionai/ling-3.0-flash:free",
        structured_output_mode=StructuredOutputMode.JSON_OBJECT,
        capabilities=LLMCapabilitiesCfg(
            structured_output=True,
            text_extraction=True,
            response_format_api=False,
        ),
        thinking_mode=ThinkingMode.ENABLED,
        api_key="sk-or-test",
    )
    client = OpenRouterTextPDFClient(
        config, _pool("sk-or-test"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await client.complete_pdf(
        prompt="system prompt\n\ntask body",
        pdf=b"pdf",
        filename="report.pdf",
    )
    assert result == '{"ok":true}'
    assert captured["model"] == "inclusionai/ling-3.0-flash:free"
    assert captured["reasoning"] == {"enabled": True}
    assert "thinking" not in captured
    assert "response_format" not in captured
    assert [item["role"] for item in captured["messages"]] == ["system", "user"]
    assert '<atlas_pdf_page number="1">' in captured["messages"][1]["content"]
    assert "task body" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_structured_chat_openrouter_uses_reasoning_parameter():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        content = {
            "question": "q",
            "calls": [],
            "answer_instruction": "grounded",
        }
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(content)},
                }]
            },
        )

    config = _model_cfg(
        provider=ModelProvider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        model="inclusionai/ling-3.0-flash:free",
        thinking_mode=ThinkingMode.ENABLED,
    )
    client = StructuredChatClient(
        config, _pool(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await client.complete_model(QueryPlan, system_prompt="s", user_prompt="u")
    assert captured["reasoning"] == {"enabled": True}
    assert "thinking" not in captured
