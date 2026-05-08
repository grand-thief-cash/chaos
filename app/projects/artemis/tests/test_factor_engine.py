"""Unit tests for Factor Engine core modules."""

import math
import numpy as np
import pandas as pd
import pytest

from artemis.engines.factor_engine.ttm import (
    get_quarter, get_year, make_period, get_prev_quarter_period,
    _val, compute_ttm, compute_single_quarter,
)
from artemis.engines.factor_engine.point_in_time import (
    get_latest_available_reports, get_latest_period,
)
from artemis.engines.factor_engine.normalizer import FactorNormalizer
from artemis.engines.factor_engine.factors.base import safe_div, avg_balance
from artemis.engines.factor_engine.factors.growth import _growth_rate, _cagr
from artemis.engines.factor_engine.registry import FACTOR_REGISTRY


# ===================================================================
# TTM helpers
# ===================================================================

class TestGetQuarter:
    def test_normal_quarters(self):
        assert get_quarter("20250331") == 1
        assert get_quarter("20250630") == 2
        assert get_quarter("20250930") == 3
        assert get_quarter("20251231") == 4

    def test_invalid_month(self):
        assert get_quarter("20250131") == 0  # January is not a report month

    def test_empty_string(self):
        assert get_quarter("") == 0

    def test_short_string(self):
        assert get_quarter("2025") == 0

    def test_garbage_input(self):
        assert get_quarter("abcdefgh") == 0


class TestGetYear:
    def test_normal(self):
        assert get_year("20250930") == 2025

    def test_empty(self):
        assert get_year("") == 0

    def test_garbage(self):
        assert get_year("abcd") == 0


class TestMakePeriod:
    def test_all_quarters(self):
        assert make_period(2025, 1) == "20250331"
        assert make_period(2025, 2) == "20250630"
        assert make_period(2025, 3) == "20250930"
        assert make_period(2025, 4) == "20251231"


class TestGetPrevQuarterPeriod:
    def test_q1_goes_to_prev_year_q4(self):
        assert get_prev_quarter_period(2025, 1) == "20241231"

    def test_q3_goes_to_q2(self):
        assert get_prev_quarter_period(2025, 3) == "20250630"


# ===================================================================
# _val
# ===================================================================

class TestVal:
    def test_normal(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [100.0]})
        assert _val(df, "20250930", "REV") == 100.0

    def test_int_period_column(self):
        """Bug fix: reporting_period stored as int should still match str period."""
        df = pd.DataFrame({"reporting_period": [20250930], "REV": [200.0]})
        assert _val(df, "20250930", "REV") == 200.0

    def test_missing_field(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [100.0]})
        assert _val(df, "20250930", "NO_SUCH_FIELD") is None

    def test_empty_period(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [100.0]})
        assert _val(df, "", "REV") is None

    def test_none_df(self):
        assert _val(None, "20250930", "REV") is None

    def test_empty_df(self):
        assert _val(pd.DataFrame(), "20250930", "REV") is None

    def test_nan_value(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [float("nan")]})
        assert _val(df, "20250930", "REV") is None

    def test_period_not_found(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [100.0]})
        assert _val(df, "20241231", "REV") is None


# ===================================================================
# TTM computation
# ===================================================================

class TestComputeTTM:
    @pytest.fixture
    def income_df(self):
        return pd.DataFrame({
            "reporting_period": [
                "20240331", "20240630", "20240930", "20241231",
                "20250331", "20250630", "20250930",
            ],
            "OPERA_REV": [100, 220, 350, 500, 120, 260, 400],
        })

    def test_q3_ttm(self, income_df):
        # TTM = 400 (Q3_2025_cum) + 500 (FY2024) - 350 (Q3_2024_cum) = 550
        assert compute_ttm(income_df, "OPERA_REV", "20250930") == 550.0

    def test_q4_annual(self, income_df):
        # Q4 = annual value directly
        assert compute_ttm(income_df, "OPERA_REV", "20241231") == 500.0

    def test_q1_ttm(self, income_df):
        # TTM = 120 (Q1_2025) + 500 (FY2024) - 100 (Q1_2024) = 520
        assert compute_ttm(income_df, "OPERA_REV", "20250331") == 520.0

    def test_missing_prior_year(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "REV": [400]})
        assert compute_ttm(df, "REV", "20250930") is None

    def test_invalid_period(self, income_df):
        assert compute_ttm(income_df, "OPERA_REV", "") is None
        assert compute_ttm(income_df, "OPERA_REV", "20250131") is None


class TestComputeSingleQuarter:
    @pytest.fixture
    def income_df(self):
        return pd.DataFrame({
            "reporting_period": [
                "20250331", "20250630", "20250930",
            ],
            "REV": [100, 220, 400],
        })

    def test_q1_is_cumulative(self, income_df):
        assert compute_single_quarter(income_df, "REV", "20250331") == 100.0

    def test_q2_delta(self, income_df):
        assert compute_single_quarter(income_df, "REV", "20250630") == 120.0

    def test_q3_delta(self, income_df):
        assert compute_single_quarter(income_df, "REV", "20250930") == 180.0

    def test_empty_period(self, income_df):
        assert compute_single_quarter(income_df, "REV", "") is None


# ===================================================================
# safe_div
# ===================================================================

class TestSafeDiv:
    def test_normal(self):
        assert safe_div(10.0, 2.0) == 5.0

    def test_zero_denominator(self):
        assert safe_div(10.0, 0.0) is None

    def test_int_zero_denominator(self):
        assert safe_div(10.0, 0) is None

    def test_none_numerator(self):
        assert safe_div(None, 2.0) is None

    def test_none_denominator(self):
        assert safe_div(10.0, None) is None

    def test_nan_numerator(self):
        assert safe_div(float("nan"), 2.0) is None

    def test_nan_denominator(self):
        assert safe_div(10.0, float("nan")) is None

    def test_tiny_denominator(self):
        assert safe_div(10.0, 1e-15) is None


# ===================================================================
# Growth helpers
# ===================================================================

class TestGrowthRate:
    def test_normal_positive(self):
        assert _growth_rate(120, 100) == pytest.approx(0.2)

    def test_negative_base_loss_to_profit(self):
        # -50 → 80: (80 - (-50)) / abs(-50) = 130/50 = 2.6
        assert _growth_rate(80, -50) == pytest.approx(2.6)

    def test_zero_base(self):
        assert _growth_rate(100, 0.0) is None

    def test_both_none(self):
        assert _growth_rate(None, None) is None


class TestCAGR:
    def test_normal(self):
        # (200/100)^(1/3) - 1 ≈ 0.2599
        assert _cagr(200, 100, 3) == pytest.approx(0.259921, rel=1e-3)

    def test_negative_base(self):
        assert _cagr(200, -100, 3) is None

    def test_negative_current(self):
        assert _cagr(-200, 100, 3) is None


# ===================================================================
# Normalizer
# ===================================================================

class TestNormalizerMAD:
    def test_outlier_clipped(self):
        s = pd.Series([10, 12, 11, 13, 100, 9, 14])
        result = FactorNormalizer.winsorize_mad(s)
        assert result.max() < 100  # outlier should be clipped

    def test_all_same_values(self):
        s = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = FactorNormalizer.winsorize_mad(s)
        assert (result == 5.0).all()  # MAD=0, no clipping

    def test_too_few_values(self):
        s = pd.Series([1.0, 2.0])
        result = FactorNormalizer.winsorize_mad(s)
        pd.testing.assert_series_equal(result, s)


class TestNormalizerZScore:
    def test_basic_zscore(self):
        norm = FactorNormalizer()
        df = pd.DataFrame(
            {"roe": [0.3, 0.2, 0.1, 0.25, 0.15, 0.35, 0.22, 0.18, 0.28, 0.12, 0.5]},
            index=[f"S{i}" for i in range(11)],
        )
        ind_map = {f"S{i}": "A" for i in range(11)}
        result = norm.zscore_by_industry(df, ind_map)
        # Z-scores should have mean ≈ 0
        assert abs(result["roe"].mean()) < 0.01

    def test_unknown_industry_not_dropped(self):
        """Bug fix: symbols not in industry_map should not be silently dropped."""
        norm = FactorNormalizer()
        df = pd.DataFrame(
            {"factor": list(range(15))},
            index=[f"S{i}" for i in range(15)],
        )
        # Only map first 12 symbols, leave S12-S14 unmapped
        ind_map = {f"S{i}": "A" for i in range(12)}
        result = norm.zscore_by_industry(df, ind_map)
        # All 15 symbols should still be in the result
        assert len(result) == 15

    def test_industry_stats_stored(self):
        norm = FactorNormalizer()
        df = pd.DataFrame(
            {"roe": list(range(15))},
            index=[f"S{i}" for i in range(15)],
        )
        ind_map = {f"S{i}": "X" for i in range(15)}
        norm.zscore_by_industry(df, ind_map)
        stats = norm.get_industry_stats()
        assert "roe" in stats
        assert "X" in stats["roe"]
        assert stats["roe"]["X"]["n"] == 15


class TestNormalizerIncremental:
    def test_basic(self):
        stored = {"roe": {"A": {"mean": 0.2, "std": 0.1, "n": 50}}}
        result = FactorNormalizer.zscore_incremental({"roe": 0.3}, "A", stored)
        assert result["roe"] == pytest.approx(1.0)  # (0.3 - 0.2) / 0.1

    def test_std_zero(self):
        stored = {"roe": {"A": {"mean": 0.2, "std": 0.0, "n": 50}}}
        result = FactorNormalizer.zscore_incremental({"roe": 0.3}, "A", stored)
        assert result["roe"] == 0.0

    def test_unknown_industry(self):
        stored = {"roe": {"A": {"mean": 0.2, "std": 0.1, "n": 50}}}
        result = FactorNormalizer.zscore_incremental({"roe": 0.3}, "B", stored)
        assert result["roe"] == 0.3  # raw value returned


# ===================================================================
# Point-in-Time
# ===================================================================

class TestPIT:
    def test_future_data_excluded(self):
        df = pd.DataFrame({
            "reporting_period": ["20250331", "20250630"],
            "ann_date": ["20250420", "20250830"],
            "REV": [100, 200],
        })
        result = get_latest_available_reports(df, "20250501")
        assert len(result) == 1
        assert result.iloc[0]["reporting_period"] == "20250331"

    def test_revision_dedup(self):
        """Same reporting_period published twice → keep latest ann_date."""
        df = pd.DataFrame({
            "reporting_period": ["20250331", "20250331"],
            "ann_date": ["20250420", "20250425"],
            "REV": [100, 110],
        })
        result = get_latest_available_reports(df, "20250430")
        assert len(result) == 1
        assert result.iloc[0]["REV"] == 110  # latest revision

    def test_empty_input(self):
        result = get_latest_available_reports(pd.DataFrame(), "20250101")
        assert result.empty

    def test_get_latest_period(self):
        df = pd.DataFrame({
            "reporting_period": ["20250930", "20250630"],
            "ann_date": ["20251020", "20250820"],
        })
        pit = get_latest_available_reports(df, "20251101")
        assert get_latest_period(pit) == "20250930"


# ===================================================================
# Factor registration
# ===================================================================

class TestFactorRegistry:
    def test_all_39_registered(self):
        assert len(FACTOR_REGISTRY) == 39

    def test_categories_covered(self):
        cats = {m.category.value for m in FACTOR_REGISTRY.values()}
        assert cats == {
            "profitability", "growth", "quality", "solvency",
            "valuation", "efficiency", "per_share",
        }

    def test_no_duplicate_names(self):
        names = list(FACTOR_REGISTRY.keys())
        assert len(names) == len(set(names))


# ===================================================================
# avg_balance
# ===================================================================

class TestAvgBalance:
    def test_normal(self):
        df = pd.DataFrame({
            "reporting_period": ["20250630", "20250930"],
            "TOTAL_ASSETS": [1000, 1200],
        })
        result = avg_balance(df, "TOTAL_ASSETS", "20250930")
        assert result == 1100.0

    def test_single_period_fallback(self):
        df = pd.DataFrame({
            "reporting_period": ["20250930"],
            "TOTAL_ASSETS": [1200],
        })
        result = avg_balance(df, "TOTAL_ASSETS", "20250930")
        assert result == 1200.0  # fallback to current only

    def test_empty_period(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "TOTAL_ASSETS": [1200]})
        result = avg_balance(df, "TOTAL_ASSETS", "")
        assert result is None

