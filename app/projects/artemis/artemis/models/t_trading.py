from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TStrategyConfig(BaseModel):
    """Causal intraday T-trading signal parameters."""

    strategy: Literal[
        "causal_mean_reversion_v1",
        "macd_volume_momentum_v1",
        "vwap_bollinger_reversion_v1",
        "opening_range_breakout_v1",
        "time_of_day_volume_momentum_v1",
        "market_residual_reversal_v1",
        "multi_timeframe_pullback_v1",
    ] = "causal_mean_reversion_v1"
    direction: Literal["buy_first", "sell_first", "independent"] = "buy_first"
    window: int = Field(default=20, ge=5, le=120)
    entry_z: float = Field(default=1.25, ge=0.0, le=5.0)
    exit_z: float = Field(default=1.0, ge=0.0, le=5.0)
    entry_rsi: float = Field(default=35.0, ge=0.0, le=100.0)
    exit_rsi: float = Field(default=65.0, ge=0.0, le=100.0)
    confirmation_bars: int = Field(default=3, ge=1, le=12)
    cooldown_bars: int = Field(default=5, ge=0, le=30)
    max_round_trips: int = Field(default=2, ge=1, le=10)
    ema_fast: int = Field(default=5, ge=2, le=60)
    ema_slow: int = Field(default=13, ge=3, le=120)
    macd_signal: int = Field(default=4, ge=2, le=30)
    min_volume_ratio: float = Field(default=0.8, ge=0.0, le=10.0)
    ema_deviation_atr: float = Field(default=0.35, ge=0.0, le=5.0)
    macd_turn_bars: int = Field(default=2, ge=1, le=6)
    volume_confirmation_window: int = Field(default=3, ge=1, le=20)
    bollinger_z: float = Field(default=1.5, ge=0.25, le=5.0)
    reversal_wick_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    max_trend_strength_atr: float = Field(default=0.8, ge=0.0, le=10.0)
    atr_window: int = Field(default=14, ge=3, le=120)
    opening_range_bars: int = Field(default=6, ge=2, le=24)
    breakout_atr_buffer: float = Field(default=0.1, ge=0.0, le=3.0)
    relative_volume_tod_threshold: float = Field(
        default=1.5, ge=0.1, le=20.0
    )
    min_time_of_day_history_days: int = Field(default=20, ge=5, le=120)
    market_beta_window: int = Field(default=20, ge=5, le=120)
    residual_z_threshold: float = Field(default=1.5, ge=0.25, le=5.0)
    higher_ema_fast: int = Field(default=5, ge=2, le=60)
    higher_ema_slow: int = Field(default=10, ge=3, le=120)
    daily_trend_window: int = Field(default=20, ge=5, le=120)
    pullback_tolerance_atr: float = Field(default=0.5, ge=0.0, le=5.0)
    @model_validator(mode="after")
    def validate_indicator_windows(self):
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be < ema_slow")
        if self.higher_ema_fast >= self.higher_ema_slow:
            raise ValueError("higher_ema_fast must be < higher_ema_slow")
        return self


class TExecutionConfig(BaseModel):
    """A-share execution and cost assumptions used by the simulator."""

    quantity: int = Field(default=100, ge=100, multiple_of=100)
    commission_rate: float = Field(default=0.0003, ge=0.0, le=0.01)
    minimum_commission: float = Field(default=5.0, ge=0.0, le=100.0)
    stamp_duty_rate_on_sell: float = Field(default=0.0005, ge=0.0, le=0.01)
    transfer_fee_rate: float = Field(default=0.00001, ge=0.0, le=0.01)
    slippage_bps: float = Field(default=1.0, ge=0.0, le=100.0)


class TSignalEvaluationConfig(BaseModel):
    """Forward event-study settings; never available to the signal engine."""

    horizons_bars: list[int] = Field(default_factory=lambda: [1, 3, 6, 12])
    primary_horizon_bars: int = Field(default=6, ge=1, le=48)
    target_return: float = Field(default=0.005, gt=0.0, le=0.2)
    stop_return: float = Field(default=0.003, gt=0.0, le=0.2)

    @field_validator("horizons_bars")
    @classmethod
    def validate_horizons(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("horizons_bars must not be empty")
        if len(value) > 8:
            raise ValueError("horizons_bars must contain at most 8 values")
        if any(horizon < 1 or horizon > 48 for horizon in value):
            raise ValueError("horizons_bars values must be between 1 and 48")
        if len(set(value)) != len(value):
            raise ValueError("horizons_bars must not contain duplicates")
        return sorted(value)

    @model_validator(mode="after")
    def validate_primary_horizon(self):
        if self.primary_horizon_bars not in self.horizons_bars:
            raise ValueError("primary_horizon_bars must be in horizons_bars")
        return self


class TReplayRequest(BaseModel):
    security_id: int = Field(gt=0)
    trade_date: date
    period: Literal["min1", "min5"] = "min1"
    adjust: Literal["nf"] = "nf"
    source: Optional[str] = None
    persistence_mode: Literal["ephemeral"] = "ephemeral"
    strategy: TStrategyConfig = Field(default_factory=TStrategyConfig)
    strategies: list[TStrategyConfig] | None = None
    benchmark_security_id: int | None = Field(default=None, gt=0)
    evaluation: TSignalEvaluationConfig = Field(
        default_factory=TSignalEvaluationConfig
    )
    include_execution_simulation: bool = False
    execution: TExecutionConfig = Field(default_factory=TExecutionConfig)

    @model_validator(mode="after")
    def validate_strategy_set(self):
        selected = self.strategies or [self.strategy]
        if not selected:
            raise ValueError("strategies must not be empty")
        if len(selected) > 8:
            raise ValueError("strategies must contain at most 8 entries")
        names = [item.strategy for item in selected]
        if len(set(names)) != len(names):
            raise ValueError("strategies must not contain duplicate strategy names")
        if (
            "market_residual_reversal_v1" in names
            and self.benchmark_security_id is None
        ):
            raise ValueError(
                "benchmark_security_id is required for market residual strategy"
            )
        if self.include_execution_simulation and len(selected) > 1:
            raise ValueError(
                "execution simulation supports only one strategy per request"
            )
        return self

    @property
    def effective_strategies(self) -> list[TStrategyConfig]:
        return self.strategies or [self.strategy]


class TBatchReplayRequest(BaseModel):
    security_ids: list[int] = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    period: Literal["min1", "min5"] = "min1"
    adjust: Literal["nf"] = "nf"
    source: Optional[str] = None
    persistence_mode: Literal["ephemeral"] = "ephemeral"
    strategy: TStrategyConfig = Field(default_factory=TStrategyConfig)
    strategies: list[TStrategyConfig] | None = None
    benchmark_security_id: int | None = Field(default=None, gt=0)
    evaluation: TSignalEvaluationConfig = Field(
        default_factory=TSignalEvaluationConfig
    )
    include_execution_simulation: bool = False
    execution: TExecutionConfig = Field(default_factory=TExecutionConfig)
    include_details: bool = False

    @model_validator(mode="after")
    def validate_scope(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        day_count = (self.end_date - self.start_date).days + 1
        if day_count > 366:
            raise ValueError("batch date range must not exceed 366 natural days")
        if day_count * len(self.security_ids) > 500:
            raise ValueError("batch scope exceeds 500 security-day combinations")
        if len(set(self.security_ids)) != len(self.security_ids):
            raise ValueError("security_ids must not contain duplicates")
        if any(security_id <= 0 for security_id in self.security_ids):
            raise ValueError("security_ids must contain only positive integers")
        selected = self.strategies or [self.strategy]
        names = [item.strategy for item in selected]
        if not selected or len(selected) > 8:
            raise ValueError("strategies must contain between 1 and 8 entries")
        if len(set(names)) != len(names):
            raise ValueError("strategies must not contain duplicate strategy names")
        if (
            "market_residual_reversal_v1" in names
            and self.benchmark_security_id is None
        ):
            raise ValueError(
                "benchmark_security_id is required for market residual strategy"
            )
        if self.include_execution_simulation and len(selected) > 1:
            raise ValueError(
                "execution simulation supports only one strategy per request"
            )
        return self

    @property
    def effective_strategies(self) -> list[TStrategyConfig]:
        return self.strategies or [self.strategy]
