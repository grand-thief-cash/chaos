"""Unit tests for Factor Engine core modules."""

from typing import Dict, List, Optional

import pandas as pd
import pytest

from artemis.consts.task_params import ADJUST_FORWARD, ADJUST_NONE
from artemis.engines.factor_engine.ttm import (
    get_quarter, get_year, make_period, get_prev_quarter_period,
    _val, compute_ttm, compute_single_quarter, normalize_period,
)
from artemis.engines.factor_engine.point_in_time import (
    get_latest_available_reports, get_latest_period,
)
from artemis.engines.factor_engine.pipeline import FactorPipeline
from artemis.engines.factor_engine.normalizer import FactorNormalizer
from artemis.engines.factor_engine.factors.base import BaseFactor, safe_div, avg_balance
from artemis.engines.factor_engine.factors.growth import _growth_rate, _cagr
from artemis.engines.factor_engine.factors.per_share import PerShareFactors
from artemis.engines.factor_engine.factors.valuation import ValuationFactors
from artemis.engines.factor_engine.models import FactorCategory, FactorMeta
from artemis.engines.factor_engine.registry import FACTOR_REGISTRY, get_factor_definition, get_factor_market_adjust_policy, list_factors
from artemis.engines.factor_engine.storage.factor_store import FactorStore


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

    def test_iso_date_input(self):
        assert get_quarter("2025-09-30") == 3


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

    def test_reads_from_index_when_column_missing(self):
        df = pd.DataFrame({"REV": [100.0]}, index=pd.Index(["20250930"], name="reporting_period"))
        assert _val(df, "2025-09-30", "REV") == 100.0

    def test_uses_canonical_phoenixa_field_names_only(self):
        df = pd.DataFrame({"reporting_period": ["20250930"], "INCOME_TAX": [12.0]})
        assert _val(df, "20250930", "INCOME_TAX") == 12.0
        assert _val(df, "20250930", "INC_TAX") is None


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


class TestNormalizePeriod:
    def test_compact_and_iso(self):
        assert normalize_period("2025-09-30") == "20250930"
        assert normalize_period("20250930") == "20250930"


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
        assert result.tolist() == [5.0, 5.0, 5.0, 5.0]  # MAD=0, no clipping

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

    def test_catalog_seeded_management_fields_are_exposed(self):
        meta_by_name = {item["name"]: item for item in list_factors()}

        div_meta = meta_by_name["dividend_yield"]
        assert div_meta["catalog_seeded"] is True
        assert div_meta["catalog_version"] == "2026-05-14"
        assert "dividend" in div_meta["management_tags"]
        assert div_meta["financial_policy"]["mode"] == "standard"
        assert div_meta["phoenix_queries"][0]["endpoint"] == "/api/v2/corporate-action/{source}/{action_type}"

    def test_all_registered_factors_are_seeded_in_catalog(self):
        seeded = [item for item in list_factors() if item.get("catalog_seeded")]
        assert len(seeded) == len(FACTOR_REGISTRY) == 39

        meta_by_name = {item["name"]: item for item in seeded}
        assert meta_by_name["revenue_cagr_3y"]["availability"]["expected"] == "conditional"
        assert "income history >= 12 quarters" in meta_by_name["revenue_cagr_3y"]["availability"]["requirements"]

    def test_factor_definition_exposes_required_fields_and_provenance(self):
        factor_def = get_factor_definition("dividend_yield")

        assert factor_def is not None
        assert "corporate_action.dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH" in factor_def["required_fields"]
        assert factor_def["provenance"]["phoenix_queries"][0]["endpoint"] == "/api/v2/corporate-action/{source}/{action_type}"
        assert "bars" in factor_def["required_data_sources"]

    def test_factor_definition_exposes_market_adjust_policy(self):
        factor_def = get_factor_definition("pe_ttm")

        assert factor_def is not None
        assert factor_def["market_adjust_policy"]["adjust"] == ADJUST_NONE

    def test_factor_catalog_market_adjust_policy_is_factor_specific(self):
        pe_policy = get_factor_market_adjust_policy("pe_ttm")
        roe_policy = get_factor_market_adjust_policy("roe")

        assert pe_policy["adjust"] == ADJUST_NONE
        assert roe_policy == {}

    def test_financial_variant_pending_policy_is_exposed(self):
        meta_by_name = {item["name"]: item for item in list_factors()}
        roic_meta = meta_by_name["roic"]

        assert roic_meta["financial_policy"]["mode"] == "financial_variant_pending"
        assert roic_meta["financial_policy"]["action"] == "exclude_for_banks_insurers_brokers"


class TestFinancialClassification:
    def test_prefers_comp_type_code_for_financial_company_kind(self):
        financial_data = {
            "balance_sheet": pd.DataFrame({"reporting_period": ["20241231"], "comp_type_code": [2]}),
        }

        assert FactorPipeline._financial_company_kind(financial_data, None) == "bank"

    def test_uses_phoenixa_derived_flags_when_comp_type_missing(self):
        financial_data = {"balance_sheet": pd.DataFrame({"reporting_period": ["20241231"]})}

        assert FactorPipeline._financial_company_kind(
            financial_data,
            {"derived_flags": {"financial_sector": True}},
        ) == "financial"

    def test_no_longer_uses_industry_code_prefix_fallback(self):
        financial_data = {"balance_sheet": pd.DataFrame({"reporting_period": ["20241231"]})}

        assert FactorPipeline._financial_company_kind(financial_data, {"industry_code": "801010"}) is None


class TestSnapshotRuntimeMetadata:
    def test_build_snapshot_meta_contains_freshness_and_missing_reasons(self):
        financial_data = {
            "balance_sheet": pd.DataFrame({
                "reporting_period": ["20241231", "20240930"],
                "ann_date": ["20250321", "20241025"],
                "comp_type_code": [2, 2],
            }),
            "income": pd.DataFrame({
                "reporting_period": ["20241231", "20240930"],
                "ann_date": ["20250321", "20241025"],
            }),
        }

        meta = FactorPipeline._build_snapshot_meta(
            factor_values={"current_ratio": None, "pe_ttm": None, "revenue_cagr_3y": None, "debt_ratio": 0.4},
            financial_data=financial_data,
            market_data=None,
            current_period="20241231",
            as_of_date="20250501",
            industry_code="801010",
            industry_context={"derived_flags": {"financial_sector": True}},
        )

        assert meta["company_kind"] == "bank"
        assert meta["industry_flags"]["financial_sector"] is True
        assert meta["reporting_period"] == "20241231"
        assert meta["latest_ann_date"] == "20250321"
        assert meta["freshness"]["freshness_label"] in {"fresh", "acceptable"}
        assert meta["missing_reasons"]["current_ratio"] == "excluded_for_bank"
        assert meta["missing_reasons"]["pe_ttm"] == "missing_market_data_frame"
        assert meta["missing_reasons"]["revenue_cagr_3y"] == "missing_required_field:income.OPERA_REV"

    def test_missing_reason_can_point_to_specific_required_field(self):
        financial_data = {
            "balance_sheet": pd.DataFrame({
                "reporting_period": ["20241231", "20240930"],
                "ann_date": ["20250321", "20241025"],
                "comp_type_code": [1, 1],
                "TOT_SHARE": [1000, 1000],
            }),
            "income": pd.DataFrame({
                "reporting_period": ["20241231", "20240930", "20240331", "20231231"],
                "ann_date": ["20250321", "20241025", "20240420", "20240320"],
                "NET_PRO_EXCL_MIN_INT_INC": [1, 1, 1, 1],
            }),
        }
        market_data = pd.DataFrame({"close": [10.0]}, index=pd.Index(["20250501"], name="trade_date"))

        meta = FactorPipeline._build_snapshot_meta(
            factor_values={"dividend_yield": None},
            financial_data=financial_data,
            market_data=market_data,
            current_period="20241231",
            as_of_date="20250501",
            industry_code="801150",
            industry_context={"derived_flags": {"financial_sector": False}},
        )

        assert meta["missing_reasons"]["dividend_yield"] == "missing_market_enrichment:dps"

    def test_factor_store_persists_snapshot_meta(self):
        store = FactorStore()
        raw = pd.DataFrame({"roe": [0.1]}, index=["000001"])
        norm = pd.DataFrame({"roe": [1.0]}, index=["000001"])
        store.save_factor_snapshot(
            "20250501",
            "zh_a",
            raw,
            norm,
            snapshot_meta={"000001": {"version": "v1.0", "reporting_period": "20241231"}},
        )

        snap = store.get_factor_snapshot("000001", "20250501", "zh_a")
        assert snap is not None
        assert snap["meta"]["reporting_period"] == "20241231"


class _AdjustAwareFactor(BaseFactor):
    def __init__(self, category: FactorCategory, name: str):
        self._meta = FactorMeta(name, name, category, "test", (), requires_market_data=True)

    def factor_metas(self) -> list:
        return [self._meta]

    def compute(
        self,
        symbol: str,
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None,
        current_period: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        adjust = None
        if market_data is not None and not market_data.empty and "adjust" in market_data.columns:
            adjust = market_data["adjust"].iloc[-1]
        return {self._meta.name: 1.0 if adjust else None}


class _MixedAdjustAwareFactor(BaseFactor):
    def __init__(self):
        self._metas = [
            FactorMeta("valuation_probe_a", "valuation_probe_a", FactorCategory.VALUATION, "test", (), requires_market_data=True),
            FactorMeta("valuation_probe_b", "valuation_probe_b", FactorCategory.VALUATION, "test", (), requires_market_data=True),
        ]

    def factor_metas(self) -> list:
        return list(self._metas)

    def compute(
        self,
        symbol: str,
        financial_data: Dict[str, pd.DataFrame],
        market_data: Optional[pd.DataFrame] = None,
        current_period: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        adjust = None
        if market_data is not None and not market_data.empty and "adjust" in market_data.columns:
            adjust = market_data["adjust"].iloc[-1]
        return {meta.name: 1.0 if adjust else None for meta in self._metas}


class _AdjustAwareProvider:
    def __init__(self):
        self.adjust_requests = []

    def get_active_symbols(self, market: str, as_of_date: str):
        return ["000001"]

    def get_industry_map(self, taxonomy: str, market: str, use_batch: bool = True, symbols: Optional[List[str]] = None):
        return {"000001": "801010"}

    def get_industry_context(self, symbol: str, taxonomy: str, market: str):
        return {"derived_flags": {"financial_sector": False}}

    def get_financial_data(self, symbol: str, as_of_date: str):
        return {"balance_sheet": pd.DataFrame({"reporting_period": ["20241231"], "ann_date": ["20250321"]})}

    def get_market_data(self, symbol: str, as_of_date: str, adjust: Optional[str] = None):
        self.adjust_requests.append(adjust)
        return pd.DataFrame({"close": [10.0], "adjust": [adjust or ADJUST_NONE]}, index=pd.Index(["20250501"], name="trade_date"))

    def get_current_period(self, symbol: str, as_of_date: str):
        return "20241231"


class TestMarketAdjustPolicy:
    def test_pipeline_uses_factor_catalog_market_adjust_policy(self, monkeypatch):
        provider = _AdjustAwareProvider()
        pipeline = FactorPipeline(provider, FactorStore())
        pipeline.factor_groups = [_AdjustAwareFactor(FactorCategory.VALUATION, "valuation_probe")]
        monkeypatch.setattr(
            "artemis.engines.factor_engine.pipeline.get_factor_market_adjust_policy",
            lambda name: {"adjust": ADJUST_FORWARD},
        )

        pipeline.run_full("20250501", "zh_a")

        assert provider.adjust_requests == [ADJUST_FORWARD]

    def test_pipeline_errors_when_factor_lacks_market_adjust_policy(self, monkeypatch):
        provider = _AdjustAwareProvider()
        pipeline = FactorPipeline(provider, FactorStore())
        pipeline.factor_groups = [_AdjustAwareFactor(FactorCategory.VALUATION, "valuation_probe")]
        monkeypatch.setattr(
            "artemis.engines.factor_engine.pipeline.get_factor_market_adjust_policy",
            lambda name: {},
        )

        with pytest.raises(ValueError, match="market_adjust_policy"):
            pipeline.run_full("20250501", "zh_a")

    def test_pipeline_errors_when_group_contains_mixed_market_adjust_policies(self, monkeypatch):
        provider = _AdjustAwareProvider()
        pipeline = FactorPipeline(provider, FactorStore())
        pipeline.factor_groups = [_MixedAdjustAwareFactor()]
        policy_map = {
            "valuation_probe_a": {"adjust": ADJUST_NONE},
            "valuation_probe_b": {"adjust": ADJUST_FORWARD},
        }
        monkeypatch.setattr(
            "artemis.engines.factor_engine.pipeline.get_factor_market_adjust_policy",
            lambda name: policy_map[name],
        )

        with pytest.raises(ValueError, match="mixed market_adjust_policy"):
            pipeline.run_full("20250501", "zh_a")



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


# ===================================================================
# Factor formulas using corrected PhoenixA sourcing
# ===================================================================

class TestValuationAndPerShareFactors:
    @pytest.fixture
    def financial_data(self):
        return {
            "income": pd.DataFrame({
                "reporting_period": ["20241231", "20250331", "20240331"],
                "NET_PRO_EXCL_MIN_INT_INC": [1000.0, 300.0, 200.0],
                "OPERA_REV": [5000.0, 1300.0, 1000.0],
                "OPERA_PROFIT": [1200.0, 320.0, 250.0],
                "EBITDA": [1500.0, 380.0, 300.0],
            }),
            "balance_sheet": pd.DataFrame({
                "reporting_period": ["20241231", "20250331"],
                "TOT_SHARE_EQUITY_EXCL_MIN_INT": [4000.0, 4200.0],
                "TOT_SHARE": [1000.0, 1000.0],
                "ST_BORROWING": [200.0, 220.0],
                "LT_LOAN": [300.0, 330.0],
                "BONDS_PAYABLE": [100.0, 100.0],
                "CURRENCY_CAP": [150.0, 120.0],
            }),
            "cashflow": pd.DataFrame({
                "reporting_period": ["20241231", "20250331", "20240331"],
                "NET_CASH_FLOW_OPERA_ACT": [900.0, 250.0, 200.0],
                "CASH_PAID_PUR_CONST_FIOLTA": [200.0, 60.0, 40.0],
            }),
        }

    @pytest.fixture
    def market_data(self):
        return pd.DataFrame({
            "close": [10.0],
            "total_share": [1000.0],
            "market_cap": [10000.0],
            "dps": [0.5],
        }, index=pd.Index(["20250501"], name="trade_date"))

    def test_valuation_uses_market_cap_total_share_and_dividend(self, financial_data, market_data):
        result = ValuationFactors().compute("000001", financial_data, market_data, "2025-03-31")

        assert result["pe_ttm"] == pytest.approx(10000.0 / 1100.0)
        assert result["pb"] == pytest.approx(10000.0 / 4200.0)
        assert result["dividend_yield"] == pytest.approx(0.05)
        assert result["peg"] is not None

    def test_per_share_uses_tot_share_and_market_dividend(self, financial_data, market_data):
        result = PerShareFactors().compute("000001", financial_data, market_data, "2025-03-31")

        assert result["eps_ttm"] == pytest.approx(1.1)
        assert result["cfps"] == pytest.approx(0.95)
        assert result["dps"] == pytest.approx(0.5)


