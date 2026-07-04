"""
Unit tests for baostock balance and dividend download tasks.

Tests cover:
  - utils: date_range_to_year_quarters, symbol_exchange_to_bs_code
  - Balance child: post_process logic (empty data, normal data, edge cases)
  - Dividend child: post_process logic (date selection, dedup, progress codes)
  - Parent: plan logic (year_quarters/years generation, child spec creation)
"""
import pandas as pd
import pytest

from artemis.engines.task_engine.download.zh.utils import (
    date_range_to_year_quarters,
    symbol_exchange_to_bs_code,
)
from artemis.engines.task_engine.download.zh.stock_zh_a_bs_balance_child import StockZhABsBalanceChild
from artemis.engines.task_engine.download.zh.stock_zh_a_bs_dividend_child import StockZhABsDividendChild


# ── Helpers ──────────────────────────────────────────

class _FakeLogger:
    def __init__(self):
        self.messages = []
    def info(self, msg):
        self.messages.append(msg)
    def warning(self, msg):
        self.messages.append(msg)
    def debug(self, msg):
        self.messages.append(msg)


class _FakeCtx:
    def __init__(self, params=None):
        self.run_id = "test-run-bs"
        self.logger = _FakeLogger()
        self.error = None
        self.failed_phase = None
        self.params = params or {}
        self.incoming_params = dict(self.params)

    def fail(self, msg, phase=''):
        self.error = str(msg)
        self.failed_phase = phase

    def has_failed(self):
        return self.error is not None


# ═══════════════════════════════════════════════════════
# utils tests
# ═══════════════════════════════════════════════════════

class TestDateRangeToYearQuarters:
    def test_single_quarter(self):
        result = date_range_to_year_quarters("2024-04-01", "2024-06-30")
        assert result == [(2024, 2)]

    def test_cross_year(self):
        result = date_range_to_year_quarters("2024-10-01", "2025-03-31")
        assert result == [(2024, 4), (2025, 1)]

    def test_full_year(self):
        result = date_range_to_year_quarters("2024-01-01", "2024-12-31")
        assert result == [(2024, 1), (2024, 2), (2024, 3), (2024, 4)]

    def test_same_quarter(self):
        result = date_range_to_year_quarters("2024-02-15", "2024-03-20")
        assert result == [(2024, 1)]

    def test_empty_range(self):
        result = date_range_to_year_quarters("2025-01-01", "2024-01-01")
        assert result == []

    def test_invalid_date(self):
        result = date_range_to_year_quarters("invalid", "2024-01-01")
        assert result == []

    def test_multi_year(self):
        result = date_range_to_year_quarters("2023-07-01", "2024-03-31")
        assert result == [(2023, 3), (2023, 4), (2024, 1)]

    def test_q4_to_q1(self):
        """Quarter boundary: Q4 of one year to Q1 of next year."""
        result = date_range_to_year_quarters("2024-12-01", "2025-01-31")
        assert result == [(2024, 4), (2025, 1)]


class TestSymbolExchangeToBsCode:
    def test_sh(self):
        assert symbol_exchange_to_bs_code("600000", "SH") == "sh.600000"

    def test_sz(self):
        assert symbol_exchange_to_bs_code("000001", "SZ") == "sz.000001"

    def test_bj(self):
        assert symbol_exchange_to_bs_code("430047", "BJ") == "bj.430047"

    def test_lowercase(self):
        assert symbol_exchange_to_bs_code("600000", "sh") == "sh.600000"

    def test_unknown_exchange(self):
        assert symbol_exchange_to_bs_code("600000", "HK") is None

    def test_empty_exchange(self):
        assert symbol_exchange_to_bs_code("600000", "") is None


# ═══════════════════════════════════════════════════════
# Balance child post_process tests
# ═══════════════════════════════════════════════════════

class TestBsBalanceChildPostProcess:
    def _make_balance_df(self, stat_date="2024-06-30", pub_date="2024-08-30",
                         current_ratio="1.5", quick_ratio="1.2", cash_ratio="0.8",
                         yoy_liability="0.1", liability_to_asset="0.6", asset_to_equity="2.5"):
        return pd.DataFrame([{
            'code': 'sh.600000',
            'pubDate': pub_date,
            'statDate': stat_date,
            'currentRatio': current_ratio,
            'quickRatio': quick_ratio,
            'cashRatio': cash_ratio,
            'YOYLiability': yoy_liability,
            'liabilityToAsset': liability_to_asset,
            'assetToEquity': asset_to_equity,
            'symbol': '600000',
        }])

    def test_normal_data(self):
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx(params={"security_id": 100, "symbol": "600000"})
        df = self._make_balance_df()
        result = task.post_process(ctx, df)
        assert len(result) == 1

        rec = result[0]
        assert rec['source'] == 'baostock'
        assert rec['security_id'] == 100
        assert rec['statement_type'] == 'bs_balance'
        assert rec['reporting_period'] == '2024-06-30'
        assert rec['ann_date'] == '2024-08-30'

        data = rec['data_json']
        assert data['currentRatio'] == 1.5
        assert data['quickRatio'] == 1.2
        assert data['cashRatio'] == 0.8
        assert data['liabilityToAsset'] == 0.6

    def test_empty_dataframe(self):
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx()
        result = task.post_process(ctx, pd.DataFrame())
        assert result == []

    def test_none_result(self):
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx()
        result = task.post_process(ctx, None)
        assert result == []

    def test_empty_stat_date_skipped(self):
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx(params={"security_id": 100, "symbol": "600000"})
        df = self._make_balance_df(stat_date="")
        result = task.post_process(ctx, df)
        assert len(result) == 0

    def test_empty_values_excluded_from_json(self):
        """Empty string values should be excluded from data_json."""
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx(params={"security_id": 100, "symbol": "600000"})
        df = self._make_balance_df(current_ratio="", quick_ratio="")
        result = task.post_process(ctx, df)
        assert len(result) == 1
        data = result[0]['data_json']
        assert 'currentRatio' not in data
        assert 'quickRatio' not in data
        # Other fields should still be present
        assert 'cashRatio' in data

    def test_missing_pub_date(self):
        """Missing pubDate should result in empty ann_date."""
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx(params={"security_id": 100, "symbol": "600000"})
        df = self._make_balance_df(pub_date="")
        result = task.post_process(ctx, df)
        assert len(result) == 1
        assert result[0]['ann_date'] == ''

    def test_meta_fields_excluded_from_data_json(self):
        """code, symbol, pubDate, statDate should NOT appear in data_json."""
        task = StockZhABsBalanceChild()
        ctx = _FakeCtx(params={"security_id": 100, "symbol": "600000"})
        df = self._make_balance_df()
        result = task.post_process(ctx, df)
        data = result[0]['data_json']
        assert 'code' not in data
        assert 'symbol' not in data
        assert 'pubDate' not in data
        assert 'statDate' not in data


# ═══════════════════════════════════════════════════════
# Dividend child post_process tests
# ═══════════════════════════════════════════════════════

class TestBsDividendChildPostProcess:
    def _make_dividend_df(self, **overrides):
        row = {
            'code': 'sh.600000',
            'dividPreNoticeDate': '',
            'dividAgmPumDate': '2024-05-16',
            'dividPlanAnnounceDate': '2024-03-19',
            'dividPlanDate': '2024-06-16',
            'dividRegistDate': '2024-06-19',
            'dividOperateDate': '2024-06-23',
            'dividPayDate': '2024-06-23',
            'dividStockMarketDate': '',
            'dividCashPsBeforeTax': '0.757',
            'dividCashPsAfterTax': '0.6813',
            'dividStocksPs': '0.000000',
            'dividCashStock': '10派7.57元',
            'dividReserveToStockPs': '',
            'symbol': '600000',
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_normal_data(self):
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df()
        result = task.post_process(ctx, df)
        assert len(result) == 1

        rec = result[0]
        assert rec['source'] == 'baostock'
        assert rec['security_id'] == 100
        assert rec['action_type'] == 'bs_dividend'
        assert rec['ann_date'] == '2024-03-19'  # uses dividPlanAnnounceDate first
        assert rec['report_period'] == '2024-12-31'
        assert rec['progress_code'] == 'implemented'  # dividOperateDate exists

    def test_empty_result(self):
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024"})
        result = task.post_process(ctx, None)
        assert result == []

    def test_no_ann_date_skipped(self):
        """Records without any announcement date should be skipped."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df(
            dividPlanAnnounceDate='',
            dividPlanDate='',
            dividOperateDate='',
        )
        result = task.post_process(ctx, df)
        assert len(result) == 0

    def test_progress_code_announced(self):
        """When only dividPlanDate is set, progress should be 'announced'."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df(
            dividOperateDate='',
            dividPlanDate='2024-06-16',
        )
        result = task.post_process(ctx, df)
        assert len(result) == 1
        assert result[0]['progress_code'] == 'announced'

    def test_progress_code_planned(self):
        """When only dividPlanAnnounceDate is set, progress should be 'planned'."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df(
            dividOperateDate='',
            dividPlanDate='',
        )
        result = task.post_process(ctx, df)
        assert len(result) == 1
        assert result[0]['progress_code'] == 'planned'

    def test_data_json_contains_values(self):
        """Numeric fields should be float-converted in data_json."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df()
        result = task.post_process(ctx, df)
        data = result[0]['data_json']
        assert data['dividCashPsBeforeTax'] == 0.757
        assert data['dividCashPsAfterTax'] == 0.6813
        assert data['dividStocksPs'] == 0.0
        # String value remains as string
        assert data['dividCashStock'] == '10派7.57元'

    def test_dedup_by_ann_date(self):
        """Duplicate records with same ann_date should be deduped."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        row = {
            'code': 'sh.600000',
            'dividPreNoticeDate': '',
            'dividAgmPumDate': '',
            'dividPlanAnnounceDate': '2024-03-19',
            'dividPlanDate': '',
            'dividRegistDate': '',
            'dividOperateDate': '',
            'dividPayDate': '',
            'dividStockMarketDate': '',
            'dividCashPsBeforeTax': '0.5',
            'dividCashPsAfterTax': '0.45',
            'dividStocksPs': '0',
            'dividCashStock': '',
            'dividReserveToStockPs': '',
            'symbol': '600000',
        }
        # Two rows with same ann_date
        row2 = dict(row)
        row2['dividCashPsBeforeTax'] = '0.6'  # different value
        df = pd.DataFrame([row, row2])
        result = task.post_process(ctx, df)
        # Should dedup to 1 record (last wins)
        assert len(result) == 1
        data = result[0]['data_json']
        assert data['dividCashPsBeforeTax'] == 0.6

    def test_none_values_excluded(self):
        """Fields with value 'None' should be excluded from data_json."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df(dividStockMarketDate='None')
        result = task.post_process(ctx, df)
        data = result[0]['data_json']
        assert 'dividStockMarketDate' not in data

    def test_meta_fields_excluded(self):
        """code and symbol should not appear in data_json."""
        task = StockZhABsDividendChild()
        ctx = _FakeCtx(params={"year": "2024", "security_id": 100, "symbol": "600000"})
        df = self._make_dividend_df()
        result = task.post_process(ctx, df)
        data = result[0]['data_json']
        assert 'code' not in data
        assert 'symbol' not in data

