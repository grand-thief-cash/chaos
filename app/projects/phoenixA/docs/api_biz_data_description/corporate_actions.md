# Corporate Actions API - 公司行为数据

## 概述

提供上市公司各类公司行为事件数据查询，包括分红、配股等股东权益变更事件。

## API 端点

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/corporate-action/{source}/{action_type}` | 查询公司行为数据 |

## 查询参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| symbol | string | 否 | 证券代码 |
| symbols | string | 否 | 证券代码列表（逗号分隔） |
| start_date | string | 否 | 起始公告日期（格式 YYYY-MM-DD） |
| end_date | string | 否 | 截止公告日期（格式 YYYY-MM-DD） |
| report_period | string | 否 | 按报告期过滤 |
| progress_code | string | 否 | 按进度代码过滤 |
| **fields** | **string** | **否** | **返回字段列表（逗号分隔），支持常规字段和 JSONB 嵌套字段（见下文说明）** |
| limit | integer | 否 | 返回数量限制 |
| offset | integer | 否 | 分页偏移量 |

### fields 参数说明

`fields` 参数允许指定返回的字段，减少数据传输量。

**格式**: `fields=字段1,字段2,字段3`

**支持的字段类型**:
1. **常规字段**: 直接使用表字段名，如 `symbol`, `report_period`, `ann_date`
2. **JSONB 嵌套字段**: 使用 `data_json.字段名` 格式，如 `data_json.DVD_PER_SHARE_PRE_TAX_CASH`, `data_json.DATE_EQY_RECORD`

**示例**:
- `fields=symbol,report_period,ann_date` - 只返回基本字段
- `fields=symbol,data_json.DVD_PER_SHARE_PRE_TAX_CASH,data_json.DATE_EQY_RECORD` - 返回分红特定字段
- `fields=data_json.PRICE,data_json.RATIO,data_json.COLLECTION_FUND` - 返回配股特定字段

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| source | string | 数据源（amazing_data, baostock 等） |
| action_type | string | 行为类型（dividend, right_issue, bs_dividend 等） |

## action_type 说明

| 值 | 说明 |
|----|------|
| dividend | 分红数据 |
| right_issue | 配股数据 |
| bs_dividend | Baostock 除权除息数据 |

## 响应格式

```json
{
  "data": [...],
  "total": 500
}
```

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| data | array | 公司行为对象数组 |
| total | integer | 总记录数 |

## 响应数据

### 公司行为对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| source | string | 数据源 |
| symbol | string | 证券代码（纯代码） |
| market | string | 市场标识（默认 zh_a） |
| action_type | string | 行为类型 |
| report_period | string | 报告期（格式 YYYY-MM-DD） |
| ann_date | string | 公告日期（格式 YYYY-MM-DD） |
| progress_code | string | 进度代码 |
| data_json | object | 行为详情数据（内容随 action_type 而不同） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

## data_json 字段说明

### dividend（分红数据）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| DIV_PROGRESS | string | 方案进度 |
| DVD_PER_SHARE_STK | float64 | 每股送转（送股数量，股/股） |
| DVD_PER_SHARE_PRE_TAX_CASH | float64 | 每股派息(税前)(元/股) |
| DVD_PER_SHARE_AFTER_TAX_CASH | float64 | 每股派息(税后)(元/股) |
| DATE_EQY_RECORD | string | 股权登记日（格式 YYYY-MM-DD） |
| DATE_EX | string | 除权除息日（格式 YYYY-MM-DD） |
| DATE_DVD_PAYOUT | string | 派息日（格式 YYYY-MM-DD） |
| LISTINGDATE_OF_DVD_SHR | string | 红股上市日（格式 YYYY-MM-DD） |
| DIV_PRELANDATE | string | 预案公告日（格式 YYYY-MM-DD） |
| DIV_SMTGDATE | string | 股东大会公告日（格式 YYYY-MM-DD） |
| DATE_DVD_ANN | string | 分红实施公告日（格式 YYYY-MM-DD） |
| DIV_BASEDATE | string | 基准日期（格式 YYYY-MM-DD） |
| DIV_BASESHARE | float64 | 基准股本(万股) |
| CURRENCY_CODE | string | 货币代码 |
| ANN_DATE | string | 公告日期（格式 YYYY-MM-DD） |
| IS_CHANGED | integer | 方案是否变更（0:未变更 1:有变更） |
| REPORT_PERIOD | string | 分红年度（格式 YYYY） |
| DIV_CHANGE | string | 方案变更说明 |
| DIV_BONUSRATE | float64 | 每股送股比例 |
| DIV_CONVERSEDRATE | float64 | 每股转增比例 |
| REMARK | string | 备注 |
| DIV_PREANN_DATE | string | 预案预披露公告日（格式 YYYY-MM-DD） |
| DIV_TARGET | string | 分红对象 |

### right_issue（配股数据）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| PROGRESS | integer | 方案进度 |
| PRICE | float64 | 配股价格(元/股) |
| RATIO | float64 | 配股比例 |
| AMT_PLAN | float64 | 配股计划数量(万股) |
| AMT_REAL | float64 | 配股实际数量(万股) |
| COLLECTION_FUND | float64 | 募集资金(元) |
| SHAREB_REG_DATE | string | 股权登记日（格式 YYYY-MM-DD） |
| EX_DIVIDEND_DATE | string | 除权日（格式 YYYY-MM-DD） |
| LISTED_DATE | string | 配股上市日（格式 YYYY-MM-DD） |
| PAY_START_DATE | string | 缴款起始日（格式 YYYY-MM-DD） |
| PAY_END_DATE | string | 缴款终止日（格式 YYYY-MM-DD） |
| PREPLAN_DATE | string | 预案公告日（格式 YYYY-MM-DD） |
| SMTG_ANN_DATE | string | 股东大会公告日（格式 YYYY-MM-DD） |
| PASS_DATE | string | 发审委通过公告日（格式 YYYY-MM-DD） |
| APPROVED_DATE | string | 证监会核准公告日（格式 YYYY-MM-DD） |
| EXECUTE_DATE | string | 配股实施公告日（格式 YYYY-MM-DD） |
| RESULT_DATE | string | 配股结果公告日（格式 YYYY-MM-DD） |
| LIST_ANN_DATE | string | 上市公告日（格式 YYYY-MM-DD） |
| GUARANTOR | string | 基准年度（如 "2023"） |
| GUARTYPE | float64 | 基准股本(万股) |
| RIGHTSISSUE_CODE | string | 配售代码 |
| ANN_DATE | string | 公告日期（格式 YYYY-MM-DD） |
| RIGHTSISSUE_YEAR | string | 配股年度（格式 YYYY） |
| RIGHTSISSUE_DESC | string | 配股说明 |
| RIGHTSISSUE_NAME | string | 配股简称 |
| RATIO_DENOMINATOR | float64 | 配股比例分母 |
| RATIO_MOLECULAR | float64 | 配股比例分子 |
| SUBS_METHOD | string | 认购方式 |
| EXPECTED_FUND_RAISING | float64 | 预计募集资金(元) |

### bs_dividend（Baostock 除权除息数据）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| dividCashPsBeforeTax | float64 | 每股股利税前（元/股） |
| dividCashPsAfterTax | float64 | 每股股利税后（元/股） |
| dividStocksPs | float64 | 每股红股（送股数量，股/股） |
| dividCashStock | float64 | 分红送转（每股派息数(税前)+每股送股数+每股转增股本数，元/股） |
| dividReserveToStockPs | float64 | 每股转增股本数（公积金转增数量，股/股） |
| dividEarningsPs | float64 | 每股送红股数（盈余公积转增数量，股/股） |
| dividCashRatio | float64 | 现金分红比例(%) |
| recordDate | string | 股权登记日（格式 YYYY-MM-DD） |
| exDividendDate | string | 除权除息日（格式 YYYY-MM-DD） |
| payDate | string | 派息日（格式 YYYY-MM-DD） |
| listingDate | string | 红股上市日（格式 YYYY-MM-DD） |

## 响应示例

### 查询分红数据

**请求**: `GET /api/v2/corporate-action/amazing_data/dividend?symbol=000001&page=1&page_size=10`

```json
[
  {
    "id": 100001,
    "source": "amazing_data",
    "symbol": "000001",
    "market": "zh_a",
    "action_type": "dividend",
    "report_period": "2023",
    "ann_date": "2024-06-11",
    "progress_code": "3",
    "data_json": {
      "MARKET_CODE": "000001",
      "DIV_PROGRESS": "3",
      "DVD_PER_SHARE_STK": 0.5,
      "DVD_PER_SHARE_PRE_TAX_CASH": 2,
      "DVD_PER_SHARE_AFTER_TAX_CASH": 1.6,
      "DATE_EQY_RECORD": "2024-06-15",
      "DATE_EX": "2024-06-16",
      "DATE_DVD_PAYOUT": "2024-06-21",
      "LISTINGDATE_OF_DVD_SHR": "2024-06-16",
      "DIV_PRELANDATE": "2024-03-28",
      "DIV_SMTGDATE": "2024-04-25",
      "DATE_DVD_ANN": "2024-06-11",
      "DIV_BASEDATE": "2024-03-31",
      "DIV_BASESHARE": 1940822.18,
      "CURRENCY_CODE": "CNY",
      "ANN_DATE": "2024-06-11",
      "IS_CHANGED": 0,
      "REPORT_PERIOD": "2023",
      "DIV_CHANGE": "",
      "DIV_BONUSRATE": 0.5,
      "DIV_CONVERSEDRATE": 0,
      "REMARK": "",
      "DIV_PREANN_DATE": "",
      "DIV_TARGET": "全体股东"
    },
    "created_at": "2024-06-12T00:00:00Z",
    "updated_at": "2024-06-12T00:00:00Z"
  }
]
```

### 查询分红数据（使用 fields 参数过滤字段）

**请求**: `GET /api/v2/corporate-action/amazing_data/dividend?symbol=000001&fields=ann_date,report_period,data_json.DVD_PER_SHARE_PRE_TAX_CASH,data_json.DATE_EQY_RECORD,data_json.DATE_EX`

```json
[
  {
    "ann_date": "2024-06-11",
    "report_period": "2023",
    "data_json->'DVD_PER_SHARE_PRE_TAX_CASH'": "data_json.DVD_PER_SHARE_PRE_TAX_CASH",
    "data_json->'DATE_EQY_RECORD'": "data_json.DATE_EQY_RECORD",
    "data_json->'DATE_EX'": "data_json.DATE_EX"
  }
]
```

---

*文档最后更新: 2026-05-13*
