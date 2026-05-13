# PhoenixA API 一致性分析报告

生成时间: 2026-05-13 (更新)

## 概述

本报告对 PhoenixA 的对外业务数据 API 进行了一致性测试，对比了 API 文档 (`docs/api_biz_data_description/`) 和实际 API 返回的数据。

## 测试环境

- **服务**: PhoenixA (phoenixA)
- **配置**: config-home.yaml
- **端口**: 8085
- **测试方法**: 实际 HTTP 请求验证

## 测试结果汇总

| API | 端点 | 状态 | 问题数 |
|-----|--------|------|--------|
| Securities | `/api/v2/securities` | PASS | 0 |
| Bars | `/api/v2/bars` | PASS | 0 |
| Taxonomy - by_security | `/api/v2/taxonomy/by_security/{symbol}` | PASS | 0 |
| Taxonomy - Categories | `/api/v2/taxonomy/.../categories` | PASS | 0 |
| Financial Statements | `/api/v2/financial/{source}/{statement_type}` | PASS | 0 |
| Corporate Actions | `/api/v2/corporate-action/{source}/{action_type}` | PASS | 0 |

**总计**: 9 个测试用例
- 通过: 9 (100%)
- 失败: 0 (0%)
- 警告: 0 (0%)

## 问题解决记录

### 1. Taxonomy by_security API - 字段映射问题 (已修复)

**端点**: `GET /api/v2/taxonomy/by_security/{symbol}`

**原问题**: 实际返回只有 6 个字段，缺少 `id, category_name, level, parent_code, created_at, updated_at` 这些字段。

**根本原因**:
- 旧版二进制（PID 187303，进程名 "main"）仍在运行，监听端口 8085
- 代码已正确修复（两查询方法），但新二进制未生效

**解决方案**:
1. 清理了旧版进程
2. 使用两查询方法：先查 taxonomy_security_map，再批量查 taxonomy_category
3. 合并结果到 TaxonomySecurityMapWithDetail

**验证**: API 现在返回完整的 12 个字段

---

### 2. Taxonomy Categories API - 响应格式 (已修复)

**端点**: `GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories`

**原问题**: 文档描述返回数组，实际返回 `{list: [...], total: ...}` 对象。

**解决方案**: 更新文档以反映实际的 `{list, total}` 响应格式。

**验证**: 测试脚本已更新，文档已更新

---

### 3. Financial Statements API - total 字段文档化 (已修复)

**端点**: `GET /api/v2/financial/{source}/{statement_type}`

**原问题**: 响应包含 `total` 字段，但文档中未提及。

**解决方案**: 在文档中添加响应格式说明，包含 `data` 和 `total` 字段。

**验证**: 文档更新完成

---

### 4. Corporate Actions API - total 字段文档化 (已修复)

**端点**: `GET /api/v2/corporate-action/{source}/{action_type}`

**原问题**: 响应包含 `total` 字段，但文档中未提及。

**解决方案**: 在文档中添加响应格式说明，包含 `data` 和 `total` 字段。

**验证**: 文档更新完成

---

## 响应格式一致性

当前 PhoenixA 中的响应格式：

| API | 响应格式 | 文档格式 |
|-----|----------|----------|
| Securities List | `{data: [...]}` | `{data: [...]}` ✓ |
| Securities Get | `{data: {...}}` | `{data: {...}}` ✓ |
| Securities Count | `{data: {count: ...}}` | `{data: {count: ...}}` ✓ |
| Bars Query | `{data: [...]}` | `{data: [...]}` ✓ |
| Bars Last Update | `{symbol: date, ...}` | `{symbol: date, ...}` ✓ |
| Taxonomy by_security | `[{...}]` | `[{...}]` ✓ |
| Taxonomy Categories | `{list: [...], total: ...}` | `{list: [...], total: ...}` ✓ |
| Taxonomy Mapping | `[{...}]` | `[{...}]` ✓ |
| Financial Statements | `{data: [...], total: ...}` | `{data: [...], total: ...}` ✓ |
| Corporate Actions | `{data: [...], total: ...}` | `{data: [...], total: ...}` ✓ |
| Taxonomy Industry Daily | `{data: [...], count: ...}` | `{data: [...]}` |

**注意**: Taxonomy Industry Daily 响应格式为 `{data: [...], count: ...}` 与其他 API 的 `total` 字段命名不一致，建议后续统一。

---

## 技术实现细节

### Taxonomy by_security 两查询方法

```go
// Query 1: Fetch all mappings for symbol
type MappingQuery struct {
    Source       string
    Taxonomy     string
    CategoryCode string
    Symbol       string
    AssetType    string
    Market       string
}
var mappings []MappingQuery
err := d.db.WithContext(ctx).
    Table("taxonomy_security_map").
    Where("symbol = ?", symbol).
    Find(&mappings).Error

// Query 2: Fetch category details in batch
type CategoryQuery struct {
    ID         uint64
    Code       string
    Name       string
    Level      uint8
    ParentCode string
}
var categories []CategoryQuery
err = d.db.WithContext(ctx).
    Table("taxonomy_category").
    Select("id, code, name, level, parent_code").
    Where("code IN ?", categoryCodes).
    Find(&categories).Error

// Merge results
for _, m := range mappings {
    cat, ok := categoryMap[m.CategoryCode]
    detail := &model.TaxonomySecurityMapWithDetail{
        Source:       m.Source,
        Taxonomy:     m.Taxonomy,
        CategoryCode: m.CategoryCode,
        Symbol:       m.Symbol,
        AssetType:    m.AssetType,
        Market:       m.Market,
    }
    if ok {
        detail.ID = cat.ID
        detail.CategoryName = cat.Name
        detail.Level = cat.Level
        detail.ParentCode = cat.ParentCode
    }
    list = append(list, detail)
}
```

---

## 附录

### 测试脚本

- **API 一致性测试**: `scripts/test_api_consistency.py`
- **综合 API 测试**: `scripts/comprehensive_api_test.py`
- **Taxonomy 调试脚本**: `scripts/debug_taxonomy_issue.py`

### 生成的报告

- **详细差异报告**: `docs/api_diff_report.json`

---

*报告更新: 2026-05-13*
*测试状态: 全部通过 (9/9)*
