"""LLM client — wraps litellm for unified model access with retry & cost tracking."""
from __future__ import annotations

import json
import logging
from typing import Any

import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from atlas.core.config import get_config

logger = logging.getLogger(__name__)

# Suppress litellm info logs
litellm.suppress_debug_info = True


def _get_llm_config() -> dict[str, Any]:
    return get_config()["llm"]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def call_llm(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.1,
    response_format: dict | None = None,
) -> dict[str, Any]:
    """Call LLM and return parsed result with usage info.

    Returns:
        {
            "content": str,           # raw text response
            "parsed": dict | None,    # parsed JSON if response is valid JSON
            "input_tokens": int,
            "output_tokens": int,
            "model": str,
            "cost": float,
        }
    """
    cfg = _get_llm_config()
    model = model or cfg["extraction_model"]

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "timeout": cfg.get("request_timeout", 120),
        "api_key": cfg.get("api_key", ""),
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = await litellm.acompletion(**kwargs)

    content = response.choices[0].message.content or ""
    usage = response.usage
    cost = litellm.completion_cost(completion_response=response)

    # Attempt JSON parse
    parsed = None
    try:
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        parsed = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("LLM response is not valid JSON (model=%s)", model)

    return {
        "content": content,
        "parsed": parsed,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "model": model,
        "cost": cost or 0.0,
    }


async def call_extraction(
    text: str,
    system_prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper: send text for structured extraction."""
    cfg = _get_llm_config()
    model = model or cfg["extraction_model"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]
    return await call_llm(
        messages,
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
    )


async def call_filter(
    text: str,
    prompt: str,
) -> dict[str, Any]:
    """Quick classification using the cheap model."""
    cfg = _get_llm_config()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    return await call_llm(
        messages,
        model=cfg["filter_model"],
        temperature=0.0,
    )


async def call_summary(
    context: str,
    prompt: str,
) -> dict[str, Any]:
    """Generate an analytical summary using the strong model."""
    cfg = _get_llm_config()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": context},
    ]
    return await call_llm(messages, model=cfg["summary_model"], temperature=0.3)

