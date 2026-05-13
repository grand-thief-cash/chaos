#!/usr/bin/env python3
"""
调研 Taxonomy by_security API 问题的根本原因
"""

import requests
import json

BASE_URL = "http://localhost:8085"

print("=" * 60)
print("第一步：分析 taxonomy_security_map 表的数据")
print("=" * 60)

# 测试：查询某个 symbol 的所有映射
print("\n1.1 直接查询 taxonomy_security_map 表（通过 mapping API）")
resp = requests.get(f"{BASE_URL}/api/v2/taxonomy/amazing_data/swhy/mapping/by_category/480301")
data = resp.json()
print(f"Status: {resp.status_code}")
if isinstance(data, list):
    print(f"返回记录数: {len(data)}")
    if len(data) > 0:
        print(f"字段: {list(data[0].keys())}")
        print(f"第一条记录:")
        print(json.dumps(data[0], indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("第二步：分析 taxonomy_category 表的数据")
print("=" * 60)

# 测试：查询某个 category 的详情
print("\n2.1 查询 category_code=480301 的详情")
resp = requests.get(f"{BASE_URL}/api/v2/taxonomy/amazing_data/swhy/zh_a/categories/480301")
data = resp.json()
print(f"Status: {resp.status_code}")
if isinstance(data, dict):
    print(f"字段: {list(data.keys())}")
    print(f"内容:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("第三步：分析 JOIN 的问题")
print("=" * 60)

# 测试：查询某个 symbol 的映射（有问题的 API）
print("\n3.1 查询 by_security API（有问题）")
resp = requests.get(f"{BASE_URL}/api/v2/taxonomy/by_security/000001")
data = resp.json()
print(f"Status: {resp.status_code}")
if isinstance(data, list):
    print(f"返回记录数: {len(data)}")
    if len(data) > 0:
        print(f"字段: {list(data[0].keys())}")
        print(f"内容:")
        for i, item in enumerate(data):
            print(f"\n  记录 {i+1}:")
            print(f"    category_code: {item.get('category_code')}")

print("\n" + "=" * 60)
print("第四步：对比数据")
print("=" * 60)

# 对比：
# mapping API 返回的是 TaxonomySecurityMap（只有 6 个字段）
# by_security API 应该返回的是 TaxonomySecurityMapWithDetail（12 个字段）

# 问题分析：
# 1. 如果 mapping API 返回了数据，说明 taxonomy_security_map 表有数据
# 2. 如果 categories API 返回了数据，说明 taxonomy_category 表有数据
# 3. 如果 by_security API 返回的数据缺少字段，说明：
#    a) JOIN 没有正确工作
#    b) 或者字段映射有问题

print("\n问题分析：")
print("  - taxonomy_security_map 表存在")
print("  - taxonomy_category 表存在")
print("  - 问题出在 JOIN 查询或字段映射上")
print("  - 实际返回的是 TaxonomySecurityMap（6字段）而非 TaxonomySecurityMapWithDetail（12字段）")

print("\n" + "=" * 60)
print("第五步：调研可能的解决方案")
print("=" * 60)

print("\n方案1：分两次查询（先查 mapping，再查 category）")
print("  优点：")
print("    - 简单、可靠，不依赖复杂的 JOIN")
print("    - 容易调试")
print("  缺点：")
print("    - 两次数据库往返")
print("    - 但可以用 IN 查询优化")

print("\n方案2：修复 GORM JOIN")
print("  优点：")
print("    - 一次查询完成")
print("    - 性能最优")
print("  难点：")
print("    - 需要调试 GORM Raw Scan 的字段映射")

print("\n结论：建议采用方案1（分两次查询），原因：")
print("  1. GORM Raw Scan 的字段映射问题较难调试")
print("  2. 分两次查询的性能影响可接受")
print("  3. 代码更清晰、更易维护")
