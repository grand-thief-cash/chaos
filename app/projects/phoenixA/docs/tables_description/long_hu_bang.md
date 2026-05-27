# long_hu_bang - 龙虎榜数据表

## 概述

`long_hu_bang` 表存储 A 股龙虎榜营业部明细。每条记录表示某只证券在某个交易日、某个上榜原因下，一个营业部的一笔买入/卖出方向明细。

数据来源：AmazingData `InfoData.get_long_hu_bang()`。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| source | VARCHAR(32) | NOT NULL, UNIQUE | 数据源标识，如 `amazing_data` |
| symbol | VARCHAR(32) | NOT NULL, UNIQUE | 证券代码（纯代码，如 `000001`） |
| market | VARCHAR(16) | NOT NULL, DEFAULT `zh_a`, UNIQUE | 市场标识 |
| trade_date | VARCHAR(10) | NOT NULL, UNIQUE | 交易日期，格式 `YYYY-MM-DD` |
| security_name | VARCHAR(128) | NOT NULL, DEFAULT `''` | 证券名称 |
| reason_type | VARCHAR(32) | NOT NULL, UNIQUE | 上榜原因类型代码 |
| reason_type_name | VARCHAR(256) | NOT NULL, DEFAULT `''` | 上榜原因名称 |
| trader_name | VARCHAR(256) | NOT NULL, UNIQUE | 营业部名称 |
| flow_mark | SMALLINT | NOT NULL, UNIQUE | 买卖方向：`1` 买入，`2` 卖出 |
| change_range | NUMERIC(20,6) | NOT NULL, DEFAULT `0` | 涨跌幅（%） |
| buy_amount | NUMERIC(24,4) | NOT NULL, DEFAULT `0` | 买入金额（元） |
| sell_amount | NUMERIC(24,4) | NOT NULL, DEFAULT `0` | 卖出金额（元） |
| total_amount | NUMERIC(24,4) | NOT NULL, DEFAULT `0` | 实际交易金额（元） |
| total_volume | NUMERIC(24,4) | NOT NULL, DEFAULT `0` | 实际交易量（万股） |

## 唯一索引

- `uk_long_hu_bang`: (`source`, `symbol`, `market`, `trade_date`, `reason_type`, `trader_name`, `flow_mark`)

## B-tree 索引

- `idx_lhb_symbol_date`: (`symbol`, `market`, `trade_date DESC`)
- `idx_lhb_trade_date`: (`trade_date DESC`)
- `idx_lhb_reason_date`: (`reason_type`, `trade_date DESC`, `flow_mark`)

## 典型查询

```sql
-- 查询单只股票最近一个月的龙虎榜明细
SELECT symbol, trade_date, reason_type, trader_name, flow_mark, buy_amount, sell_amount
FROM long_hu_bang
WHERE source = 'amazing_data'
  AND symbol = '000001'
  AND trade_date BETWEEN '2026-05-01' AND '2026-05-31'
ORDER BY trade_date DESC, trader_name;

-- 查询某个上榜原因下的买入席位
SELECT symbol, trade_date, trader_name, buy_amount
FROM long_hu_bang
WHERE reason_type = '1001'
  AND flow_mark = 1
ORDER BY trade_date DESC;
```


