# Adjust Factors API - 复权因子数据

## 概述

提供 A 股复权因子数据查询。该数据来自 Baostock `query_adjust_factor()`，记录每次除权除息事件对应的前复权因子、后复权因子和本次复权因子，可用于基于本地不复权日线重建复权行情。

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v2/adjust-factors/{source}` | 查询复权因子数据 |

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| source | string | 数据源，目前为 `baostock` |

## 查询参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| symbol | string | 否 | 单个证券代码（纯代码，如 `600000`） |
| symbols | string | 否 | 多个证券代码，逗号分隔 |
| market | string | 否 | 市场标识，默认常用为 `zh_a` |
| start_date | string | 否 | 起始除权除息日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 截止除权除息日期，格式 `YYYY-MM-DD` |
| fields | string | 否 | 返回字段列表，逗号分隔 |
| page | integer | 否 | 页码，默认 `1` |
| page_size | integer | 否 | 每页条数，默认 `100` |

## 响应格式

```json
{
  "data": [...],
  "total": 3
}
```

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| data | array | 复权因子对象数组 |
| total | integer | 总记录数 |

## 响应数据

### 复权因子对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| source | string | 数据来源 |
| symbol | string | 证券代码（纯代码） |
| market | string | 市场标识 |
| divid_operate_date | string | 除权除息日期，格式 `YYYY-MM-DD` |
| fore_adjust_factor | number | 向前复权因子 |
| back_adjust_factor | number | 向后复权因子 |
| adjust_factor | number | 本次复权因子 |

## 响应示例

**请求**: `GET /api/v2/adjust-factors/baostock?symbol=600000&start_date=2015-01-01&end_date=2017-12-31`

```json
{
  "data": [
    {
      "id": 1,
      "source": "baostock",
      "symbol": "600000",
      "market": "zh_a",
      "divid_operate_date": "2015-06-23",
      "fore_adjust_factor": 0.663792,
      "back_adjust_factor": 6.295967,
      "adjust_factor": 6.295967
    },
    {
      "id": 2,
      "source": "baostock",
      "symbol": "600000",
      "market": "zh_a",
      "divid_operate_date": "2016-06-23",
      "fore_adjust_factor": 0.751598,
      "back_adjust_factor": 7.128788,
      "adjust_factor": 7.128788
    }
  ],
  "total": 2
}
```