# industry_base_info - 行业指数基本信息表

## 概述

`industry_base_info` 表存储行业指数的基本信息，包括指数代码、行业分类、级别等元数据。数据来源于 AmazingData 的"行业指数数据"类别。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL | 数据源标识（如: `amazing_data`） |
| index_code | VARCHAR(32) | NOT NULL | 指数代码 |
| industry_code | VARCHAR(32) | NOT NULL | 行业代码 |
| level_type | INT | NOT NULL | 指数类别（1:一级行业, 2:二级行业, 3:三级行业） |
| level1_name | VARCHAR(128) | NOT NULL DEFAULT '' | 一级行业名称 |
| level2_name | VARCHAR(128) | NOT NULL DEFAULT '' | 二级行业名称 |
| level3_name | VARCHAR(128) | NOT NULL DEFAULT '' | 三级行业名称 |
| is_pub | INT | NOT NULL | 是否发布（1:已发布, 2:未发布） |
| change_reason | VARCHAR(512) | NOT NULL DEFAULT '' | 变动原因 |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

## 唯一索引

- `uk_industry_base`: (source, index_code)

## B-tree 索引

- `idx_industry_code`: (industry_code)
- `idx_level_type`: (level_type)

## 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_base_info()`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.1 行业指数基本信息

## 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| INDEX_CODE | string | 指数代码 | - |
| INDUSTRY_CODE | string | 行业代码 | - |
| LEVEL_TYPE | int | 指数类别 | 1：一级行业 2：二级行业 3：三级行业 |
| LEVEL1_NAME | string | 一级行业 | - |
| LEVEL2_NAME | string | 二级行业 | - |
| LEVEL3_NAME | string | 三级行业 | - |
| IS_PUB | int | 是否发布 | 1：已发布； 2：未发布 |
| CHANGE_REASON | string | 变动原因 | - |

## 示例数据

```json
{
  "INDEX_CODE": "801010",
  "INDUSTRY_CODE": "801010",
  "LEVEL_TYPE": 1,
  "LEVEL1_NAME": "农林牧渔",
  "LEVEL2_NAME": "",
  "LEVEL3_NAME": "",
  "IS_PUB": 1,
  "CHANGE_REASON": ""
}
```

## 查询示例

```sql
-- 查询所有一级行业指数
SELECT * FROM industry_base_info
WHERE level_type = 1 AND is_pub = 1
ORDER BY index_code;

-- 查询特定指数的详细信息
SELECT * FROM industry_base_info
WHERE index_code = '801010';
```

---

*文档最后更新: 2026-05-12*
