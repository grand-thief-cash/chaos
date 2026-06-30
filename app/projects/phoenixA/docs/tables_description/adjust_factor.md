# adjust_factor - 复权因子数据表

## 概述

`adjust_factor` 表存储证券在除权除息事件上的复权因子数据。该表是独立于 `corporate_action` 的市场数据支撑表，主要用于基于本地不复权日线重建前复权/后复权价格。

数据来源：Baostock `query_adjust_factor()`。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL, UNIQUE | 数据源标识，如 `baostock` |
| symbol | VARCHAR(32) | NOT NULL, UNIQUE | 证券代码（纯代码，如 `600000`） |
| market | VARCHAR(16) | NOT NULL, DEFAULT `zh_a`, UNIQUE | 市场标识 |
| divid_operate_date | VARCHAR(10) | NOT NULL, UNIQUE | 除权除息日期，格式 `YYYY-MM-DD` |
| fore_adjust_factor | NUMERIC(20,8) | NULL | 向前复权因子 |
| back_adjust_factor | NUMERIC(20,8) | NULL | 向后复权因子 |
| adjust_factor | NUMERIC(20,8) | NULL | 本次复权因子 |

## 唯一索引

- `uk_adjust_factor`: (`source`, `symbol`, `market`, `divid_operate_date`)

## B-tree 索引

- `idx_af_symbol_date`: (`symbol`, `market`, `divid_operate_date DESC`)
- `idx_af_operate_date`: (`divid_operate_date DESC`)

## 典型查询

```sql
-- 查询单只股票的复权因子历史
SELECT symbol, divid_operate_date, fore_adjust_factor, back_adjust_factor, adjust_factor
FROM adjust_factor
WHERE source = 'baostock' AND symbol = '600000'
ORDER BY divid_operate_date DESC;

-- 查询某日期区间内的复权事件
SELECT *
FROM adjust_factor
WHERE divid_operate_date BETWEEN '2015-01-01' AND '2017-12-31'
ORDER BY symbol, divid_operate_date;
```


