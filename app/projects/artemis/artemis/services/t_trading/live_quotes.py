from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class QuoteBookLevel:
    price: float
    volume: float

    def validate(self) -> None:
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("quote book price must be a positive finite number")
        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError(
                "quote book volume must be a non-negative finite number"
            )


@dataclass(frozen=True)
class QuotePoint:
    """One observed real-time quote; raw points are intentionally not persisted."""

    observed_at: datetime
    price: float
    cumulative_volume: float | None = None
    source_time: datetime | None = None
    source: str = ""
    symbol: str = ""
    name: str = ""
    cumulative_amount: float | None = None
    open: float | None = None
    previous_close: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    bids: tuple[QuoteBookLevel, ...] = ()
    asks: tuple[QuoteBookLevel, ...] = ()
    status: str = ""

    @property
    def event_time(self) -> datetime:
        return self.source_time or self.observed_at

    def validate(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("quote observed_at must be timezone-aware")
        if self.source_time is not None and self.source_time.tzinfo is None:
            raise ValueError("quote source_time must be timezone-aware")
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("quote price must be a positive finite number")
        if self.cumulative_volume is not None and (
            not isfinite(self.cumulative_volume)
            or self.cumulative_volume < 0
        ):
            raise ValueError(
                "quote cumulative_volume must be a non-negative finite number"
            )
        if self.cumulative_amount is not None and (
            not isfinite(self.cumulative_amount)
            or self.cumulative_amount < 0
        ):
            raise ValueError(
                "quote cumulative_amount must be a non-negative finite number"
            )
        for field_name in (
            "open",
            "previous_close",
            "day_high",
            "day_low",
        ):
            value = getattr(self, field_name)
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(
                    f"quote {field_name} must be a positive finite number"
                )
        for level in (*self.bids, *self.asks):
            level.validate()


@dataclass
class _HorizonState:
    horizon_seconds: int
    deadline: datetime
    quote_count: int = 0
    last_price: float | None = None
    mfe: float = 0.0
    mae: float = 0.0
    time_to_mfe_seconds: float | None = None
    time_to_mae_seconds: float | None = None
    first_touch: str = "no_touch"
    first_touch_seconds: float | None = None


@dataclass
class _TrackedSignal:
    signal_id: str
    side: str
    decision_time: datetime
    decision_price: float
    strategy: str
    horizons: dict[int, _HorizonState] = field(default_factory=dict)


class OnlineSignalOutcomeTracker:
    """Track compact post-signal outcomes directly from quotes without raw storage."""

    def __init__(
        self,
        *,
        horizons_seconds: list[int],
        target_return: float,
        stop_return: float,
    ):
        if not horizons_seconds or any(value <= 0 for value in horizons_seconds):
            raise ValueError("horizons_seconds must contain positive values")
        if len(set(horizons_seconds)) != len(horizons_seconds):
            raise ValueError("horizons_seconds must not contain duplicates")
        if target_return <= 0 or stop_return <= 0:
            raise ValueError("target_return and stop_return must be positive")
        self.horizons_seconds = sorted(horizons_seconds)
        self.target_return = target_return
        self.stop_return = stop_return
        self._signals: dict[str, _TrackedSignal] = {}
        self._last_event_time: datetime | None = None

    def register(
        self,
        *,
        signal_id: str,
        side: str,
        decision_time: datetime,
        decision_price: float,
        strategy: str,
    ) -> None:
        if signal_id in self._signals:
            raise ValueError(f"duplicate signal_id: {signal_id}")
        if side not in {"BUY", "SELL"}:
            raise ValueError("signal side must be BUY or SELL")
        if decision_time.tzinfo is None:
            raise ValueError("signal decision_time must be timezone-aware")
        if not isfinite(decision_price) or decision_price <= 0:
            raise ValueError("signal decision_price must be positive and finite")
        self._signals[signal_id] = _TrackedSignal(
            signal_id=signal_id,
            side=side,
            decision_time=decision_time,
            decision_price=decision_price,
            strategy=strategy,
            horizons={
                horizon: _HorizonState(
                    horizon_seconds=horizon,
                    deadline=decision_time + timedelta(seconds=horizon),
                )
                for horizon in self.horizons_seconds
            },
        )

    def _observe(
        self,
        signal: _TrackedSignal,
        state: _HorizonState,
        point: QuotePoint,
    ) -> None:
        elapsed = (point.event_time - signal.decision_time).total_seconds()
        directional_return = (
            point.price / signal.decision_price - 1
            if signal.side == "BUY"
            else 1 - point.price / signal.decision_price
        )
        favorable = max(directional_return, 0.0)
        adverse = max(-directional_return, 0.0)
        state.quote_count += 1
        state.last_price = point.price
        if state.time_to_mfe_seconds is None or favorable > state.mfe:
            state.mfe = favorable
            state.time_to_mfe_seconds = elapsed
        if state.time_to_mae_seconds is None or adverse > state.mae:
            state.mae = adverse
            state.time_to_mae_seconds = elapsed
        if state.first_touch == "no_touch":
            if directional_return >= self.target_return:
                state.first_touch = "target_first"
                state.first_touch_seconds = elapsed
            elif directional_return <= -self.stop_return:
                state.first_touch = "stop_first"
                state.first_touch_seconds = elapsed

    @staticmethod
    def _finish(
        signal: _TrackedSignal, state: _HorizonState
    ) -> dict[str, Any]:
        base = {
            "signal_id": signal.signal_id,
            "strategy": signal.strategy,
            "side": signal.side,
            "decision_time": signal.decision_time.isoformat(),
            "decision_price": signal.decision_price,
            "horizon_seconds": state.horizon_seconds,
            "evaluation_kind": "online_quote_event_study_v1",
        }
        if state.quote_count == 0 or state.last_price is None:
            return {
                **base,
                "evaluable": False,
                "reason": "no_post_signal_quote_before_deadline",
            }
        directional_return = (
            state.last_price / signal.decision_price - 1
            if signal.side == "BUY"
            else 1 - state.last_price / signal.decision_price
        )
        return {
            **base,
            "evaluable": True,
            "quote_count": state.quote_count,
            "last_observed_price": state.last_price,
            "directional_return": round(directional_return, 6),
            "direction_correct": directional_return > 0,
            "mfe": round(state.mfe, 6),
            "mae": round(state.mae, 6),
            "time_to_mfe_seconds": state.time_to_mfe_seconds,
            "time_to_mae_seconds": state.time_to_mae_seconds,
            "first_touch": state.first_touch,
            "first_touch_seconds": state.first_touch_seconds,
        }

    def update(self, point: QuotePoint) -> list[dict[str, Any]]:
        point.validate()
        if (
            self._last_event_time is not None
            and point.event_time <= self._last_event_time
        ):
            raise ValueError("quote event_time must be strictly increasing")
        self._last_event_time = point.event_time
        completed: list[dict[str, Any]] = []
        completed_signals: list[str] = []
        for signal_id, signal in self._signals.items():
            completed_horizons: list[int] = []
            for horizon, state in signal.horizons.items():
                if point.event_time <= signal.decision_time:
                    continue
                if point.event_time <= state.deadline:
                    self._observe(signal, state, point)
                    if point.event_time < state.deadline:
                        continue
                completed.append(self._finish(signal, state))
                completed_horizons.append(horizon)
            for horizon in completed_horizons:
                signal.horizons.pop(horizon)
            if not signal.horizons:
                completed_signals.append(signal_id)
        for signal_id in completed_signals:
            self._signals.pop(signal_id)
        return completed

    @property
    def active_signal_count(self) -> int:
        return len(self._signals)
