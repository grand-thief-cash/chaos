# Securities API - 证券基础信息

## 概述

提供证券基础信息查询，包括股票、指数、基金等证券的代码、名称、交易所、上市状态等信息。

`security_registry` 的代理主键 `security_id` (BIGSERIAL) 是 `(exchange, asset_type, symbol)` 自然键的代理，作为其他表逻辑外键 `security_id` 的引用目标（不建真实 FK 约束）。`security_id` 是永久、不可回收的内部身份；全量刷新必须按自然键 upsert，并通过 `status`、`list_date`、`delist_date` 表达生命周期，禁止删除后重建注册表。

## API 端点

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/securities` | 查询证券列表 |
| GET | `/api/v2/securities/{security_id}` | 按 security_id 获取单个证券信息 |
| GET | `/api/v2/securities/count` | 统计证券数量 |
| POST | `/api/v2/securities/upsert` | 批量插入/更新证券信息（按自然键 upsert，已有 security_id 保持不变） |

## 查询参数

### GET /api/v2/securities

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| security_id | integer | 否 | 证券代理主键（单个，优先于自然键筛选） |
| symbol | string | 否 | 证券代码（单个） |
| symbols | string | 否 | 证券代码列表（逗号分隔） |
| symbol_list | string | 否 | 证券代码列表（逗号分隔，别名） |
| asset_type | string | 否 | 资产类型（默认：stock） |
| market | string | 否 | 市场（默认：zh_a） |
| exchange | string | 否 | 交易所 |
| exchanges | string | 否 | 交易所列表（逗号分隔） |
| name | string | 否 | 证券名称（模糊匹配） |
| status | string | 否 | 状态（默认：active） |
| limit | integer | 否 | 返回数量限制 |
| offset | integer | 否 | 分页偏移量 |

### GET /api/v2/securities/{security_id}

按代理主键 `security_id` 查询单个证券，无需 `asset_type`/`market` 参数（id 已唯一标识行）。

### GET /api/v2/securities/count

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| asset_type | string | 否 | 资产类型（默认：stock） |
| market | string | 否 | 市场（默认：zh_a） |
| exchange | string | 否 | 交易所 |
| name | string | 否 | 证券名称（模糊匹配） |
| status | string | 否 | 状态（默认：active） |

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| security_id | integer | 证券代理主键 (BIGSERIAL)，(exchange, asset_type, symbol) 自然键的代理 |

## 请求体

### POST /api/v2/securities/upsert

按自然键 `(exchange, asset_type, symbol)` upsert。新证券由数据库分配 `security_id`，已有证券更新属性但保留原 `security_id`（client 无需也不应传入 id）。退市或暂时不活跃的证券仍保留注册表行，通过 `status`、`list_date`、`delist_date` 更新生命周期。

## 响应数据

### 证券对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| security_id | integer | 证券代理主键 (BIGSERIAL) |
| symbol | string | 证券代码（纯代码） |
| asset_type | string | 资产类型 |
| market | string | 市场 |
| exchange | string | 交易所（SZ, SH 等） |
| name | string | 证券名称 |
| full_name | string | 证券全称（可选，预留） |
| status | string | 状态（active, delisted 等） |
| list_date | string | 上市日期（格式 YYYY-MM-DD，可选，预留） |
| delist_date | string | 退市日期（格式 YYYY-MM-DD，可选，预留） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

## 资产类型说明

| 值 | 说明 |
|----|------|
| stock | 股票 |
| index | 指数 |
| fund | 基金 |
| bond | 债券 |

## 市场说明

| 值 | 说明 |
|----|------|
| zh_a | 中国A股 |
| hk | 香港 |
| us | 美国 |

## 交易所说明

| 值 | 说明 |
|----|------|
| SZ | 深圳证券交易所 |
| SH | 上海证券交易所 |

## 响应示例

### 查询证券列表

```json
{
  "data": [
    {
      "security_id": 1,
      "symbol": "000001",
      "asset_type": "stock",
      "market": "zh_a",
      "exchange": "SZ",
      "name": "平安银行",
      "status": "active",
      "created_at": "2026-04-14T15:08:16+08:00",
      "updated_at": "2026-05-13T12:41:59+08:00"
    }
  ]
}
```

### 获取单个证券

```json
{
  "data": {
    "security_id": 1,
    "symbol": "000001",
    "asset_type": "stock",
    "market": "zh_a",
    "exchange": "SZ",
    "name": "平安银行",
    "status": "active",
    "created_at": "2026-04-14T15:08:16+08:00",
    "updated_at": "2026-05-13T12:41:59+08:00"
  }
}
```

### 统计证券数量

```json
{
  "data": {
    "count": 10585
  }
}
```

---

*文档最后更新: 2026-07-14*
