# industry_constituent - 行业指数成分股表

## 概述

`industry_constituent` 表存储行业指数的成分股信息，记录每个指数包含哪些股票以及纳入/剔除日期。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL | 数据源标识（如: `amazing_data`） |
| index_code | VARCHAR(32) | NOT NULL | 指数代码 |
| con_code | VARCHAR(32) | NOT NULL | 成份股代码 |
| in_date | VARCHAR(10) | NOT NULL DEFAULT '' | 纳入日期（YYYY-MM-DD 格式） |
| out_date | VARCHAR(10) | NOT NULL DEFAULT '' | 剔除日期（YYYY-MM-DD 格式），未剔除时为空 |
| index_name | VARCHAR(128) | NOT NULL DEFAULT '' | 指数名称 |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

## 唯一索引

- `uk_industry_constituent`: (source, index_code, con_code, in_date)

## B-tree 索引

- `idx_ind_const_index`: (index_code)
- `idx_ind_const_code`: (con_code)
- `idx_ind_const_in_date`: (in_date)

## 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_constituent(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.2 行业指数成分股

## 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| INDEX_CODE | string | 指数代码 | - |
| CON_CODE | string | 成份股代码 | 纯代码 |
| INDATE | string | 纳入日期 | YYYY-MM-DD 格式 |
| OUTDATE | string | 剔除日期 | YYYY-MM-DD 格式，未剔除时为空 |
| INDEX_NAME | string | 指数名称 | - |

## 示例数据

```json
{
  "INDEX_CODE": "801010",
  "CON_CODE": "000001",
  "INDATE": "2024-01-01",
  "OUTDATE": "",
  "INDEX_NAME": "申万农林牧渔"
}
```

## 查询示例

```sql
-- 查询某行业指数的最新成分股
SELECT ic.con_code, ic.in_date, ic.out_date, ibi.index_name
FROM industry_constituent ic
JOIN industry_base_info ibi ON ic.index_code = ibi.index_code
WHERE ic.index_code = '801010' AND (ic.out_date = '' OR ic.out_date IS NULL)
ORDER BY ic.in_date DESC;

-- 查询某股票所属的所有行业指数
SELECT ic.index_code, ic.in_date, ic.out_date, ibi.level1_name, ibi.level2_name
FROM industry_constituent ic
JOIN industry_base_info ibi ON ic.index_code = ibi.index_code
WHERE ic.con_code = '000001'
ORDER BY ic.index_code;
```

---

*文档最后更新: 2026-05-12*
