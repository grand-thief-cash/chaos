# corporate_action - 公司行为数据表

## 概述

`corporate_action` 表存储上市公司的各类公司行为事件，包括分红、配股等股东权益变更事件。数据来源于 AmazingData 和 Baostock。

## 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL, UNIQUE | 数据源标识（如: `amazing_data`, `baostock`） |
| symbol | VARCHAR(32) | NOT NULL, UNIQUE | 证券代码（纯代码，如 "000001"，不含交易所后缀） |
| market | VARCHAR(16) | NOT NULL, DEFAULT 'zh_a' | 市场标识（默认: zh_a，表示沪深A股） |
| action_type | VARCHAR(32) | NOT NULL, UNIQUE | 行为类型（见下方说明） |
| report_period | VARCHAR(10) | NOT NULL, DEFAULT '' | 报告期（YYYY-MM-DD 格式） |
| ann_date | VARCHAR(10) | NOT NULL, DEFAULT '' | 公告日期（YYYY-MM-DD 格式） |
| progress_code | VARCHAR(8) | NOT NULL, DEFAULT '' | 进度代码（见下方说明） |
| data_json | JSONB | NOT NULL | 存储行为详情数据的 JSON 字段 |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

## 唯一索引

- `uk_corp_action`: (source, symbol, market, action_type, report_period, ann_date)

## B-tree 索引

- `idx_ca_symbol_action`: (symbol, action_type)
- `idx_ca_report_period`: (report_period) WHERE report_period != ''
- `idx_ca_ann_date`: (ann_date) WHERE ann_date != ''

## GIN 索引

- `idx_ca_data_gin`: (data_json) - 支持高效的 JSONB 查询（@>, ?, ?| 操作符）

## action_type 行为类型

| 值 | 说明 | 数据来源 |
|----|------|----------|
| dividend | 分红数据 | AmazingData - get_dividend() |
| right_issue | 配股数据 | AmazingData - get_right_issue() |
| bs_dividend | Baostock 除权除息数据 | Baostock - query_dividend_data() |

---

## 1. dividend - 分红数据

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_dividend(code_list)`
- **数据类别**: 3.5.7 股东权益数据 → 3.5.7.1 分红数据

### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | AmazingData 原始字段，映射到表 symbol |
| DIV_PROGRESS | string | 方案进度 | 映射到表 progress_code，见进度代码表 |
| DVD_PER_SHARE_STK | float | 每股送转 | 送股数量（股） |
| DVD_PER_SHARE_PRE_TAX_CASH | float | 每股派息(税前)(元) | 税前现金分红 |
| DVD_PER_SHARE_AFTER_TAX_CASH | float | 每股派息(税后)(元) | 税后现金分红 |
| DATE_EQY_RECORD | string | 股权登记日 | YYYY-MM-DD 格式 |
| DATE_EX | string | 除权除息日 | YYYY-MM-DD 格式 |
| DATE_DVD_PAYOUT | string | 派息日 | YYYY-MM-DD 格式 |
| LISTINGDATE_OF_DVD_SHR | string | 红股上市日 | YYYY-MM-DD 格式 |
| DIV_PRELANDATE | string | 预案公告日 | 董事会预案公告日期，YYYY-MM-DD 格式 |
| DIV_SMTGDATE | string | 股东大会公告日 | YYYY-MM-DD 格式 |
| DATE_DVD_ANN | string | 分红实施公告日 | YYYY-MM-DD 格式 |
| DIV_BASEDATE | string | 基准日期 | YYYY-MM-DD 格式 |
| DIV_BASESHARE | float | 基准股本(万股) | 分红计算的基准股本数 |
| CURRENCY_CODE | string | 货币代码 | 如 "CNY" |
| ANN_DATE | string | 公告日期 | YYYY-MM-DD 格式，映射到表 ann_date |
| IS_CHANGED | int | 方案是否变更 | 1: 有变更过, 0: 未变更 |
| REPORT_PERIOD | string | 分红年度 | YYYY 格式，映射到表 report_period |
| DIV_CHANGE | string | 方案变更说明 | 变更的详细描述 |
| DIV_BONUSRATE | float | 每股送股比例 | 送股比例 |
| DIV_CONVERSEDRATE | float | 每股转增比例 | 资本公积转增股本比例 |
| REMARK | string | 备注 | 其他说明信息 |
| DIV_PREANN_DATE | string | 预案预披露公告日 | 股东提议的公告日期，YYYY-MM-DD 格式 |
| DIV_TARGET | string | 分红对象 | 如 "全体股东" |

### 分红进度代码 (DIV_PROGRESS)

| 进度代码 | 进度描述 | 说明 |
|----------|----------|------|
| 1 | 董事会预案 | 公司董事会提出分红方案 |
| 2 | 股东大会通过 | 股东大会审议通过 |
| 3 | 实施 | 分红方案正式实施 |
| 4 | 未通过 | 方案被股东大会否决 |
| 12 | 停止实施 | 方案停止执行 |
| 17 | 股东提议 | 股东提出分红建议 |
| 19 | 董事会预案预披露 | 方案预披露 |

**分红实施进程**: 股东提议 → 董事会预案 → 股东大会 → 实施

### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "DIV_PROGRESS": "3",
  "DVD_PER_SHARE_STK": 0.5,
  "DVD_PER_SHARE_PRE_TAX_CASH": 2.0,
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
  "DIV_CONVERSEDRATE": 0.0,
  "REMARK": "",
  "DIV_PREANN_DATE": "",
  "DIV_TARGET": "全体股东"
}
```

---

## 2. right_issue - 配股数据

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_right_issue(code_list)`
- **数据类别**: 3.5.7 股东权益数据 → 3.5.7.2 配股数据

### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | AmazingData 原始字段，映射到表 symbol |
| PROGRESS | int | 方案进度 | 映射到表 progress_code，见进度代码表 |
| PRICE | double | 配股价格(元) | 每股配股价格 |
| RATIO | double | 配股比例 | 如 10 配 3 则为 0.3 |
| AMT_PLAN | double | 配股计划数量(万股) | 计划配股数量 |
| AMT_REAL | double | 配股实际数量(万股) | 实际配股数量 |
| COLLECTION_FUND | double | 募集资金(元) | 实际募集金额 |
| SHAREB_REG_DATE | string | 股权登记日 | YYYY-MM-DD 格式 |
| EX_DIVIDEND_DATE | string | 除权日 | YYYY-MM-DD 格式 |
| LISTED_DATE | string | 配股上市日 | YYYY-MM-DD 格式 |
| PAY_START_DATE | string | 缴款起始日 | YYYY-MM-DD 格式 |
| PAY_END_DATE | string | 缴款终止日 | YYYY-MM-DD 格式 |
| PREPLAN_DATE | string | 预案公告日 | YYYY-MM-DD 格式 |
| SMTG_ANN_DATE | string | 股东大会公告日 | YYYY-MM-DD 格式 |
| PASS_DATE | string | 发审委通过公告日 | YYYY-MM-DD 格式 |
| APPROVED_DATE | string | 证监会核准公告日 | YYYY-MM-DD 格式 |
| EXECUTE_DATE | string | 配股实施公告日 | YYYY-MM-DD 格式 |
| RESULT_DATE | string | 配股结果公告日 | YYYY-MM-DD 格式 |
| LIST_ANN_DATE | string | 上市公告日 | YYYY-MM-DD 格式 |
| GUARANTOR | string | 基准年度 | 如 "2023" |
| GUARTYPE | double | 基准股本(万股) | 配股计算的基准股本 |
| RIGHTSISSUE_CODE | string | 配售代码 | 配股专用代码 |
| ANN_DATE | string | 公告日期 | YYYY-MM-DD 格式，映射到表 ann_date |
| RIGHTSISSUE_YEAR | string | 配股年度 | YYYY 格式，映射到表 report_period |
| RIGHTSISSUE_DESC | string | 配股说明 | 配股详细说明 |
| RIGHTSISSUE_NAME | string | 配股简称 | 如 "2023年度配股" |
| RATIO_DENOMINATOR | double | 配股比例分母 | 比例的分母部分 |
| RATIO_MOLECULAR | double | 配股比例分子 | 比例的分子部分 |
| SUBS_METHOD | string | 认购方式 | 如 "网上认购" |
| EXPECTED_FUND_RAISING | double | 预计募集资金(元) | 计划募集金额 |

### 配股进度代码 (PROGRESS)

| 进度代码 | 进度描述 | 说明 |
|----------|----------|------|
| 1 | 董事会预案 | 公司董事会提出配股方案 |
| 2 | 股东大会通过 | 股东大会审议通过 |
| 3 | 实施 | 配股方案正式实施 |
| 4 | 未通过 | 方案被股东大会否决 |
| 5 | 证监会核准 | 证监会审批通过 |
| 6 | 达成转让意向 | 相关方达成意向 |
| 7 | 签署转让协议 | 正式签署协议 |
| 8 | 国资委批准 | 国资部门审批通过 |
| 9 | 商务部批准 | 商务部审批通过 |
| 10 | 过户 | 股权过户完成 |
| 11 | 延期实施 | 方案延期执行 |
| 12 | 停止实施 | 方案停止执行 |
| 13 | 分红方案待定 | 方案待定 |
| 14 | 传闻 | 市场传闻信息 |
| 15 | 传闻被否认 | 官方否认传闻 |
| 16 | 股东提议 | 股东提出建议 |
| 17 | 保监会批复 | 保监会审批通过 |
| 18 | 董事会预案预披露 | 方案预披露 |
| 19 | 发审委通过 | 发审委审核通过 |
| 20 | 发审委未通过 | 发审委审核未通过 |
| 21 | 股东大会未通过 | 股东大会否决 |
| 22 | 银监会批准 | 银监会审批通过 |
| 23 | 证监会恢复审核 | 证监会恢复审核 |
| 24 | 预发行 | 预发行阶段 |
| 25 | 提交注册 | 提交注册申请 |
| 26 | (待补充) |  |

### 示例数据

```json
{
  "MARKET_CODE": "600000",
  "PROGRESS": 3,
  "PRICE": 5.88,
  "RATIO": 0.3,
  "AMT_PLAN": 150000.0,
  "AMT_REAL": 145000.0,
  "COLLECTION_FUND": 852600000.0,
  "SHAREB_REG_DATE": "2024-07-10",
  "EX_DIVIDEND_DATE": "2024-07-11",
  "LISTED_DATE": "2024-07-15",
  "PAY_START_DATE": "2024-07-11",
  "PAY_END_DATE": "2024-07-17",
  "PREPLAN_DATE": "2024-03-20",
  "SMTG_ANN_DATE": "2024-04-18",
  "PASS_DATE": "2024-05-25",
  "APPROVED_DATE": "2024-06-10",
  "EXECUTE_DATE": "2024-07-05",
  "RESULT_DATE": "2024-07-20",
  "LIST_ANN_DATE": "2024-07-14",
  "GUARANTOR": "2023",
  "GUARTYPE": 500000.0,
  "RIGHTSISSUE_CODE": "700123",
  "ANN_DATE": "2024-07-05",
  "RIGHTSISSUE_YEAR": "2023",
  "RIGHTSISSUE_DESC": "公司拟向全体股东每10股配售3股",
  "RIGHTSISSUE_NAME": "2023年度配股",
  "RATIO_DENOMINATOR": 10.0,
  "RATIO_MOLECULAR": 3.0,
  "SUBS_METHOD": "网上认购",
  "EXPECTED_FUND_RAISING": 900000000.0
}
```

---

## 3. bs_dividend - Baostock 除权除息数据

### 数据来源

- **数据源**: Baostock
- **接口函数**: `bs.query_dividend_data(code, year, yearType)`
- **说明**: Baostock 提供的历史除权除息数据，包含税前税后分红、送股、转增等信息

### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 | 算法说明 |
|--------|------|------|------|----------|
| dividCashPsBeforeTax | float | 每股股利税前 | 税前分红金额（元） | 派息比例分子(税前)/派息比例分母 |
| dividCashPsAfterTax | float | 每股股利税后 | 税后分红金额（元） | 派息比例分子(税后)/派息比例分母 |
| dividStocksPs | float | 每股红股 | 送股数量（股） | - |
| dividCashStock | float | 分红送转 | 每股派息数(税前)+每股送股数+每股转增股本数（元） | - |
| dividReserveToStockPs | float | 每股转增股本数 | 公积金转增数量（股） | - |
| dividEarningsPs | float | 每股送红股数 | 盈余公积转增数量（股） | - |
| dividCashRatio | float | 现金分红比例(%) | 分红比例 | - |
| recordDate | string | 股权登记日 | YYYY-MM-DD 格式 | - |
| exDividendDate | string | 除权除息日 | YYYY-MM-DD 格式 | - |
| payDate | string | 派息日 | YYYY-MM-DD 格式 | - |
| listingDate | string | 红股上市日 | YYYY-MM-DD 格式 | - |

### 示例数据

```json
{
  "dividCashPsBeforeTax": 2.5,
  "dividCashPsAfterTax": 2.0,
  "dividStocksPs": 0.3,
  "dividReserveToStockPs": 0.2,
  "dividEarningsPs": 0.0,
  "dividCashRatio": 30.5,
  "recordDate": "2024-06-15",
  "exDividendDate": "2024-06-16",
  "payDate": "2024-06-21",
  "listingDate": "2024-06-16"
}
```

---

## 查询示例

### 基础查询

```sql
-- 查询某股票的所有分红记录
SELECT * FROM corporate_action
WHERE symbol = '000001' AND action_type = 'dividend'
ORDER BY ann_date DESC;

-- 查询某年度的所有分红记录
SELECT * FROM corporate_action
WHERE action_type = 'dividend' AND report_period = '2023'
ORDER BY ann_date DESC;
```

### JSONB 字段查询

```sql
-- 查询每股派息大于1元的分红记录
SELECT * FROM corporate_action
WHERE action_type = 'dividend'
  AND (data_json->>'DVD_PER_SHARE_PRE_TAX_CASH')::float > 1.0;

-- 查询包含特定JSON字段的记录
SELECT * FROM corporate_action
WHERE action_type = 'dividend'
  AND data_json ? 'DVD_BONUSRATE';

-- 使用包含查询
SELECT * FROM corporate_action
WHERE action_type = 'dividend'
  AND data_json @> '{"DIV_PROGRESS": "3"}';

-- 查询进度为"实施"的分红记录
SELECT symbol, report_period,
       data_json->>'DVD_PER_SHARE_PRE_TAX_CASH' as dividend_per_share,
       data_json->>'DATE_DVD_PAYOUT' as payout_date
FROM corporate_action
WHERE action_type = 'dividend'
  AND progress_code = '3'
ORDER BY ann_date DESC;
```

### 组合查询

```sql
-- 查询最近一年实施的分红和配股
SELECT
    symbol,
    action_type,
    report_period,
    ann_date,
    CASE
        WHEN action_type = 'dividend' THEN data_json->>'DVD_PER_SHARE_PRE_TAX_CASH'
        WHEN action_type = 'right_issue' THEN data_json->>'PRICE'
    END as amount
FROM corporate_action
WHERE (action_type = 'dividend' OR action_type = 'right_issue')
  AND progress_code = '3'
  AND ann_date >= '2023-01-01'
ORDER BY symbol, ann_date DESC;
```

---

## 数据更新机制

- **数据源**: Artemis 下载任务
- **更新频率**: 根据各数据源特性配置（通常为每日/每周）
- **去重机制**: 基于 (source, symbol, market, action_type, report_period, ann_date) 唯一键
- **版本控制**: updated_at 字段记录最后更新时间

---

*文档最后更新: 2026-05-12*
