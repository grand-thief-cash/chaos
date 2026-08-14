from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable

from atlas.models import LLMHarnessCfg, LLMHarnessStrategy
from atlas.core.harness_events import HarnessEventRegistry

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
        stage: str = "llm",
        events: HarnessEventRegistry | None = None,
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
        self.stage = stage
        self.events = events
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
            self._emit(
                "PROVIDER_ATTEMPT_STARTED",
                f"阶段 {self.stage} 尝试模型 {name}",
                provider=name,
                details={"operation": method_name},
            )
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
            except Exception as exc:
                self._reject_attempt(name, method_name, exc, validator_rejected=False)
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            if validator is not None:
                try:
                    validator(result)
                except Exception as exc:
                    self._reject_attempt(
                        name, method_name, exc, validator_rejected=True
                    )
                    errors.append(f"{name}: {type(exc).__name__}: {exc}")
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
            self._emit(
                "PROVIDER_ATTEMPT_ACCEPTED",
                f"阶段 {self.stage} 已采用模型 {provider_label}",
                provider=provider_label,
                details={"operation": method_name},
            )
            return result
        self._emit(
            "HARNESS_EXHAUSTED",
            f"阶段 {self.stage} 的所有模型均失败",
            level="ERROR",
            details={"operation": method_name, "failure_count": len(errors)},
        )
        raise RuntimeError("all LLM harness providers failed: " + " | ".join(errors))

    def _reject_attempt(
        self,
        name: str,
        method_name: str,
        exc: Exception,
        *,
        validator_rejected: bool,
    ) -> None:
        self._record_failure(name)
        logger.warning("LLM harness provider %s failed: %s", name, exc)
        failure_kind = "业务输出校验未通过" if validator_rejected else "调用失败"
        self._emit(
            "PROVIDER_ATTEMPT_FAILED",
            f"模型 {name}{failure_kind}，Harness 将尝试下一候选",
            level="WARNING",
            provider=name,
            details={
                "operation": method_name,
                "error_type": type(exc).__name__,
                "reason": str(exc),
                "validator_rejected": validator_rejected,
            },
        )

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
            self._emit(
                "PROVIDER_CIRCUIT_OPENED",
                f"模型 {name} 连续失败，进入冷却期",
                level="WARNING",
                provider=name,
                details={
                    "consecutive_failures": state.consecutive_failures,
                    "cooldown_seconds": self.harness_config.cooldown_seconds,
                },
            )

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

    def _emit(self, event_type: str, message: str, **kwargs: Any) -> None:
        if self.events is not None:
            self.events.emit(
                stage=f"llm.{self.stage}",
                event_type=event_type,
                message=message,
                **kwargs,
            )
