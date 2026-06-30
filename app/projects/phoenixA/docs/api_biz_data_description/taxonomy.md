# Taxonomy API - 分类与行业数据

## 概述

提供证券分类、行业分类、行业成分股、行业权重、行业行情等数据查询。

## API 端点

### 分类映射

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/taxonomy/by_security/{symbol}` | 获取证券的所有分类映射 |

### 分类定义

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories` | 获取分类列表 |
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/{code}` | 获取分类详情 |

### 行业成分股

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_index/{indexCode}` | 按指数查询成分股 |
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_stock/{symbol}` | 按股票查询所属指数 |

### 行业权重

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/{indexCode}` | 查询指数成分股权重 |

### 行业行情

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily` | 查询行业日行情 |

## 查询参数

### GET /api/v2/taxonomy/by_security/{symbol}

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| source | string | 否 | 按数据源过滤 |
| taxonomy | string | 否 | 按分类体系过滤 |

### GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| level | integer | 否 | 按分类层级过滤 |
| parent_code | string | 否 | 按父分类过滤 |
| name | string | 否 | 按名称模糊匹配 |
| limit | integer | 否 | 返回数量限制 |
| offset | integer | 否 | 偏移量（用于分页） |

**响应格式**:
```json
{
  "list": [
    {
      "id": 1,
      "source": "amazing_data",
      "taxonomy": "sw_l1",
      "market": "zh_a",
      "code": "801000",
      "name": "银行",
      "level": 1,
      "parent_code": null,
      "is_leaf": false,
      "index_code": "801000.SI",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-05-12T00:00:00Z"
    }
  ],
  "total": 511
}
```

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| list | array | 分类定义对象数组 |
| total | integer | 总记录数 |

### GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| index_code | string | 否 | 按指数代码过滤 |
| start_date | string | 否 | 起始日期（格式 YYYY-MM-DD） |
| end_date | string | 否 | 截止日期（格式 YYYY-MM-DD） |
| limit | integer | 否 | 返回数量限制 |

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| source | string | 数据源（amazing_data, baostock 等） |
| taxonomy | string | 分类体系（sw_l1, sw_l2, sw_l3, citics 等） |
| market | string | 市场（zh_a, hk, us 等） |

## 响应数据

### 分类映射对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| source | string | 数据源 |
| taxonomy | string | 分类体系 |
| category_code | string | 分类代码 |
| category_name | string | 分类名称 |
| level | integer | 分类层级（1, 2, 3） |
| parent_code | string | 父分类代码（可能为 null） |
| index_code | string | 原始分类记录对应的行业指数代码（可能为空） |
| canonical_source | string | 标准化分类来源，仅表达体系提供方，例如 `sw` / `citics` |
| canonical_taxonomy | string | 标准化体系根，例如 `sw` / `citics` |
| canonical_level | integer | 标准化层级（1, 2, 3） |
| canonical_category_code | string | 当前层级标准化分类代码 |
| canonical_category_name | string | 当前层级标准化分类名称 |
| canonical_parent_code | string | 父层级标准化分类代码（可能为空） |
| canonical_index_code | string | 当前层级对应行业指数代码（可能为空） |
| derived_flags | object | PhoenixA 统一派生语义容器，当前包含 `financial_sector` 布尔标记 |
| symbol | string | 证券代码 |
| asset_type | string | 资产类型 |
| market | string | 市场标识 |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

### 分类定义对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| source | string | 数据源 |
| taxonomy | string | 分类体系 |
| market | string | 市场标识 |
| code | string | 分类代码 |
| name | string | 分类名称 |
| level | integer | 分类层级（1, 2, 3） |
| parent_code | string | 父分类代码（可能为 null） |
| is_leaf | boolean | 是否为叶子节点 |
| index_code | string | 关联的指数代码（可能为 null） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

### 行业成分股对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| index_code | string | 指数代码 |
| con_code | string | 成分股代码 |
| symbol | string | 成分股代码 |
| index_name | string | 指数名称 |
| in_date | string | 纳入日期（格式 YYYY-MM-DD，可能为 null） |
| out_date | string | 剔除日期（格式 YYYY-MM-DD，可能为 null） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

### 行业权重对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| index_code | string | 指数代码 |
| con_code | string | 成分股代码 |
| symbol | string | 成分股代码 |
| trade_date | string | 交易日期（格式 YYYY-MM-DD） |
| weight | float64 | 权重（%） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

### 行业日行情对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| index_code | string | 指数代码 |
| trade_date | string | 交易日期（格式 YYYY-MM-DD） |
| open | float64 | 开盘价（点数） |
| high | float64 | 最高价（点数） |
| low | float64 | 最低价（点数） |
| close | float64 | 收盘价（点数） |
| pre_close | float64 | 昨收盘价（点数） |
| amount | float64 | 成交金额（元） |
| volume | float64 | 成交量（股） |
| pb | float64 | 市净率 |
| pe | float64 | 市盈率 |
| total_cap | float64 | 总市值（万元） |
| a_float_cap | float64 | A股流通市值（万元） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

## 分类体系说明

| 分类体系 | 说明 |
|---------|------|
| sw_l1 | 申万一级行业 |
| sw_l2 | 申万二级行业 |
| sw_l3 | 申万三级行业 |
| citics | 中信行业分类 |

## 标准化行业层级字段

`GET /api/v2/taxonomy/by_security/{symbol}` 现在已经补充了一组稳定的标准化字段，供 Artemis / Cthulhu / 其他策略系统直接消费，而不必再分别解析 `sw_l1/sw_l2/...` 或依赖 `source=sw/citics` 的组合判断。

| 字段名 | 类型 | 说明 |
|--------|------|------|
| canonical_source | string | 标准化分类来源，例如 `sw`、`citics` |
| canonical_taxonomy | string | 标准化体系根，例如 `sw` / `citics` |
| canonical_level | integer | 标准化层级（1/2/3） |
| canonical_category_code | string | 当前层级的标准化分类代码 |
| canonical_category_name | string | 当前层级的标准化分类名称 |
| canonical_parent_code | string | 父层级标准化分类代码 |
| canonical_index_code | string | 对应行业指数代码 |
| derived_flags | object | 统一派生 flags 容器，例如 `{ "financial_sector": true }` |

当前语义：

1. `canonical_*` 字段只表达“统一后应如何消费”，不替代原始 `source/taxonomy/category_code`
2. `canonical_source` / `canonical_taxonomy` 当前会对 `sw_*`、`swhy`、`citics_*`、`source=sw/citics + taxonomy=industry` 等组合做统一归一
3. `canonical_level` 由 PhoenixA 明确给出，调用方不再需要从 taxonomy 字符串自行解析层级
4. `canonical_category_code` / `canonical_parent_code` / `canonical_index_code` 直接给出当前层级主键链路
5. `derived_flags` 是 PhoenixA 对 taxonomy 结果做统一派生后的语义容器，当前稳定提供 `financial_sector`
6. Artemis / Cthulhu 应直接消费 PhoenixA 提供的 `canonical_* + derived_flags`，不再在客户端重复维护 taxonomy fallback 规则
7. 若未来引入更多行业体系（如 `wind`）或更多布尔标记，也继续优先通过 `canonical_*` 与 `derived_flags` 扩展，而不是新增大量顶层 `is_*` 字段
8. `derived_flags` 由 PhoenixA 内部派生层维护，可落在独立派生表中；原始 `taxonomy_category` 继续保持 ODS/source-faithful 语义

## 响应示例

### 获取证券分类映射

```json
[
  {
    "id": 1,
    "source": "amazing_data",
    "taxonomy": "sw_l1",
    "category_code": "801000",
    "category_name": "银行",
    "level": 1,
    "parent_code": null,
    "index_code": "801000.SI",
    "canonical_source": "sw",
    "canonical_taxonomy": "sw",
    "canonical_level": 1,
    "canonical_category_code": "801000",
    "canonical_category_name": "银行",
    "canonical_parent_code": null,
    "canonical_index_code": "801000.SI",
    "derived_flags": {
      "financial_sector": true
    },
    "symbol": "000001",
    "asset_type": "stock",
    "market": "zh_a",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-05-12T00:00:00Z"
  },
  {
    "id": 2,
    "source": "amazing_data",
    "taxonomy": "sw_l2",
    "category_code": "801010",
    "category_name": "全国性股份制银行",
    "level": 2,
    "parent_code": "801000",
    "index_code": "801010.SI",
    "canonical_source": "sw",
    "canonical_taxonomy": "sw",
    "canonical_level": 2,
    "canonical_category_code": "801010",
    "canonical_category_name": "全国性股份制银行",
    "canonical_parent_code": "801000",
    "canonical_index_code": "801010.SI",
    "derived_flags": {
      "financial_sector": true
    },
    "symbol": "000001",
    "asset_type": "stock",
    "market": "zh_a",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-05-12T00:00:00Z"
  }
]
```

### 获取行业日行情

```json
[
  {
    "id": 100001,
    "index_code": "801010",
    "trade_date": "2024-05-10",
    "open": 1250.5,
    "high": 1270,
    "low": 1245.5,
    "close": 1265,
    "pre_close": 1248,
    "amount": 158000000000,
    "volume": 125000000,
    "pb": 1.8,
    "pe": 18.5,
    "total_cap": 25000000,
    "a_float_cap": 18000000,
    "created_at": "2024-05-11T00:00:00Z",
    "updated_at": "2024-05-11T00:00:00Z"
  }
]
```

---

*文档最后更新: 2026-05-14*
