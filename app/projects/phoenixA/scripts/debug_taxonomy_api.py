#!/usr/bin/env python3
"""
调试脚本：检查 taxonomy by_security API 的返回
"""

import requests
import json

# 测试不同的 taxonomy 值
taxonomies = ["swhy", "sw_l1", "sw_l2"]

for taxonomy in taxonomies:
    print(f"\n=== Testing taxonomy: {taxonomy} ===")
    resp = requests.get(f"http://localhost:8085/api/v2/taxonomy/by_security/000001?taxonomy={taxonomy}")
    data = resp.json()
    print(f"Status: {resp.status_code}")
    if isinstance(data, list) and len(data) > 0:
        print(f"Count: {len(data)}")
        print(f"Fields: {list(data[0].keys())}")
        print(f"First item:")
        print(json.dumps(data[0], indent=2, ensure_ascii=False))
