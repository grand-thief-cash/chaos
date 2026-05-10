"""
Integration test for financial data pipeline.
Tests: SDK download → post_process → PhoenixA upsert → PhoenixA query → data validation
Only uses 2 stocks (000001, 600519) for speed.
"""
import json
import sys
import time

import requests
import pandas as pd

PHOENIXA_BASE = "http://192.168.31.142:8085"

# ─── helpers ───

def phoenix_upsert(path, data):
    r = requests.post(f"{PHOENIXA_BASE}{path}", json=data, timeout=30)
    assert 200 <= r.status_code < 300, f"Upsert failed: {r.status_code} {r.text[:200]}"
    return r.json()

def phoenix_query(path, params=None):
    r = requests.get(f"{PHOENIXA_BASE}{path}", params=params or {}, timeout=30)
    assert 200 <= r.status_code < 300, f"Query failed: {r.status_code} {r.text[:200]}"
    return r.json()

def phoenix_delete_test_data(table_hint):
    """Note: PhoenixA has no delete API, so we just upsert and verify."""
    pass


# ─── SDK download helpers ───

_sdk_logged_in = False

def ensure_sdk_login():
    """Login to AmazingData SDK once."""
    global _sdk_logged_in
    if _sdk_logged_in:
        return
    import AmazingData as ad
    ad.login(
        username="10100224503",
        password="10100224503@2026",
        host="101.230.159.234",
        port=8600,
    )
    _sdk_logged_in = True
    print("  AmazingData SDK logged in")


def download_sdk_data(sdk_method_name, code_list):
    """Download data from AmazingData SDK for specific stocks."""
    import AmazingData as ad
    import os
    os.makedirs("/tmp/test_artemis_cache", exist_ok=True)

    ensure_sdk_login()
    info_data = ad.InfoData()
    base_data = ad.BaseData()

    # Get full code list and filter to test stocks only
    calendar = base_data.get_calendar()
    today = calendar[-1]
    all_codes = base_data.get_hist_code_list(
        security_type='EXTRA_STOCK_A_SH_SZ',
        start_date=20130101,
        end_date=today,
    )

    # Filter: all_codes is a list of dicts with MARKET_CODE
    test_codes = []
    for c in all_codes:
        code = c.get('MARKET_CODE', '') if isinstance(c, dict) else str(c)
        if any(t in str(code) for t in code_list):
            test_codes.append(c)

    print(f"  SDK method: {sdk_method_name}, filtered codes: {len(test_codes)}")
    if not test_codes:
        print(f"  [WARN] No matching codes found for {code_list}")
        return None

    method = getattr(info_data, sdk_method_name)
    result = method(test_codes, local_path="/tmp/test_artemis_cache", is_local=False)
    return result


def normalize_result(result):
    if isinstance(result, dict):
        return list(result.values())
    elif isinstance(result, pd.DataFrame):
        return [result]
    return []


def post_process_financial(task_type, statement_type, result):
    """Simplified version of BaseFinancialStatementTask.post_process"""
    METADATA_FIELDS = {
        'MARKET_CODE', 'SECURITY_NAME', 'STATEMENT_TYPE', 'REPORT_TYPE',
        'REPORTING_PERIOD', 'ANN_DATE', 'ACTUAL_ANN_DATE', 'COMP_TYPE_CODE',
    }

    processed = []
    frames = normalize_result(result)

    for df in frames:
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        print(f"  DataFrame shape: {df.shape}, columns sample: {list(df.columns[:5])}")
        for row in df.to_dict('records'):
            symbol_val = row.get('MARKET_CODE', '')
            if pd.isna(symbol_val):
                continue
            symbol = str(symbol_val).strip()

            period_val = row.get('REPORTING_PERIOD', '')
            if pd.isna(period_val):
                continue
            reporting_period = str(period_val).strip()
            if not symbol or not reporting_period:
                continue

            data_fields = {}
            for col, val in row.items():
                if col in METADATA_FIELDS:
                    continue
                if pd.isna(val):
                    continue
                if hasattr(val, 'item'):
                    val = val.item()
                data_fields[col] = val

            def _str(v):
                return '' if pd.isna(v) else str(v).strip()
            def _int(v):
                return 0 if pd.isna(v) else int(v)

            record = {
                'source': 'amazing_data',
                'symbol': symbol,
                'market': 'zh_a',
                'statement_type': statement_type,
                'reporting_period': reporting_period,
                'data_json': json.dumps(data_fields, ensure_ascii=False),
            }

            if task_type == 'profit_express':
                record.update({
                    'report_type': '',
                    'statement_code': '',
                    'security_name': '',
                    'ann_date': _str(row.get('ANN_DATE')),
                    'actual_ann_date': _str(row.get('ACTUAL_ANN_DATE')),
                    'comp_type_code': 0,
                })
            elif task_type == 'profit_notice':
                record.update({
                    'report_type': _str(row.get('REPORT_TYPE')),
                    'statement_code': '',
                    'security_name': _str(row.get('SECURITY_NAME')),
                    'ann_date': _str(row.get('ANN_DATE')),
                    'actual_ann_date': '',
                    'comp_type_code': 0,
                })
            else:
                record.update({
                    'report_type': _str(row.get('REPORT_TYPE')),
                    'statement_code': _str(row.get('STATEMENT_TYPE')),
                    'security_name': _str(row.get('SECURITY_NAME')),
                    'ann_date': _str(row.get('ANN_DATE')),
                    'actual_ann_date': _str(row.get('ACTUAL_ANN_DATE')),
                    'comp_type_code': _int(row.get('COMP_TYPE_CODE')),
                })

            processed.append(record)

    print(f"  post_process done: {len(processed)} records")
    return processed


def post_process_corporate(action_type, report_period_field, progress_field, result):
    """Simplified version of BaseCorporateActionTask.post_process"""
    CORP_META = {'MARKET_CODE', 'ANN_DATE'}
    all_meta = CORP_META | {report_period_field, progress_field}

    processed = []
    skipped_empty_ann = 0
    frames = normalize_result(result)

    for df in frames:
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        print(f"  DataFrame shape: {df.shape}, columns sample: {list(df.columns[:5])}")
        for row in df.to_dict('records'):
            symbol_val = row.get('MARKET_CODE', '')
            if pd.isna(symbol_val):
                continue
            symbol = str(symbol_val).strip()
            if not symbol:
                continue

            ann_date_val = row.get('ANN_DATE', '')
            ann_date = '' if pd.isna(ann_date_val) else str(ann_date_val).strip()

            rp_val = row.get(report_period_field, '')
            report_period = '' if pd.isna(rp_val) else str(rp_val).strip()

            pv_val = row.get(progress_field, '')
            progress_code = '' if pd.isna(pv_val) else str(pv_val).strip()

            if not ann_date:
                skipped_empty_ann += 1
                continue

            data_fields = {}
            for col, val in row.items():
                if col in all_meta:
                    continue
                if pd.isna(val):
                    continue
                if hasattr(val, 'item'):
                    val = val.item()
                data_fields[col] = val

            processed.append({
                'source': 'amazing_data',
                'symbol': symbol,
                'market': 'zh_a',
                'action_type': action_type,
                'report_period': report_period,
                'ann_date': ann_date,
                'progress_code': progress_code,
                'data_json': json.dumps(data_fields, ensure_ascii=False),
            })

    if skipped_empty_ann:
        print(f"  [WARN] Skipped {skipped_empty_ann} records with empty ann_date")
    print(f"  post_process done: {len(processed)} records")
    return processed


def validate_record(record, domain, dtype_name):
    """Validate a processed record."""
    errors = []
    if not record.get('symbol'):
        errors.append("empty symbol")
    if domain == 'financial':
        if not record.get('reporting_period'):
            errors.append("empty reporting_period")
        if not record.get('data_json'):
            errors.append("empty data_json")
        try:
            dj = json.loads(record['data_json'])
            if not isinstance(dj, dict) or len(dj) == 0:
                errors.append(f"data_json not a dict or empty: {type(dj)}")
        except json.JSONDecodeError as e:
            errors.append(f"data_json invalid JSON: {e}")
    elif domain == 'corporate':
        if not record.get('ann_date'):
            errors.append("empty ann_date")
        if not record.get('data_json'):
            errors.append("empty data_json")
        try:
            dj = json.loads(record['data_json'])
            if not isinstance(dj, dict) or len(dj) == 0:
                errors.append(f"data_json not a dict or empty: {type(dj)}")
        except json.JSONDecodeError as e:
            errors.append(f"data_json invalid JSON: {e}")
    return errors


# ─── test runner ───

def run_test(name, fn):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        fn()
        print(f"  ✅ PASSED: {name}")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {name}")
        print(f"     Error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ─── test cases ───

TEST_CODES = ['000001', '600519']

FINANCIAL_TASKS = [
    ("balance_sheet", "get_balance_sheet", "balance_sheet"),
    ("income", "get_income", "income"),
    ("cashflow", "get_cash_flow", "cashflow"),
    ("profit_express", "get_profit_express", "profit_express"),
    ("profit_notice", "get_profit_notice", "profit_notice"),
]

CORP_TASKS = [
    ("dividend", "get_dividend", "REPORT_PERIOD", "DIV_PROGRESS"),
    ("right_issue", "get_right_issue", "RIGHTSISSUE_YEAR", "PROGRESS"),
]


def test_phoenixa_financial_upsert_query():
    """Test PhoenixA financial statement CRUD with hand-crafted data."""
    # Upsert
    data = [
        {
            "symbol": "TEST001",
            "market": "zh_a",
            "reporting_period": "20241231",
            "report_type": "4",
            "statement_code": "1",
            "security_name": "测试公司",
            "ann_date": "20250315",
            "actual_ann_date": "20250315",
            "comp_type_code": 1,
            "data_json": json.dumps({"TOTAL_ASSETS": 1.5e11, "TOTAL_LIAB": 8e10, "CURRENCY_CAP": 5e10}),
        }
    ]
    resp = phoenix_upsert("/api/v2/financial/amazing_data/balance_sheet/upsert", data)
    assert resp["status"] == "ok" and resp["count"] == 1, f"Unexpected upsert response: {resp}"

    # Query
    result = phoenix_query("/api/v2/financial/amazing_data/balance_sheet", {"symbol": "TEST001"})
    assert result["total"] >= 1, f"Expected >=1 result, got {result['total']}"
    rec = result["data"][0]
    assert rec["symbol"] == "TEST001"
    assert rec["reporting_period"] == "20241231"
    assert rec["statement_type"] == "balance_sheet"
    dj = json.loads(rec["data_json"])
    assert "TOTAL_ASSETS" in dj, f"TOTAL_ASSETS not in data_json: {dj}"

    # Update (upsert same key with new data)
    data[0]["data_json"] = json.dumps({"TOTAL_ASSETS": 1.6e11, "TOTAL_LIAB": 8.5e10, "CURRENCY_CAP": 5.5e10})
    resp2 = phoenix_upsert("/api/v2/financial/amazing_data/balance_sheet/upsert", data)
    assert resp2["status"] == "ok"

    result2 = phoenix_query("/api/v2/financial/amazing_data/balance_sheet", {"symbol": "TEST001"})
    rec2 = result2["data"][0]
    dj2 = json.loads(rec2["data_json"])
    assert dj2["TOTAL_ASSETS"] == 1.6e11, f"Upsert update failed: {dj2}"

    print(f"  Upsert→Query→Upsert(update)→Query verified for financial_statement")


def test_phoenixa_corporate_upsert_query():
    """Test PhoenixA corporate action CRUD with hand-crafted data."""
    data = [
        {
            "symbol": "TEST001",
            "market": "zh_a",
            "report_period": "20241231",
            "ann_date": "20250401",
            "progress_code": "3",
            "data_json": json.dumps({"DVD_PER_SHARE_STK": 0.5, "DVD_PER_SHARE_PRE_TAX_CASH": 2.0}),
        }
    ]
    resp = phoenix_upsert("/api/v2/corporate-action/amazing_data/dividend/upsert", data)
    assert resp["status"] == "ok" and resp["count"] == 1

    # Query
    result = phoenix_query("/api/v2/corporate-action/amazing_data/dividend", {"symbol": "TEST001"})
    assert result["total"] >= 1
    rec = result["data"][0]
    assert rec["symbol"] == "TEST001"
    assert rec["action_type"] == "dividend"
    dj = json.loads(rec["data_json"])
    assert "DVD_PER_SHARE_STK" in dj

    # Update
    data[0]["data_json"] = json.dumps({"DVD_PER_SHARE_STK": 0.6, "DVD_PER_SHARE_PRE_TAX_CASH": 2.5})
    phoenix_upsert("/api/v2/corporate-action/amazing_data/dividend/upsert", data)
    result2 = phoenix_query("/api/v2/corporate-action/amazing_data/dividend", {"symbol": "TEST001"})
    dj2 = json.loads(result2["data"][0]["data_json"])
    assert dj2["DVD_PER_SHARE_STK"] == 0.6

    print(f"  Upsert→Query→Upsert(update)→Query verified for corporate_action")


def test_phoenixa_financial_period_range_query():
    """Test PhoenixA financial period range query."""
    # Query with period range
    result = phoenix_query("/api/v2/financial/amazing_data/balance_sheet", {
        "symbol": "TEST001",
        "period_start": "20240101",
        "period_end": "20251231",
    })
    assert result["total"] >= 1
    print(f"  Period range query: found {result['total']} records")


def test_phoenixa_pagination():
    """Test PhoenixA pagination."""
    result = phoenix_query("/api/v2/financial/amazing_data/balance_sheet", {
        "page": 1,
        "page_size": 1,
    })
    assert "data" in result and "total" in result
    print(f"  Pagination: page_size=1, total={result['total']}, returned={len(result['data'])}")


def make_sdk_download_test(task_type, sdk_method, statement_type):
    def test_fn():
        print(f"  Downloading {task_type} for codes: {TEST_CODES}...")
        result = download_sdk_data(sdk_method, TEST_CODES)

        processed = post_process_financial(task_type, statement_type, result)
        assert len(processed) > 0, f"No records produced for {task_type}"

        # Validate records
        for i, rec in enumerate(processed[:5]):
            errors = validate_record(rec, 'financial', task_type)
            if errors:
                print(f"  [WARN] Record {i} ({rec['symbol']}): {errors}")

        # Show first record summary
        r0 = processed[0]
        dj = json.loads(r0['data_json'])
        print(f"  Sample: symbol={r0['symbol']}, period={r0['reporting_period']}, "
              f"stmt_code={r0['statement_code']}, data_json fields={len(dj)}")

        # Upsert to PhoenixA (first 10 records max)
        batch = processed[:10]
        resp = phoenix_upsert(f"/api/v2/financial/amazing_data/{statement_type}/upsert", batch)
        print(f"  Upserted {resp['count']} records to PhoenixA")

        # Query back
        result = phoenix_query(f"/api/v2/financial/amazing_data/{statement_type}", {
            "symbol": r0['symbol'],
        })
        assert result["total"] >= 1, f"Query returned 0 results for {r0['symbol']}"
        qrec = result["data"][0]
        qdj = json.loads(qrec["data_json"])
        print(f"  Query back: symbol={qrec['symbol']}, period={qrec['reporting_period']}, "
              f"data_json fields={len(qdj)}")
        assert len(qdj) > 0, "data_json empty after query"

    return test_fn


def make_sdk_corporate_test(action_type, sdk_method, rp_field, progress_field):
    def test_fn():
        print(f"  Downloading {action_type} for codes: {TEST_CODES}...")
        result = download_sdk_data(sdk_method, TEST_CODES)

        processed = post_process_corporate(action_type, rp_field, progress_field, result)
        assert len(processed) > 0, f"No records produced for {action_type}"

        for i, rec in enumerate(processed[:5]):
            errors = validate_record(rec, 'corporate', action_type)
            if errors:
                print(f"  [WARN] Record {i} ({rec['symbol']}): {errors}")

        r0 = processed[0]
        dj = json.loads(r0['data_json'])
        print(f"  Sample: symbol={r0['symbol']}, period={r0['report_period']}, "
              f"ann_date={r0['ann_date']}, progress={r0['progress_code']}, data_json fields={len(dj)}")

        batch = processed[:10]
        resp = phoenix_upsert(f"/api/v2/corporate-action/amazing_data/{action_type}/upsert", batch)
        print(f"  Upserted {resp['count']} records to PhoenixA")

        result = phoenix_query(f"/api/v2/corporate-action/amazing_data/{action_type}", {
            "symbol": r0['symbol'],
        })
        assert result["total"] >= 1
        qrec = result["data"][0]
        qdj = json.loads(qrec["data_json"])
        print(f"  Query back: symbol={qrec['symbol']}, period={qrec['report_period']}, "
              f"data_json fields={len(qdj)}")
        assert len(qdj) > 0, "data_json empty after query"

    return test_fn


if __name__ == "__main__":
    import os
    os.makedirs("/tmp/test_artemis_cache", exist_ok=True)

    results = {}

    # Phase 1: PhoenixA CRUD tests (no SDK needed)
    print("\n" + "="*60)
    print("PHASE 1: PhoenixA CRUD Tests (no SDK)")
    print("="*60)
    results["CRUD: financial upsert/query/update"] = run_test(
        "PhoenixA financial upsert/query/update", test_phoenixa_financial_upsert_query)
    results["CRUD: corporate upsert/query/update"] = run_test(
        "PhoenixA corporate upsert/query/update", test_phoenixa_corporate_upsert_query)
    results["CRUD: financial period range"] = run_test(
        "PhoenixA financial period range query", test_phoenixa_financial_period_range_query)
    results["CRUD: pagination"] = run_test(
        "PhoenixA pagination", test_phoenixa_pagination)

    # Phase 2: SDK → Pipeline → PhoenixA tests
    print("\n" + "="*60)
    print("PHASE 2: SDK → Pipeline → PhoenixA (2 stocks only)")
    print("="*60)

    for task_type, sdk_method, stmt_type in FINANCIAL_TASKS:
        name = f"SDK→PhoenixA: {task_type}"
        results[name] = run_test(name, make_sdk_download_test(task_type, sdk_method, stmt_type))

    for action_type, sdk_method, rp_field, prog_field in CORP_TASKS:
        name = f"SDK→PhoenixA: {action_type}"
        results[name] = run_test(name, make_sdk_corporate_test(action_type, sdk_method, rp_field, prog_field))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  Total: {passed} passed, {failed} failed, {len(results)} tests")
    sys.exit(0 if failed == 0 else 1)
