# industry_weight - 行业指数成分股日权重表

## 概述

`industry_weight` 表存储行业指数成分股的每日权重数据。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL | 数据源标识（如: `amazing_data`） |
| index_code | VARCHAR(32) | NOT NULL | 指数代码 |
| con_code | VARCHAR(32) | NOT NULL | 成份股代码 |
| trade_date | VARCHAR(10) | NOT NULL | 交易日期（YYYY-MM-DD 格式） |
| weight | FLOAT | NOT NULL DEFAULT 0 | 权重 |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

## 唯一索引

- `uk_industry_weight`: (source, index_code, con_code, trade_date)

## B-tree 索引

- `idx_ind_weight_index`: (index_code)
- `idx_ind_weight_code`: (con_code)
- `idx_ind_weight_date`: (trade_date)

## 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_weight(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.3 行业指数成分股日权重

## 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| WEIGHT | float | 权重 | - |
| CON_CODE | string | 成份股代码 | - |
| TRADE_DATE | string | 交易日期 | YYYY-MM-DD 格式 |
| INDEX_CODE | string | 指数代码 | - |

## 示例数据

```json
{
  "INDEX_CODE": "801010",
  "CON_CODE": "000001",
  "TRADE_DATE": "2024-06-15",
  "WEIGHT": 3.25
}
```

## 查询示例

```sql
-- 查询某日期的成分股权重
SELECT iw.con_code, iw.weight, iw.trade_date
FROM industry_weight iw
WHERE iw.index_code = '801010' AND iw.trade_date = '2024-06-15'
ORDER BY iw.weight DESC;
```

---

*文档最后更新: 2026-05-12*
