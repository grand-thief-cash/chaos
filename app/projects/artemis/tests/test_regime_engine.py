"""Unit tests for Market Regime Engine."""

import math
import pytest

from artemis.engines.regime_engine.models import (
    RegimeFeatures, RegimeState, StrategyAllocation, derive_labels,
)
from artemis.engines.regime_engine.estimator import (
    RegimeStateEstimator, _clip, _sigmoid_clip,
)
from artemis.engines.regime_engine.allocator import StrategyAllocator, FactorWeightAdjuster
from artemis.engines.regime_engine.config import RegimeConfig


# ===================================================================
# Utility functions
# ===================================================================

class TestClip:
    def test_within_range(self):
        assert _clip(0.5) == 0.5

    def test_below_range(self):
        assert _clip(-0.3) == 0.0

    def test_above_range(self):
        assert _clip(1.5) == 1.0

    def test_custom_range(self):
        assert _clip(0.5, -1.0, 1.0) == 0.5
        assert _clip(-2.0, -1.0, 1.0) == -1.0


class TestSigmoidClip:
    def test_zero(self):
        assert _sigmoid_clip(0) == 0.0

    def test_positive(self):
        assert 0.0 < _sigmoid_clip(1.0) < 1.0

    def test_negative(self):
        assert -1.0 < _sigmoid_clip(-1.0) < 0.0

    def test_extreme_positive_no_overflow(self):
        result = _sigmoid_clip(10000)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_extreme_negative_no_overflow(self):
        result = _sigmoid_clip(-10000)
        assert result == pytest.approx(-1.0, abs=0.01)

    def test_symmetry(self):
        assert _sigmoid_clip(1.0) == pytest.approx(-_sigmoid_clip(-1.0))


# ===================================================================
# RegimeState and labels
# ===================================================================

class TestDeriveLabels:
    def test_bull_trend(self):
        state = RegimeState(trend_strength=0.8, volatility_stress=0.3)
        labels = derive_labels(state)
        assert labels["label_market"] == "BULL_TREND"

    def test_bear_trend(self):
        state = RegimeState(trend_strength=0.2, volatility_stress=0.3)
        labels = derive_labels(state)
        assert labels["label_market"] == "BEAR_TREND"

    def test_panic_overrides_trend(self):
        state = RegimeState(trend_strength=0.8, volatility_stress=0.9)
        labels = derive_labels(state)
        assert labels["label_market"] == "PANIC"  # vol > 0.8 overrides trend

    def test_sideways(self):
        state = RegimeState(trend_strength=0.5, volatility_stress=0.4)
        labels = derive_labels(state)
        assert labels["label_market"] == "SIDEWAYS"

    def test_vol_spike(self):
        state = RegimeState(volatility_stress=0.85, vol_acceleration=0.5)
        labels = derive_labels(state)
        assert labels["label_vol"] == "SPIKE"

    def test_vol_low(self):
        state = RegimeState(volatility_stress=0.1)
        labels = derive_labels(state)
        assert labels["label_vol"] == "LOW"


# ===================================================================
# RegimeStateEstimator
# ===================================================================

class TestRegimeStateEstimator:
    def test_first_estimate_no_smoothing(self):
        est = RegimeStateEstimator()
        f = RegimeFeatures(
            trade_date="20260501",
            hs300_distance_from_ma120=0.05,
            hs300_ma20_slope=0.002,
            breadth_above_ma20_pct=0.62,
            vol_ratio=1.1,
            turnover_ratio=1.2,
            style_small_vs_large=0.03,
            industry_concentration=0.1,
        )
        state = est.estimate(f)
        assert 0.0 <= state.trend_strength <= 1.0
        assert 0.0 <= state.volatility_stress <= 1.0
        assert state.breadth_momentum == 0.0  # no previous
        assert state.labels  # should have labels

    def test_second_estimate_has_smoothing(self):
        est = RegimeStateEstimator()
        f1 = RegimeFeatures(trade_date="20260501", breadth_above_ma20_pct=0.6)
        f2 = RegimeFeatures(trade_date="20260502", breadth_above_ma20_pct=0.7)

        s1 = est.estimate(f1)
        s2 = est.estimate(f2)

        # EMA smoothing means s2.market_breadth is NOT simply 0.7
        assert s2.market_breadth != 0.7
        # It should be between s1 and raw f2 value
        assert s1.market_breadth <= s2.market_breadth <= 0.7

    def test_breadth_momentum_computed(self):
        est = RegimeStateEstimator()
        f1 = RegimeFeatures(trade_date="20260501", breadth_above_ma20_pct=0.5)
        f2 = RegimeFeatures(trade_date="20260502", breadth_above_ma20_pct=0.7)

        est.estimate(f1)
        s2 = est.estimate(f2)
        assert s2.breadth_momentum > 0  # breadth improved

    def test_vol_stress_asymmetric_smoothing(self):
        """Vol stress: up = no smoothing (instant), down = smoothed."""
        config = RegimeConfig(smoothing_alpha=0.3)
        est = RegimeStateEstimator(config)

        # Low vol → high vol: should jump immediately
        f1 = RegimeFeatures(trade_date="d1", vol_ratio=0.8)
        f2 = RegimeFeatures(trade_date="d2", vol_ratio=1.8)

        s1 = est.estimate(f1)
        s2 = est.estimate(f2)
        raw_vol2 = _clip((1.8 - 0.7) / 1.3)
        assert s2.volatility_stress == pytest.approx(raw_vol2, abs=0.01)

    def test_reset(self):
        est = RegimeStateEstimator()
        est.estimate(RegimeFeatures(trade_date="d1"))
        est.reset()
        s = est.estimate(RegimeFeatures(trade_date="d2"))
        assert s.breadth_momentum == 0.0  # no previous after reset


# ===================================================================
# StrategyAllocator
# ===================================================================

class TestStrategyAllocator:
    def test_weights_sum_to_one(self):
        alloc = StrategyAllocator()
        state = RegimeState(
            trend_strength=0.7, risk_appetite=0.6,
            volatility_stress=0.3, market_breadth=0.6,
            liquidity=0.5, sector_concentration=0.2,
        )
        result = alloc.allocate(state)
        total = sum(result.weights.values())
        assert total == pytest.approx(1.0)

    def test_position_limit_high_vol(self):
        alloc = StrategyAllocator()
        state = RegimeState(volatility_stress=0.9, trend_strength=0.5)
        result = alloc.allocate(state)
        assert result.position_limit < 0.5  # should be very low

    def test_position_limit_calm_market(self):
        alloc = StrategyAllocator()
        state = RegimeState(
            volatility_stress=0.1, trend_strength=0.7,
            market_breadth=0.6, breadth_momentum=0.1,
        )
        result = alloc.allocate(state)
        assert result.position_limit > 0.7

    def test_holding_period_high_vol(self):
        alloc = StrategyAllocator()
        state = RegimeState(volatility_stress=0.8)
        result = alloc.allocate(state)
        assert result.suggested_holding_period == "short"


class TestFactorWeightAdjuster:
    def test_bull_favors_growth(self):
        state = RegimeState(trend_strength=0.8, risk_appetite=0.7, volatility_stress=0.2)
        adj = FactorWeightAdjuster.adjust(state)
        assert adj["growth_revenue_yoy"] > 1.0  # growth boosted in bull

    def test_bear_favors_value(self):
        state = RegimeState(trend_strength=0.2, risk_appetite=0.3, volatility_stress=0.6)
        adj = FactorWeightAdjuster.adjust(state)
        assert adj["valuation_pe_ttm"] > 1.0  # value boosted in bear
        assert adj["per_share_dps"] > 1.0  # dividend boosted


# ===================================================================
# RegimeState serialization
# ===================================================================

class TestRegimeStateSerialization:
    def test_to_state_vector(self):
        state = RegimeState(trend_strength=0.7, risk_appetite=0.6)
        vec = state.to_state_vector()
        assert vec["trend_strength"] == 0.7
        assert "trade_date" not in vec

    def test_to_dict(self):
        state = RegimeState(trade_date="20260508", trend_strength=0.7)
        state.labels = {"label_market": "BULL_TREND"}
        d = state.to_dict()
        assert d["trade_date"] == "20260508"
        assert d["trend_strength"] == 0.7
        assert d["label_market"] == "BULL_TREND"

