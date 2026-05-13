# industry_daily - 行业指数日行情表

## 概述

`industry_daily` 表存储行业指数的每日行情数据，包括 OHLCV、市值、PE/PB 等指标。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL | 数据源标识（如: `amazing_data`） |
| index_code | VARCHAR(32) | NOT NULL | 指数代码 |
| trade_date | VARCHAR(10) | NOT NULL | 交易日期（YYYY-MM-DD 格式） |
| open | FLOAT | NOT NULL DEFAULT 0 | 开盘价 |
| high | FLOAT | NOT NULL DEFAULT 0 | 最高价 |
| low | FLOAT | NOT NULL DEFAULT 0 | 最低价 |
| close | FLOAT | NOT NULL DEFAULT 0 | 收盘价 |
| volume | BIGINT | NOT NULL DEFAULT 0 | 成交量（股） |
| amount | DECIMAL(20,2) | NOT NULL DEFAULT 0 | 成交金额（元） |
| pre_close | FLOAT | NOT NULL DEFAULT 0 | 昨收盘价 |
| pe | DECIMAL(10,2) | NOT NULL DEFAULT 0 | 指数市盈率 |
| pb | DECIMAL(10,2) | NOT NULL DEFAULT 0 | 指数市净率 |
| total_cap | DECIMAL(20,2) | NOT NULL DEFAULT 0 | 总市值（万元） |
| a_float_cap | DECIMAL(20,2) | NOT NULL DEFAULT 0 | A 股流通市值（万元） |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

## 唯一索引

- `uk_industry_daily`: (source, index_code, trade_date)

## B-tree 索引

- `idx_ind_daily_index`: (index_code)
- `idx_ind_daily_date`: (trade_date)

## 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_daily(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.4 行业指数日行情

## 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| OPEN | float | 开盘价 | - |
| HIGH | float | 最高价 | - |
| CLOSE | float | 收盘价 | - |
| LOW | float | 最低价 | - |
| AMOUNT | float | 成交金额（元） | - |
| VOLUME | float | 成交量（股） | - |
| PB | float | 指数市净率 | - |
| PE | float | 指数市盈率 | - |
| TOTAL_CAP | float | 总市值（万元） | - |
| A_FLOAT_CAP | float | A 股流通市值（万元） | - |
| INDEX_CODE | string | 指数代码 | - |
| PRE_CLOSE | float | 昨收盘价 | - |
| TRADE_DATE | string | 交易日期 | YYYY-MM-DD 格式 |

## 示例数据

```json
{
  "INDEX_CODE": "801010",
  "TRADE_DATE": "2024-06-15",
  "OPEN": 1250.5,
  "HIGH": 1270.0,
  "LOW": 1245.5,
  "CLOSE": 1265.0,
  "VOLUME": 125000000,
  "AMOUNT": 158000000000,
  "PRE_CLOSE": 1248.0,
  "PE": 18.5,
  "PB": 1.8,
  "TOTAL_CAP": 25000000,
  "A_FLOAT_CAP": 18000000
}
```

## 查询示例

```sql
-- 查询某指数的日行情
SELECT * FROM industry_daily
WHERE index_code = '801010' AND trade_date >= '2024-01-01'
ORDER BY trade_date DESC;

-- 查询某指数最新的行情数据
SELECT * FROM industry_daily
WHERE index_code = '801010'
ORDER BY trade_date DESC
LIMIT 1;
```

---

*文档最后更新: 2026-05-12*
