# Long Hu Bang API - 龙虎榜数据

> Phase 3: identity is `security_id`; `symbol`/`market` removed.

## 概述

提供 A 股龙虎榜营业部明细查询。该数据来自 AmazingData `InfoData.get_long_hu_bang()`，记录证券在指定交易日、指定上榜原因下的营业部买入/卖出明细，可用于跟踪异常交易、热门席位和市场情绪。

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v2/long-hu-bang/{source}` | 查询龙虎榜明细 |

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| source | string | 数据源，目前为 `amazing_data` |

## 查询参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| security_id | integer | 否 | 单个证券 ID（`security_registry.id`） |
| security_ids | string | 否 | 多个证券 ID，逗号分隔 |
| trade_date | string | 否 | 精确交易日期，格式 `YYYY-MM-DD` |
| start_date | string | 否 | 起始交易日期，格式 `YYYY-MM-DD` |
| end_date | string | 否 | 截止交易日期，格式 `YYYY-MM-DD` |
| reason_type | string | 否 | 上榜原因类型代码 |
| trader_name | string | 否 | 营业部名称 |
| flow_mark | integer | 否 | 买卖方向：`1` 买入，`2` 卖出 |
| fields | string | 否 | 返回字段列表，逗号分隔 |
| page | integer | 否 | 页码，默认 `1` |
| page_size | integer | 否 | 每页条数，默认 `100` |

## 响应格式

```json
{
  "data": [...],
  "total": 1
}
```

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| data | array | 龙虎榜对象数组 |
| total | integer | 总记录数 |

## 响应数据

### 龙虎榜对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| source | string | 数据来源 |
| security_id | integer | 证券 ID（`security_registry.id`） |
| trade_date | string | 交易日期，格式 `YYYY-MM-DD` |
| security_name | string | 证券名称 |
| reason_type | string | 上榜原因类型代码 |
| reason_type_name | string | 上榜原因名称 |
| trader_name | string | 营业部名称 |
| flow_mark | integer | 买卖方向：`1` 买入，`2` 卖出 |
| change_range | number | 涨跌幅（%） |
| buy_amount | number | 买入金额（元） |
| sell_amount | number | 卖出金额（元） |
| total_amount | number | 实际交易金额（元） |
| total_volume | number | 实际交易量（万股） |

## 响应示例

**请求**: `GET /api/v2/long-hu-bang/amazing_data?security_id=1&start_date=2026-05-01&end_date=2026-05-31`

```json
{
  "data": [
    {
      "source": "amazing_data",
      "security_id": 1,
      "trade_date": "2026-05-27",
      "security_name": "平安银行",
      "reason_type": "1001",
      "reason_type_name": "日涨幅偏离值达7%",
      "trader_name": "国泰君安证券上海分公司",
      "flow_mark": 1,
      "change_range": 9.98,
      "buy_amount": 123456789.12,
      "sell_amount": 98765432.10,
      "total_amount": 24680246.80,
      "total_volume": 321.50
    }
  ],
  "total": 1
}
```


