# Bars API - K线/OHLCV 行情数据

## 概述

提供证券的 K线（OHLCV）行情数据查询与写入。

> **Phase 4 (`security_registry` 代理主键重构)**: bars API 契约已迁 `security_id`（无双轨，§3.6）。
> `security_id` 在 controller 入口解析为物理 `symbol` 后再查/写 `bars_*` 物理表；`bars_*` 物理表
> 仍以 `symbol` 为主键（§3.2 永久存储特例）。路径 `{asset_type}/{market}` 必须与 `security_id`
> 解析出的资产类型/市场一致，否则 400（§10.d.4 option A）。`symbol`/`symbols` 参数已废弃，传则 400。

## API 端点

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/bars/{asset_type}/{market}` | 查询 K 线数据 |
| POST | `/api/v2/bars/{asset_type}/{market}/upsert` | 写入 K 线数据 |
| GET | `/api/v2/bars/{asset_type}/{market}/last_update` | 获取最新数据日期 |

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| asset_type | string | 资产类型（stock, index, fund 等）；须与 security_id 解析结果一致 |
| market | string | 市场（zh_a, hk, us 等）；须与 security_id 解析结果一致 |

## 查询参数

### GET /api/v2/bars/{asset_type}/{market}

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| security_id | integer | 是 | 证券ID（`security_registry.id`）。`symbol`/`symbols` 已废弃，传则 400 |
| start_date | string | 是 | 起始日期（格式 YYYY-MM-DD） |
| end_date | string | 是 | 截止日期（格式 YYYY-MM-DD） |
| period | string | 是 | 周期（1min, 5min, 15min, 30min, 60min, daily, weekly, monthly） |
| adjust | string | 是 | 复权类型（nf, qfq, hfq） |
| limit | integer | 否 | 返回数量限制（默认 1000，最大 5000） |
| offset | integer | 否 | 分页偏移量 |
| fields | string | 否 | 返回字段列表（逗号分隔） |

严格校验：`security_id` 为空、0、非数字 → 400（绝不静默退化为未过滤查询，与 Phase 1/3 一致）。

### POST /api/v2/bars/{asset_type}/{market}/upsert

请求体：

```json
{
  "meta": {"period": "daily", "adjust": "nf", "source": "baostock"},
  "bars": [{"security_id": 1, "trade_date": "2026-01-05", "open": 10.0, "high": 11.0,
            "low": 9.5, "close": 10.5, "volume": 1000, "amount": 10500,
            "preclose": 9.8, "pct_chg": 1.92}],
  "ext":  [{"security_id": 1, "trade_date": "2026-01-05", "turn": 1.2,
            "pe_ttm": 15.0, "ps_ttm": 2.0, "pb_mrq": 1.5, "pcf_ncf_ttm": 8.0}]
}
```

每行 `bars`/`ext` 必须携带 `security_id`；未知 id 或路径 `{asset_type}/{market}` 与解析结果不一致 → 400（orphan 防护，§10.c）。controller 在入口解析 `security_id → symbol` 后再进 DAO/write buffer，故异步 buffer 收到的已是 resolved 物理 行（§10.d.2）。

### GET /api/v2/bars/{asset_type}/{market}/last_update

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| security_id | integer | 否 | 单个证券ID |
| security_ids | string | 否 | 证券ID列表（逗号分隔） |
| period | string | 是 | 周期 |
| adjust | string | 是 | 复权类型 |

`security_id` 与 `security_ids` 至少传一个；`symbols` 已废弃，传则 400。严格校验：空/0/非数字/空 token → 400。

## 响应数据

### K线对象（Bar）

返回字段基于 JSON，类型为数字或字符串：

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| security_id | integer | 证券ID（响应装饰，→ security_registry.id；物理表存 symbol，§3.2） |
| symbol | string | 证券代码（响应装饰） |
| trade_date | string | 交易日期（格式 YYYY-MM-DD） |
| open | float64 | 开盘价（元） |
| high | float64 | 最高价（元） |
| low | float64 | 最低价（元） |
| close | float64 | 收盘价（元） |
| volume | integer | 成交量（股） |
| amount | integer | 成交金额（元） |
| preclose | float64 | 昨收盘价（元） |
| pct_chg | float64 | 涨跌幅（%） |

### Baostock 扩展字段

当 data_source 为 baostock 时，以下字段可能存在：

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| turn | float64 | 换手率（%） |
| pe_ttm | float64 | 市盈率（TTM） |
| ps_ttm | float64 | 市销率（TTM） |
| pb_mrq | float64 | 市净率（MRQ） |
| pcf_ncf_ttm | float64 | 市现率（TTM，经营活动现金流） |

## 响应格式

### 查询 K 线数据

```json
{
  "data": [
    {
      "security_id": 1,
      "symbol": "000001",
      "trade_date": "2024-05-10",
      "open": 12.5,
      "high": 12.75,
      "low": 12.45,
      "close": 12.68,
      "volume": 125000000,
      "amount": 1582000000,
      "preclose": 12.5,
      "pct_chg": 1.44
    }
  ]
}
```

### 获取最新数据日期

```json
{
  "data": [
    {"security_id": 1, "symbol": "000001", "last_update": "2024-05-13"},
    {"security_id": 2, "symbol": "600000", "last_update": "2024-05-13"}
  ]
}
```

### 写入 K 线数据

```json
{"status": "ok"}
```

## period 参数说明

| 值 | 说明 |
|-----|------|
| 1min | 1分钟 K线 |
| 5min | 5分钟 K线 |
| 15min | 15分钟 K线 |
| 30min | 30分钟 K线 |
| 60min | 60分钟 K线 |
| daily | 日 K线 |
| weekly | 周 K线 |
| monthly | 月 K线 |

## adjust 参数说明

| 值 | 说明 |
|-----|------|
| nf | 不复权 |
| qfq | 前复权 |
| hfq | 后复权 |

## fields 参数说明

当指定 fields 参数时，响应只包含指定的字段。可用字段：

| 字段名 | 说明 |
|--------|------|
| security_id | 证券ID（响应装饰） |
| symbol | 证券代码 |
| trade_date | 交易日期 |
| open | 开盘价 |
| high | 最高价 |
| low | 最低价 |
| close | 收盘价 |
| volume | 成交量 |
| amount | 成交金额 |
| preclose | 昨收盘价 |
| pct_chg | 涨跌幅 |

---

*文档最后更新: 2026-07-04 (Phase 4: security_id 迁移)*
