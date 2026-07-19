# Factor Data Readiness API 设计

> **Status: Superseded（2026-07-14）**
>
> 本文仅保留作历史记录，已由 `docs/system_design/2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md` 替代，不得再作为新开发或验收依据。

## 概述

当接入新因子时，需要判断 PhoenixA 是否已提供所需数据。

**当前问题**：
- 手动维护 FACTOR_ENGINE_DATA_CONTRACT（因子需求）
- 手动维护 SDK_DOWNLOAD_TASK_ONBOARDING（数据供给）
- 两边难以对齐，更新容易遗漏

**解决方案**：
提供一个 API，LLM 可以像 function calling 一样调用，返回：
- 已可用的数据源
- 每个数据源包含的字段
- API 端点和使用示例

---

## API 设计

### 端点

```
GET /api/v2/catalog/factor-data-readiness
```

### 查询参数

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| category | string | 否 | 过滤特定因子分类（profitability/growth/quality/solvency/valuation/efficiency/per_share） |
| data_type | string | 否 | 过滤特定数据类型（financial/market/dividend/taxonomy） |

### 响应格式

```json
{
  "generated_at": "2026-05-11T10:00:00Z",
  "data_sources": {
    "financial": {
      "balance_sheet": {
        "available": true,
        "api_endpoint": "GET /api/v2/financial/amazing_data/balance_sheet",
        "fields": {
          "TOTAL_ASSETS": {
            "type": "number",
            "description": "总资产（元）",
            "unit": "元"
          },
          "TOT_SHARE": {
            "type": "number",
            "description": "股本（股）",
            "unit": "股"
          }
          // ... more fields
        },
        "sample_count": 224000
      },
      "income": {
        "available": true,
        "api_endpoint": "GET /api/v2/financial/amazing_data/income",
        "fields": {
          "OPERA_REV": {...},
          "NET_PRO_EXCL_MIN_INT_INC": {...}
          // ... more fields
        }
      },
      "cashflow": {
        "available": true,
        "api_endpoint": "GET /api/v2/financial/amazing_data/cashflow",
        "fields": {...}
      }
    },
    "market": {
      "bars": {
        "available": true,
        "api_endpoint": "GET /api/v2/bars/stock/zh_a",
        "fields": {
          "trade_date": {"type": "date", "description": "交易日期"},
          "open": {"type": "number", "description": "开盘价"},
          "high": {"type": "number", "description": "最高价"},
          "low": {"type": "number", "description": "最低价"},
          "close": {"type": "number", "description": "收盘价"},
          "volume": {"type": "number", "description": "成交量"}
        },
        "sample_count": 89200000
      }
    },
    "taxonomy": {
      "sw_industry": {
        "available": true,
        "api_endpoint": "GET /api/v2/taxonomy/by_security/{symbol}",
        "description": "申万行业分类",
        "fields": {
          "category_code": {"type": "string", "description": "行业代码"},
          "taxonomy": {"type": "string", "description": "分类体系"}
        }
      }
    },
    "dividend": {
      "amazing_data": {
        "available": true,
        "api_endpoint": "GET /api/v2/corporate-action/amazing_data/dividend",
        "fields": {
          "dividOperateDate": {"type": "date", "description": "除权除息日期"},
          "dividCashPsAfterTax": {"type": "number", "description": "每股股利税后"},
          "dividStocksPs": {"type": "number", "description": "每股红股"}
        }
      },
      "baostock": {
        "available": false,
        "reason": "未接入 baostock 除权除息数据",
        "missing_fields": ["dividPreNoticeDate", "dividAgmPumDate", "dividPlanAnnounceDate", ...]
      }
    }
  },
  "factor_readiness": {
    "profitability": {
      "roe": {
        "status": "ready",
        "required_fields": ["NET_PRO_EXCL_MIN_INT_INC", "TOT_SHARE_EQUITY_EXCL_MIN_INT"],
        "all_available": true
      },
      "gross_margin": {
        "status": "ready",
        "required_fields": ["OPERA_REV", "LESS_OPERA_COST"],
        "all_available": true
      }
      // ... more factors
    },
    "valuation": {
      "dividend_yield": {
        "status": "ready",
        "required_fields": ["dividCashPsAfterTax", "close"],
        "all_available": true
      },
      "ev_to_ebitda": {
        "status": "partial",
        "required_fields": ["market_cap", "EBITDA", "debt"],
        "available_fields": ["market_cap", "EBITDA"],
        "missing_fields": ["debt"],
        "can_compute": false,
        "notes": "缺少债务数据（ST_BORROWING, LT_LOAN, BONDS_PAYABLE 在 balance_sheet 中存在，但无总债务字段）"
      }
    }
  }
}
```

---

## 使用场景

### 场景 1：接入新因子 - 偿债能力因子

**需求描述**（用户提供）：
```
需要接入一个季频偿债能力因子：
- 使用 baostock 的 query_balance_data() API
- 需要 currentRatio, quickRatio, cashRatio, liabilityToAsset 等字段
```

**LLM 调用**：
```
GET /api/v2/catalog/factor-data-readiness?data_type=financial
```

**分析过程**：
1. 检查 `financial.balance_sheet` 是否包含所需字段
2. 发现：这些字段不在 PhoenixA 的 balance_sheet 中
3. 检查是否有其他数据源可能包含

**返回建议**：
```
当前状态：数据不可用
建议：需要新增 baostock 偿债能力数据下载任务
所需字段：currentRatio, quickRatio, cashRatio, liabilityToAsset, assetToEquity
可用替代：无

参考 SDK：
- baostock.query_balance_data(code, year, quarter)
```

### 场景 2：接入新因子 - 除权除息

**需求描述**：
```
需要接入除权除息相关因子：
- 需要 dividOperateDate, dividCashPsAfterTax 等字段
- 数据源可能是 amazing_data 或 baostock
```

**LLM 调用**：
```
GET /api/v2/catalog/factor-data-readiness?data_type=dividend
```

**分析过程**：
1. 检查 `dividend.amazing_data`：只有部分字段
2. 检查 `dividend.baostock`：标记为未接入
3. 对比所需字段

**返回建议**：
```
当前状态：数据部分可用
- amazing_data: 可用 dividCashPsAfterTax, dividStocksPs
- baostock: 未接入

建议：
1. 检查 amazing_data corporate_action 是否满足需求
2. 如果需要完整字段（dividPreNoticeDate 等），使用 SDK_DOWNLOAD_TASK_ONBOARDING.md 接入 baostock

参考文档：
- docs/2026-05-11 FACTOR_ENGINE_DATA_CONTRACT.md (字段语义对照）
```

### 场景 3：查询所有因子就绪状态

**LLM 调用**：
```
GET /api/v2/catalog/factor-data-readiness
```

**返回**：
- 所有因子分类的就绪状态
- 哪些因子可以计算（ready）
- 哪些因子缺失数据（partial/unavailable）

---

## 数据源注册

### 新增数据源时更新

当通过 SDK_DOWNLOAD_TASK_ONBOARDING.md 接入新数据任务时，需要在本 API 的响应中注册。

**示例：接入 baostock 季频偿债能力**

1. 在 `catalog_service.go` 中添加数据源定义
2. 在 `factor_data_readiness()` 方法中包含该数据源

```go
// 数据源注册
var factorDataSources = map[string]DataSourceInfo{
    "balance_sheet": {
        Available: true,
        APIEndpoint: "GET /api/v2/financial/amazing_data/balance_sheet",
        Fields: balanceSheetFields,
    },
    "solvency_baostock": {
        Available: false,
        Reason: "未接入",
        APIEndpoint: "",
        RequiredSDK: "baostock.query_balance_data",
        RequiredFields: []string{"currentRatio", "quickRatio", "cashRatio"},
    },
}
```

### 字段注册格式

```go
var balanceSheetFields = map[string]FieldInfo{
    "TOTAL_ASSETS": {
        Type: "number",
        Description: "总资产（元）",
        Unit: "元",
        Source: "amazing_data",
    },
    "TOT_SHARE": {
        Type: "number",
        Description: "股本（股）",
        Unit: "股",
        Source: "amazing_data",
    },
}
```

---

## 实现要点

### 1. 动态字段发现

不要硬编码字段列表，而是：
- 使用 JSONB 字段发现（已有 `discoverJSONBKeysGeneric()`）
- 从实际数据库中获取字段

```go
func (s *CatalogService) discoverFinancialFields(ctx context.Context, statementType string) map[string]FieldInfo {
    fields := make(map[string]FieldInfo)

    // 查询一条数据获取 JSONB 字段
    row, err := s.Dao.GetSampleRow(ctx, statementType)
    if err != nil {
        return fields
    }

    // 发现 JSONB 中的所有字段
    jsonbKeys := s.SchemaDao.DiscoverJSONBKeysGeneric(ctx, "security_dev", "financial_statement", "data_json", 200)
    for _, keyInfo := range jsonbKeys {
        fields[keyInfo.Name] = FieldInfo{
            Type: keyInfo.ValueType,
            Description: "", // TODO: 从配置或文档加载
            Unit: "", // TODO: 从配置或文档加载
        }
    }

    return fields
}
```

### 2. 因子需求注册

创建一个因子需求的注册表，存储每个因子需要的数据字段。

```go
// 因子需求注册
var factorRequirements = map[string]FactorRequirement{
    "roe": {
        Category: "profitability",
        RequiredFields: []string{"NET_PRO_EXCL_MIN_INT_INC", "TOT_SHARE_EQUITY_EXCL_MIN_INT"},
        RequiredDataSources: []string{"financial.balance_sheet", "financial.income"},
    },
    "gross_margin": {
        Category: "profitability",
        RequiredFields: []string{"OPERA_REV", "LESS_OPERA_COST"},
        RequiredDataSources: []string{"financial.income"},
    },
    "ev_to_ebitda": {
        Category: "valuation",
        RequiredFields: []string{"market_cap", "EBITDA", "debt"},
        RequiredDataSources: []string{"market.bars", "financial.income", "financial.balance_sheet"},
    },
}
```

### 3. 就绪状态计算

```go
func (s *CatalogService) computeFactorReadiness(ctx context.Context) map[string]FactorReadinessStatus {
    result := make(map[string]FactorReadinessStatus)

    for factorName, req := range factorRequirements {
        status := "ready"
        availableFields := []string{}
        missingFields := []string{}

        // 检查每个数据源
        for _, dataSource := range req.RequiredDataSources {
            sourceInfo := factorDataSources[dataSource]
            if !sourceInfo.Available {
                status = "unavailable"
                missingFields = append(missingFields, req.RequiredFields...)
                continue
            }

            // 检查字段是否可用
            for _, field := range req.RequiredFields {
                if _, exists := sourceInfo.Fields[field]; exists {
                    availableFields = append(availableFields, field)
                } else {
                    missingFields = append(missingFields, field)
                }
            }
        }

        if len(missingFields) > 0 {
            status = "partial"
        }

        result[factorName] = FactorReadinessStatus{
            Status: status,
            RequiredFields: req.RequiredFields,
            AvailableFields: availableFields,
            MissingFields: missingFields,
            CanCompute: status == "ready",
        }
    }

    return result
}
```

---

## 与现有 API 的关系

### data-dictionary API
- **用途**：展示数据库表结构（所有表，所有字段）
- **本 API**：聚焦因子引擎数据需求
- **不同**：本 API 按**因子使用视角**组织，data-dictionary 按**数据库视角**组织

### business-overview API
- **用途**：业务数据概览，按领域分类
- **本 API**：因子就绪状态，按数据可用性分类
- **不同**：本 API 更关注**字段级**的数据可用性

---

## 技能更新

在 `SDK_DOWNLOAD_TASK_ONBOARDING.md` 中添加：

### 阶段 6.5：Factor Engine Data Contract Update

更新为：

```markdown
## 阶段 6.5：Factor Data Readiness API 更新

当新增的下载任务数据用于 Factor Engine 因子计算时，需要同步更新 Factor Data Readiness API。

### 数据源注册

**位置**：`phoenixA/internal/service/catalog_service.go`

在 `factorDataSources` 注册表中添加新数据源：

```go
"your_data_source": {
    Available: true/false,
    APIEndpoint: "GET /api/v2/...",
    Fields: map[string]FieldInfo{},
    SampleCount: 12345,
}
```

### 字段描述来源

字段描述可以从以下来源获取：
1. **AmazingData_development_guide.md** — 现有数据源的字段说明
2. **SDK 文档** — 新接入的 SDK 的字段说明
3. **手动维护** — 对于自定义字段

### 示例：接入 baostock 季频偿债能力

```go
"solvency_baostock": {
    Available: true,
    APIEndpoint: "GET /api/v2/solvency/baostock/balance",
    Fields: map[string]FieldInfo{
        "currentRatio": {
            Type: "number",
            Description: "流动比率 = 流动资产/流动负债",
            Unit: "倍",
            Source: "baostock",
        },
        "quickRatio": {
            Type: "number",
            Description: "速动比率 = (流动资产-存货净额)/流动负债",
            Unit: "倍",
            Source: "baostock",
        },
        // ... more fields
    },
}
```

### 验证清单

新增下载任务完成后：

- [ ] Factor Data Readiness API 已注册新数据源
- [ ] 字段信息完整（类型、描述、单位）
- [ ] 因子需求已更新（如新增了因子）
- [ ] API 返回的就绪状态正确
- [ ] 使用示例已更新
```
```

---

## 下一步

1. 实现 `GET /api/v2/catalog/factor-data-readiness` 端点
2. 创建 `factor_requirements.go` 注册所有因子需求
3. 动态发现字段（不硬编码）
4. 编写 LLM skill，调用此 API 进行就绪检查
5. 前端集成（可选）：在 Cthulhu 中展示因子就绪状态
