from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class TStrategyConfig(BaseModel):
    """Causal intraday T-trading signal parameters."""

    direction: Literal["buy_first", "sell_first"] = "buy_first"
    window: int = Field(default=20, ge=5, le=120)
    entry_z: float = Field(default=1.25, ge=0.0, le=5.0)
    exit_z: float = Field(default=1.0, ge=0.0, le=5.0)
    entry_rsi: float = Field(default=35.0, ge=0.0, le=100.0)
    exit_rsi: float = Field(default=65.0, ge=0.0, le=100.0)
    confirmation_bars: int = Field(default=3, ge=1, le=12)
    cooldown_bars: int = Field(default=2, ge=0, le=30)
    max_round_trips: int = Field(default=2, ge=1, le=10)


class TExecutionConfig(BaseModel):
    """A-share execution and cost assumptions used by the simulator."""

    quantity: int = Field(default=100, ge=100, multiple_of=100)
    commission_rate: float = Field(default=0.0003, ge=0.0, le=0.01)
    minimum_commission: float = Field(default=5.0, ge=0.0, le=100.0)
    stamp_duty_rate_on_sell: float = Field(default=0.0005, ge=0.0, le=0.01)
    transfer_fee_rate: float = Field(default=0.00001, ge=0.0, le=0.01)
    slippage_bps: float = Field(default=1.0, ge=0.0, le=100.0)


class TReplayRequest(BaseModel):
    security_id: int = Field(gt=0)
    trade_date: date
    period: Literal["min5"] = "min5"
    adjust: Literal["nf"] = "nf"
    source: Optional[str] = None
    persistence_mode: Literal["ephemeral"] = "ephemeral"
    strategy: TStrategyConfig = Field(default_factory=TStrategyConfig)
    execution: TExecutionConfig = Field(default_factory=TExecutionConfig)


class TBatchReplayRequest(BaseModel):
    security_ids: list[int] = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    period: Literal["min5"] = "min5"
    adjust: Literal["nf"] = "nf"
    source: Optional[str] = None
    persistence_mode: Literal["ephemeral"] = "ephemeral"
    strategy: TStrategyConfig = Field(default_factory=TStrategyConfig)
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
        return self
