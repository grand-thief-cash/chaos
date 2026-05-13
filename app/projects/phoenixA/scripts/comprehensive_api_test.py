#!/usr/bin/env python3
"""
综合测试：检查所有 API 的响应格式
"""

import requests
import json

BASE_URL = "http://localhost:8085"

def test_and_print(name, url, params=None):
    """测试并打印结果"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    if params:
        print(f"Params: {params}")
    print('='*60)

    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        print(f"Status: {resp.status_code}")

        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    print(f"\n  {key}: (array with {len(value)} items)")
                    print(f"    First item keys: {list(value[0].keys())}")
                    print(f"    First item sample:")
                    sample = dict(list(value[0].items())[:5])
                    print(f"    {json.dumps(sample, indent=6, ensure_ascii=False)}")
                elif isinstance(value, dict):
                    print(f"\n  {key}: (dict)")
                    print(f"    Keys: {list(value.keys())}")
                else:
                    print(f"\n  {key}: {value}")
        elif isinstance(data, list) and len(data) > 0:
            print(f"Type: array with {len(data)} items")
            print(f"First item keys: {list(data[0].keys())}")
        else:
            print(f"Data: {data}")

    except Exception as e:
        print(f"Error: {e}")

# Test all APIs
test_and_print("Securities List", f"{BASE_URL}/api/v2/securities", {"limit": "1"})
test_and_print("Securities Get", f"{BASE_URL}/api/v2/securities/000001")
test_and_print("Securities Count", f"{BASE_URL}/api/v2/securities/count")

test_and_print("Bars Query", f"{BASE_URL}/api/v2/bars/stock/zh_a", {
    "symbol": "000001",
    "start_date": "2024-01-01",
    "end_date": "2024-01-05",
    "period": "daily",
    "adjust": "nf",
    "limit": "1"
})
test_and_print("Bars Last Update", f"{BASE_URL}/api/v2/bars/stock/zh_a/last_update", {
    "period": "daily",
    "adjust": "nf",
    "symbols": "000001"
})

test_and_print("Taxonomy by_security", f"{BASE_URL}/api/v2/taxonomy/by_security/000001")
test_and_print("Taxonomy Categories", f"{BASE_URL}/api/v2/taxonomy/amazing_data/swhy/zh_a/categories", {"limit": "1"})

test_and_print("Financial Statements", f"{BASE_URL}/api/v2/financial/amazing_data/balance_sheet", {
    "symbol": "000001",
    "limit": "1"
})

test_and_print("Corporate Actions", f"{BASE_URL}/api/v2/corporate-action/amazing_data/dividend", {
    "symbol": "000001",
    "limit": "1"
})
