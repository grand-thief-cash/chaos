from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ValuationMethod = Literal["forward_pe", "pb_roe", "ev_ebitda", "dcf"]


class ValuationAnalyzeRequest(BaseModel):
    security_id: int = Field(gt=0)
    valuation_date: date | None = None
    horizon_years: int = Field(default=1, ge=1, le=3)
    history_years: int = Field(default=5, ge=2, le=10)
    methods: list[ValuationMethod] = Field(
        default_factory=lambda: ["forward_pe", "pb_roe", "ev_ebitda", "dcf"],
    )
    financial_source: str = "amazing_data"
    statement_code: str = "1"

    @model_validator(mode="after")
    def validate_methods(self):
        if not self.methods:
            raise ValueError("at least one valuation method is required")
        self.methods = list(dict.fromkeys(self.methods))
        return self


class ValuationHistoryRequest(BaseModel):
    security_id: int = Field(gt=0)
    start_date: date
    end_date: date
    interval: Literal["month_end", "quarter_end"] = "month_end"
    history_years: int = Field(default=5, ge=2, le=10)
    financial_source: str = "amazing_data"
    statement_code: str = "1"

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if (self.end_date - self.start_date).days > 3655:
            raise ValueError("history replay range must be <= 10 years")
        return self
