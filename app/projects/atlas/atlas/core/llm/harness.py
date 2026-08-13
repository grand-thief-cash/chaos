from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable

from atlas.models import LLMHarnessCfg, LLMHarnessStrategy

logger = logging.getLogger(__name__)

_request_providers: ContextVar[tuple[str, ...]] = ContextVar(
    "atlas_llm_harness_request_providers", default=()
)


@dataclass(slots=True)
class _ProviderState:
    consecutive_failures: int = 0
    unavailable_until: float = 0


class FailoverLLMClient:
    """Provider-agnostic stage harness with failover and a small circuit breaker."""

    def __init__(
        self,
        clients: list[tuple[str, Any]],
        config: LLMHarnessCfg,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not clients:
            raise ValueError("LLM harness requires at least one available client")
        self.clients = clients
        self.harness_config = config
        context_windows = [
            getattr(getattr(client, "config", None), "context_window_tokens", 4096)
            for _, client in clients
        ]
        self.config = SimpleNamespace(context_window_tokens=min(context_windows))
        self.clock = clock
        self.model_id = "harness:" + ",".join(name for name, _ in clients)
        self.input_mode = "TEXT_EXTRACTED"
        self._states = {name: _ProviderState() for name, _ in clients}
        self._cursor = 0
        self._lock = asyncio.Lock()

    async def complete_pdf(self, **kwargs: Any) -> str:
        return await self._complete("complete_pdf", kwargs)

    async def complete_text(self, **kwargs: Any) -> str:
        return await self._complete("complete_text", kwargs)

    async def complete_text_validated(
        self,
        *,
        validator: Callable[[str], Any],
        **kwargs: Any,
    ) -> str:
        """Fail over when transport succeeds but business output is invalid.

        Free providers frequently return HTTP 200 with the wrong JSON shape.
        Stage code supplies its parser/evidence validator; a rejected response
        counts as a provider failure and the same request moves to the next
        model instead of retrying the same incompatible model.
        """
        return await self._complete("complete_text", kwargs, validator=validator)

    async def _complete(
        self,
        method_name: str,
        kwargs: dict[str, Any],
        *,
        validator: Callable[[str], Any] | None = None,
    ) -> str:
        errors: list[str] = []
        for name, client in await self._ordered_candidates(method_name):
            try:
                result = await getattr(client, method_name)(**kwargs)
                consume_response_model = getattr(
                    client, "consume_response_model", None
                )
                routed_model = (
                    consume_response_model()
                    if callable(consume_response_model)
                    else None
                )
                if validator is not None:
                    validator(result)
            except Exception as exc:
                self._record_failure(name)
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                logger.warning("LLM harness provider %s failed: %s", name, exc)
                continue
            self._record_success(name)
            provider_label = (
                f"{name}->{routed_model}"
                if routed_model and routed_model != getattr(client, "model_id", None)
                else name
            )
            _request_providers.set(_request_providers.get() + (provider_label,))
            logger.info(
                "LLM harness completed request with provider %s", provider_label
            )
            return result
        raise RuntimeError("all LLM harness providers failed: " + " | ".join(errors))

    async def _ordered_candidates(self, method_name: str) -> list[tuple[str, Any]]:
        now = self.clock()
        capable = [
            item
            for item in self.clients
            if callable(getattr(item[1], method_name, None))
            and self._states[item[0]].unavailable_until <= now
        ]
        if not capable:
            capable = sorted(
                [item for item in self.clients if callable(getattr(item[1], method_name, None))],
                key=lambda item: self._states[item[0]].unavailable_until,
            )[:1]
        if self.harness_config.strategy == LLMHarnessStrategy.BALANCED_FAILOVER and capable:
            async with self._lock:
                offset = self._cursor % len(capable)
                self._cursor += 1
            capable = capable[offset:] + capable[:offset]
        return capable

    def _record_failure(self, name: str) -> None:
        state = self._states[name]
        state.consecutive_failures += 1
        if state.consecutive_failures >= self.harness_config.failure_threshold:
            state.unavailable_until = self.clock() + self.harness_config.cooldown_seconds

    def _record_success(self, name: str) -> None:
        state = self._states[name]
        state.consecutive_failures = 0
        state.unavailable_until = 0

    def status(self) -> dict[str, dict[str, float | int | bool]]:
        now = self.clock()
        return {
            name: {
                "consecutive_failures": state.consecutive_failures,
                "circuit_open": state.unavailable_until > now,
                "retry_after_seconds": max(0, state.unavailable_until - now),
            }
            for name, state in self._states.items()
        }

    @staticmethod
    def consume_request_providers() -> list[str]:
        providers = list(_request_providers.get())
        _request_providers.set(())
        return providers
