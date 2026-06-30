# PhoenixA 数据表参考文档

本文档详细描述 PhoenixA 中存储的数据表结构、字段含义及数据来源。

---

## adjust_factor - 复权因子数据表

### 概述

`adjust_factor` 表存储证券在每次除权除息事件上的复权因子数据。该表独立于 `corporate_action`，定位为行情复权支撑数据，用于基于本地不复权日线重建前复权和后复权价格序列。

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL, UNIQUE | 数据源标识（如 `baostock`） |
| symbol | VARCHAR(32) | NOT NULL, UNIQUE | 证券代码（纯代码） |
| market | VARCHAR(16) | NOT NULL, DEFAULT 'zh_a', UNIQUE | 市场标识 |
| divid_operate_date | VARCHAR(10) | NOT NULL, UNIQUE | 除权除息日期（YYYY-MM-DD） |
| fore_adjust_factor | NUMERIC(20,8) | NULL | 向前复权因子 |
| back_adjust_factor | NUMERIC(20,8) | NULL | 向后复权因子 |
| adjust_factor | NUMERIC(20,8) | NULL | 本次复权因子 |

### 唯一索引

- `uk_adjust_factor`: (source, symbol, market, divid_operate_date)

### B-tree 索引

- `idx_af_symbol_date`: (symbol, market, divid_operate_date DESC)
- `idx_af_operate_date`: (divid_operate_date DESC)

### 数据说明

- **数据源**: Baostock
- **接口函数**: `bs.query_adjust_factor(code, start_date, end_date)`
- **关键字段**:
  - `fore_adjust_factor`: 向前复权因子
  - `back_adjust_factor`: 向后复权因子
  - `adjust_factor`: 本次复权因子
  - `divid_operate_date`: 除权除息日期

### 示例数据

```json
{
  "source": "baostock",
  "symbol": "600000",
  "market": "zh_a",
  "divid_operate_date": "2017-05-25",
  "fore_adjust_factor": 0.989551,
  "back_adjust_factor": 9.385732,
  "adjust_factor": 9.385732
}
```

---

## corporate_action - 公司行为数据表

### 概述

`corporate_action` 表存储上市公司的各类公司行为事件，包括分红、配股等股东权益变更事件。数据来源于 AmazingData 的"股东权益数据"类别。

### 表结构

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

### 唯一索引

- `uk_corp_action`: (source, symbol, market, action_type, report_period, ann_date)

### B-tree 索引

- `idx_ca_symbol_action`: (symbol, action_type)
- `idx_ca_report_period`: (report_period) WHERE report_period != ''
- `idx_ca_ann_date`: (ann_date) WHERE ann_date != ''

### GIN 索引

- `idx_ca_data_gin`: (data_json) - 支持高效的 JSONB 查询（@>, ?, ?| 操作符）

### action_type 行为类型

| 值 | 说明 | 数据来源 |
|----|------|----------|
| dividend | 分红数据 | AmazingData - get_dividend() |
| right_issue | 配股数据 | AmazingData - get_right_issue() |
| bs_dividend | Baostock 除权除息数据 | Baostock - query_dividend_data() |

---

## 数据类型详情

### 1. dividend - 分红数据

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_dividend(code_list)`
- **数据类别**: 3.5.7 股东权益数据 → 3.5.7.1 分红数据

#### data_json 字段结构

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

#### 分红进度代码 (DIV_PROGRESS)

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

#### 示例数据

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

### 2. right_issue - 配股数据

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_right_issue(code_list)`
- **数据类别**: 3.5.7 股东权益数据 → 3.5.7.2 配股数据

#### data_json 字段结构

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

#### 配股进度代码 (PROGRESS)

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

#### 示例数据

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

### 3. bs_dividend - Baostock 除权除息数据

#### 数据来源

- **数据源**: Baostock
- **接口函数**: `bs.query_dividend_data(code, year, yearType)`
- **说明**: Baostock 提供的历史除权除息数据，包含税前税后分红、送股、转增等信息

#### data_json 字段结构

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

#### 示例数据

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

## financial_statement - 财务报表数据表

### 概述

`financial_statement` 表存储上市公司的各类财务报表数据，包括资产负债表、利润表、现金流量表、业绩快报和业绩预告。数据来源于 AmazingData 的"财务数据"类别。

### 表结构

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PRIMARY KEY | 自增主键 |
| source | VARCHAR(32) | NOT NULL | 数据源标识（如: `amazing_data`） |
| symbol | VARCHAR(32) | NOT NULL | 证券代码（纯代码，如 "000001"，不含交易所后缀） |
| market | VARCHAR(16) | NOT NULL, DEFAULT 'zh_a' | 市场标识（默认: zh_a，表示沪深A股） |
| statement_type | VARCHAR(32) | NOT NULL | 报表类型（见下方说明） |
| reporting_period | VARCHAR(10) | NOT NULL | 报告期（YYYY-MM-DD 格式） |
| report_type | VARCHAR(32) | NOT NULL, DEFAULT '' | 报告期名称（如：年报、半年报、季报） |
| statement_code | VARCHAR(32) | NOT NULL, DEFAULT '' | 报表类型代码（见报表类型代码表） |
| security_name | VARCHAR(128) | NOT NULL, DEFAULT '' | 证券简称 |
| ann_date | VARCHAR(10) | NOT NULL, DEFAULT '' | 公告日期（YYYY-MM-DD 格式） |
| actual_ann_date | VARCHAR(10) | NOT NULL, DEFAULT '' | 实际公告日期（YYYY-MM-DD 格式） |
| comp_type_code | SMALLINT | NOT NULL, DEFAULT 0 | 公司类型代码（见下方说明） |
| data_json | JSONB | NOT NULL | 存储财务报表详情数据的 JSON 字段 |
| created_at | TIMESTAMPTZ | NOT NULL | 记录创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 记录更新时间 |

### 唯一索引

- `uk_fin_stmt`: (source, symbol, market, statement_type, reporting_period, report_type, statement_code)

### B-tree 索引

- `idx_fs_symbol_type`: (symbol, statement_type)
- `idx_fs_report_period`: (reporting_period)
- `idx_fs_ann_date`: (ann_date) WHERE ann_date != ''
- `idx_fs_comp_type`: (comp_type_code) WHERE comp_type_code > 0

### GIN 索引

- `idx_fs_data_gin`: (data_json) - 支持高效的 JSONB 查询（@>, ?, ?| 操作符）

### statement_type 报表类型

| 值 | 说明 | 数据来源 |
|----|------|----------|
| balance_sheet | 资产负债表 | AmazingData - get_balance_sheet() |
| income | 利润表 | AmazingData - get_income() |
| cashflow | 现金流量表 | AmazingData - get_cash_flow() |
| profit_express | 业绩快报 | AmazingData - get_profit_express() |
| profit_notice | 业绩预告 | AmazingData - get_profit_notice() |

### comp_type_code 公司类型代码

| 值 | 说明 |
|----|------|
| 1 | 非金融类 |
| 2 | 银行 |
| 3 | 保险 |
| 4 | 证券 |

---

## 数据类型详情

### 1. balance_sheet - 资产负债表

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_balance_sheet(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.1 资产负债表

#### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | 映射到表 symbol |
| SECURITY_NAME | string | 证券简称 | 映射到表 security_name |
| STATEMENT_TYPE | string | 报表类型 | 参看报表类型代码表，映射到表 statement_code |
| REPORT_TYPE | string | 报告期名称 | 参看报告期名称，映射到表 report_type |
| REPORTING_PERIOD | string | 报告期 | YYYY-MM-DD 格式，映射到表 reporting_period |
| ANN_DATE | string | 公告日期 | YYYY-MM-DD 格式，映射到表 ann_date |
| ACTUAL_ANN_DATE | string | 实际公告日期 | YYYY-MM-DD 格式，映射到表 actual_ann_date |
| ACC_PAYABLE | float | 应付票据及应付账款 | - |
| ACC_RECEIVABLE | float | 应收票据及应收账款 | - |
| ACC_RECEIVABLES | float | 应收款项 | - |
| ACCRUED_EXP | float | 预提费用 | - |
| ACCT_PAYABLE | float | 应付账款 | - |
| ACCT_RECEIVABLE | float | 应收账款 | - |
| ACT_TRADING_SEC | float | 代理买卖证券款 | - |
| ACT_UW_SEC | float | 代理承销证券款 | - |
| ADV_PREM | float | 预收保费 | - |
| ADV_RECEIPT | float | 预收款项 | - |
| AGENCY_ASSETS | float | 代理业务资产 | - |
| AGENCY_BUSINESS_LIAB | float | 代理业务负债 | - |
| ANTICIPATION_LIAB | float | 预计负债 | - |
| ASSET_DEP_FUNDS_OTHER_FIN_INST | float | 存放同业和其它金融机构款项 | - |
| BONDS_PAYABLE | float | 应付债券 | - |
| CAP_RESV | float | 资本公积金 | - |
| CAP_STOCK | float | 股本 | 金额（元），公布值 |
| CASH_CENTRAL_BANK_DEPOSITS | float | 现金及存放中央银行款项 | - |
| CED_INSUR_CONT_RESERVES_RCV | float | 应收分保合同准备金 | - |
| CLAIMS_PAYABLE | float | 应付赔付款 | - |
| CLIENTS_FUND_DEPOSIT | float | 客户资金存款 | - |
| CLIENTS_RESERVES | float | 客户备付金 | - |
| CNVD_DIFF_FOREIGN_CURR_STAT | float | 外币报表折算差额 | - |
| COMP_TYPE_CODE | int | 公司类型代码 | 1:非金融类 2:银行 3:保险 4:证券，映射到表 comp_type_code |
| CONST_IN_PROC | float | 在建工程 | - |
| CONST_IN_PROC_TOTAL | float | 在建工程(合计)(元) | - |
| CONSUMP_BIO_ASSETS | float | 消耗性生物资产 | - |
| CONT_ASSETS | float | 合同资产 | 单位（元） |
| CONT_LIABILITIES | float | 合同负债 | 单位（元） |
| CURRENCY_CAP | float | 货币资金 | - |
| CURRENCY_CODE | float | 货币代码 | - |
| DEBT_INV | float | 债权投资(元) | - |
| DEFERRED_INC_NONCUR_LIAB | float | 递延收益-非流动负债 | - |
| DEFERRED_INCOME | float | 递延收益 | - |
| DEFERRED_TAX_ASSETS | float | 递延所得税资产 | - |
| DEFERRED_TAX_LIAB | float | 递延所得税负债 | - |
| DEP_RECEIVED_IB_DEP | float | 吸收存款及同业存放 | - |
| DEPOSIT_CAP_RECOG | float | 存出资本保证金 | - |
| DEPOSIT_TAKING | float | 吸收存款 | - |
| DEPOSITS_RECEIVED | float | 存入保证金 | - |
| DER_FIN_ASSETS | float | 衍生金融资产 | - |
| DERI_FIN_LIAB | float | 衍生金融负债 | - |
| DEVELOP_EXP | float | 开发支出 | - |
| DISPOSAL_FIX_ASSET | float | 固定资产清理 | - |
| DIV_PAYABLE | float | 应付股利 | - |
| DIV_RECEIVABLE | float | 应收股利 | - |
| EMPL_PAY_PAYABLE | float | 应付职工薪酬 | - |
| ENGIN_MAT | float | 工程物资 | - |
| FIN_ASSETS_AVA_FOR_SALE | float | 可供出售金融资产 | - |
| FIN_ASSETS_COST_SHARING | float | 以摊余成本计量的金融资产 | - |
| FIN_ASSETS_FAIR_VALUE | float | 以公允价值计量且其变动计入其他综合收益的金融资产 | - |
| FIXED_ASSETS | float | 固定资产 | - |
| FIXED_ASSETS_TOTAL | float | 固定资产(合计)(元) | - |
| FIXED_TERM_DEPOSIT | float | 定期存款 | - |
| GOODWILL | float | 商誉 | - |
| GUA_DEPOSITS_PAID | float | 存出保证金 | - |
| GUA_PLEDGE_LOANS | float | 保户质押贷款 | - |
| HOLD_ASSETS_FOR_SALE | float | 持有待售的资产 | - |
| HOLD_TO_MTY_INV | float | 持有至到期投资 | - |
| INC_PLEDGE_LOAN | float | 其中:质押借款 | - |
| INCL_TRADING_SEAT_FEES | float | 其中:交易席位费 | - |
| IND_ACCT_ASSETS | float | 独立账户资产 | - |
| IND_ACCT_LIAB | float | 独立账户负债 | - |
| INSURED_DEPOSIT_IN | float | 保户储金及投资款 | - |
| INSURED_DIV_PAYABLE | float | 应付保单红利 | - |
| INT_RECEIVABLE | float | 应收利息 | - |
| INTANGIBLE_ASSETS | float | 无形资产 | - |
| INTEREST_PAYABLE | float | 应付利息 | - |
| INV | float | 存货 | - |
| INV_REALESTATE | float | 投资性房地产 | - |
| LEASE_LIABILITY | float | 租赁负债 | - |
| LEND_FUNDS | float | 融出资金 | - |
| LENDING_FUNDS | float | 拆出资金 | - |
| LESS_TREASURY_STK | float | 减:库存股 | - |
| LIA_HFS | float | 持有待售的负债 | - |
| LIAB_DEP_FUNDS_OTHER_FIN_INST | float | 同业和其它金融机构存放款项 | - |
| LIFE_INSUR_RESV | float | 寿险责任准备金 | - |
| LOAN_CENTRAL_BANK | float | 向中央银行借款 | - |
| LOANS_AND_ADVANCES | float | 发放贷款及垫款 | - |
| LOANS_FROM_OTHER_BANKS | float | 拆入资金 | - |
| LT_DEFERRED_EXP | float | 长期待摊费用 | - |
| LT_EMP_COMP_PAY | float | 长期应付职工薪酬 | - |
| LT_EQUITY_INV | float | 长期股权投资 | - |
| LT_HEALTH_INSUR_RESV | float | 长期健康险责任准备金 | - |
| LT_LOAN | float | 长期借款 | - |
| LT_PAYABLE | float | 长期应付款 | - |
| LT_PAYABLE_TOTAL | float | 长期应付款(合计)(元) | - |
| LT_RECEIVABLES | float | 长期应收款 | - |
| MINORITY_EQUITY | float | 少数股东权益 | - |
| NOM_RISKS_PREP | float | 一般风险准备 | - |
| NONCUR_ASSETS_DUE_WITHIN_1Y | float | 一年内到期的非流动资产 | - |
| NONCUR_LIAB_DUE_WITHIN_1Y | float | 一年内到期的非流动负债 | - |
| NOTES_PAYABLE | float | 应付票据 | - |
| NOTES_RECEIVABLE | float | 应收票据 | - |
| OIL_AND_GAS_ASSETS | float | 油气资产 | - |
| OTH_COMP_INCOME | float | 其他综合收益 | - |
| OTH_EQUITY_TOOLS | float | 其他权益工具 | - |
| OTH_EQUITY_TOOLS_PRE_SHR | float | 其他权益工具:优先股 | - |
| OTH_NONCUR_ASSETS | float | 其他非流动资产 | - |
| OTHER_ASSETS | float | 其他资产 | - |
| OTHER_CUR_ASSETS | float | 其他流动资产 | - |
| OTHER_CUR_LIAB | float | 其他流动负债 | - |
| OTHER_DEBT_INV | float | 其他债权投资(元) | - |
| OTHER_EQUITY_INV | float | 其他权益工具投资(元) | - |
| OTHER_LIAB | float | 其他负债 | - |
| OTHER_NONCUR_FIN_ASSETS | float | 其他非流动金融资产(元) | - |
| OTHER_NONCUR_LIAB | float | 其他非流动负债 | - |
| OTHER_PAYABLE | float | 其他应付款 | - |
| OTHER_PAYABLE_TOTAL | float | 其他应付款(合计)(元) | - |
| OTHER_RCV_TOTAL | float | 其他应收款(合计)（元） | - |
| OTHER_RECEIVABLE | float | 其他应收款 | - |
| OTHER_SUSTAIN_BONDS | float | 其他权益工具:永续债(元) | - |
| OUT_LOSS_RESV | float | 未决赔款准备金 | - |
| PAYABLE | float | 应付款项 | - |
| PAYABLE_FOR_REINSURANCE | float | 应付分保账款 | - |
| PRECIOUS_METAL | float | 贵金属 | - |
| PREPAYMENT | float | 预付款项 | - |
| PROD_BIO_ASSETS | float | 生产性生物资产 | - |
| RCV_CED_CLAIM_RESV | float | 应收分保未决赔款准备金 | - |
| RCV_CED_LIFE_INSUR_RESV | float | 应收分保寿险责任准备金 | - |
| RCV_CED_LT_HEALTH_INSUR_RESV | float | 应收分保长期健康险责任准备金 | - |
| RCV_CED_UNEARNED_PREM_RESV | float | 应收分保未到期责任准备金 | - |
| RCV_FINANCING | float | 应收款项融资 | - |
| RCV_INV | float | 应收款项类投资 | - |
| RECEIVABLE_PREM | float | 应收保费 | - |
| RED_MON_CAP_FOR_SALE | float | 买入返售金融资产 | - |
| REINSURANCE_ACC_RCV | float | 应收分保账款 | - |
| RSRV_FUND_INSUR_CONT | float | 保险合同准备金 | - |
| SELL_REPO_FIN_ASSETS | float | 卖出回购金融资产款 | - |
| SERVICE_CHARGE_COMM_PAYABLE | float | 应付手续费及佣金 | - |
| SETTLE_FUNDS | float | 结算备付金 | - |
| SPE_ASSETS_BAL_DIFF | float | 资产差额(特殊报表科目) | - |
| SPE_CUR_ASSETS_DIFF | float | 流动资产差额(特殊报表科目) | - |
| SPE_CUR_LIAB_DIFF | float | 流动负债差额(特殊报表科目) | - |
| SPE_LIAB_BAL_DIFF | float | 负债差额(特殊报表科目) | - |
| SPE_LIAB_EQUITY_BAL_DIFF | float | 负债及股东权益差额(特殊报表项目) | - |
| SPE_NONCUR_ASSETS_DIFF | float | 非流动资产差额(特殊报表科目) | - |
| SPE_NONCUR_LIAB_DIFF | float | 非流动负债差额(特殊报表科目) | - |
| SPE_SHARE_EQUITY_BAL_DIFF | float | 股东权益差额(特殊报表科目) | - |
| SPECIAL_PAYABLE | float | 专项应付款 | - |
| SPECIAL_RESV | float | 专项储备 | - |
| ST_BONDS_PAYABLE | float | 应付短期债券 | - |
| ST_BORROWING | float | 短期借款 | - |
| ST_FIN_PAYABLE | float | 应付短期融资款 | - |
| SUBR_RCV | float | 应收代位追偿款 | - |
| SURPLUS_RESV | float | 盈余公积金 | - |
| TAX_PAYABLE | float | 应交税费 | - |
| TOT_ASSETS_BAL_DIFF | float | 资产差额(合计平衡项目) | - |
| TOT_CUR_ASSETS_DIFF | float | 流动资产差额(合计平衡项目) | - |
| TOT_CUR_LIAB_DIFF | float | 流动负债差额(合计平衡项目) | - |
| TOT_LIAB_BAL_DIFF | float | 负债差额(合计平衡项目) | - |
| TOT_LIAB_EQUITY_BAL_DIFF | float | 负债及股东权益差额(合计平衡项目) | - |
| TOT_NONCUR_ASSETS | float | 非流动资产合计 | - |
| TOT_NONCUR_ASSETS_DIFF | float | 非流动资产差额(合计平衡项目) | - |
| TOT_NONCUR_LIAB_DIFF | float | 非流动负债差额(合计平衡项目) | - |
| TOT_SHARE | float | 期末总股本 | 单位（股） |
| TOT_SHARE_EQUITY_BAL_DIFF | float | 股东权益差额(合计平衡项目) | - |
| TOT_SHARE_EQUITY_EXCL_MIN_INT | float | 股东权益合计(不含少数股东权益) | - |
| TOT_SHARE_EQUITY_INCL_MIN_INT | float | 股东权益合计(含少数股东权益) | - |
| TOTAL_ASSETS | float | 资产总计 | - |
| TOTAL_CUR_ASSETS | float | 流动资产合计 | - |
| TOTAL_CUR_LIAB | float | 流动负债合计 | - |
| TOTAL_LIAB | float | 负债合计 | - |
| TOTAL_LIAB_SHARE_EQUITY | float | 负债及股东权益总计 | - |
| TOTAL_NONCUR_LIAB | float | 非流动负债合计 | - |
| TRADING_FIN_LIAB | float | 交易性金融负债 | - |
| TRADING_FINASSETS | float | 交易性金融资产 | - |
| UNAMORTIZED_EXP | float | 待摊费用 | - |
| UNCONFIRMED_INV_LOSS | float | 未确认的投资损失 | - |
| UNDISTRIBUTED_PRO | float | 未分配利润 | - |
| UNEARNED_PREM_RESV | float | 未到期责任准备金 | - |
| USE_RIGHT_ASSETS | float | 使用权资产 | - |

#### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "SECURITY_NAME": "平安银行",
  "STATEMENT_TYPE": "合并报表",
  "REPORT_TYPE": "2023年报",
  "REPORTING_PERIOD": "2023-12-31",
  "ANN_DATE": "2024-03-28",
  "ACTUAL_ANN_DATE": "2024-03-28",
  "TOTAL_ASSETS": 4553234000000.0,
  "TOTAL_CUR_ASSETS": 2100000000000.0,
  "TOTAL_CUR_LIAB": 1800000000000.0,
  "TOTAL_LIAB": 4100000000000.0,
  "TOT_SHARE_EQUITY_INCL_MIN_INT": 453234000000.0,
  "CURRENCY_CAP": 350000000000.0,
  "CAP_STOCK": 19408221800.0,
  "TOT_SHARE": 19408221800.0,
  "FIXED_ASSETS": 80000000000.0,
  "GOODWILL": 50000000000.0,
  "INTANGIBLE_ASSETS": 20000000000.0,
  "INV": 30000000000.0,
  "COMP_TYPE_CODE": 2
}
```

---

### 2. cashflow - 现金流量表

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_cash_flow(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.2 现金流量表

#### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | 映射到表 symbol |
| SECURITY_NAME | string | 证券简称 | 映射到表 security_name |
| STATEMENT_TYPE | string | 报表类型 | 参看报表类型代码表，映射到表 statement_code |
| REPORT_TYPE | string | 报告期名称 | 参看报告期名称，映射到表 report_type |
| REPORTING_PERIOD | string | 报告期 | YYYY-MM-DD 格式，映射到表 reporting_period |
| ANN_DATE | string | 公告日期 | YYYY-MM-DD 格式，映射到表 ann_date |
| ACTUAL_ANN_DATE | string | 实际公告日期 | YYYY-MM-DD 格式，映射到表 actual_ann_date |
| ABSORB_CASH_RECP_INV | double | 吸收投资收到的现金 | - |
| AMORT_INTAN_ASSETS | double | 无形资产摊销 | - |
| AMORT_LT_DEFERRED_EXP | double | 长期待摊费用摊销 | - |
| BEG_BAL_CASH_CASH_EQU | double | 期初现金及现金等价物余额 | - |
| CASH_END_BAL | double | 现金的期末余额 | - |
| CASH_FOR_CHARGE | double | 支付手续费的现金 | - |
| CASH_PAID_INSUR_POLICY | double | 支付保单红利的现金 | - |
| CASH_PAID_INV | double | 投资支付的现金 | - |
| CASH_PAID_PUR_CONST_FIOLTA | double | 购建固定资产、无形资产和其他长期资产支付的现金 | - |
| CASH_PAY_CLAIMS_OIC | double | 支付原保险合同赔付款项的现金 | - |
| CASH_PAY_DIST_DIV_PRO_INT | double | 分配股利、利润或偿付利息支付的现金 | - |
| CASH_PAY_EMPLOYEE | double | 支付给职工以及为职工支付的现金 | - |
| CASH_PAY_FOR_DEBT | double | 偿还债务支付的现金 | - |
| CASH_PAY_GOODS_SERVICES | double | 购买商品、接受劳务支付的现金 | - |
| CASH_RECE_BORROW | double | 取得借款收到的现金 | - |
| CASH_RECE_ISSUE_BONDS | double | 发行债券收到的现金 | - |
| CASH_RECP_INV_INCOME | double | 取得投资收益收到的现金 | - |
| CASH_RECP_PREM_OIC | double | 收到原保险合同保费取得的现金 | - |
| CASH_RECP_RECOV_INV | double | 收回投资收到的现金 | - |
| CASH_RECP_SG_AND_RS | double | 销售商品、提供劳务收到的现金 | - |
| COMP_TYPE_CODE | string | 公司类型代码 | 1:非金融类 2:银行 3:保险 4:证券，映射到表 comp_type_code |
| CONV_CORP_BONDS_DUE_WITHIN_1Y | double | 一年内到期的可转换公司债券 | - |
| CONV_DEBT_INT_O_CAP | double | 债务转为资本 | - |
| CREDIT_IMPAIR_LOSS | double | 信用减值损失 | - |
| CURRENCY_CODE | string | 货币代码 | - |
| DECR_DEFER_INC_TAX_ASSETS | double | 递延所得税资产减少 | - |
| DECR_DEFERRED_EXPENSE | double | 待摊费用减少 | - |
| DECR_INVENTORY | double | 存货的减少 | - |
| DECR_OPERA_RECEIVABLE | double | 经营性应收项目的减少 | - |
| DEPRE_FA_OGA_PBA | double | 固定资产折旧、油气资产折耗、生产性生物资产折旧 | - |
| EFF_FX_FLUC_CASH | double | 汇率变动对现金的影响 | - |
| END_BAL_CASH_CASH_EQU | double | 期末现金及现金等价物余额 | - |
| FINANCIAL_EXP | double | 财务费用 | - |
| FIXED_ASSETS_F_IN_LEASE | double | 融资租入固定资产 | - |
| FREE_CASH_FLOW | double | 企业自由现金流量 | - |
| INCL_CASH_RECP_SAIMS | double | 其中:子公司吸收少数股东投资收到的现金 | - |
| INCL_DIV_PRO_PAID_SMS | double | 其中:子公司支付给少数股东的股利、利润 | - |
| INCR_ACCRUED_EXP | double | 预提费用增加 | - |
| INCR_DEFE_INC_TAX_LIAB | double | 递延所得税负债增加 | - |
| INCR_OPERA_PAYABLE | double | 经营性应付项目的增加 | - |
| IND_NET_CASH_FLOWS_OPERA_ACT | double | 间接法-经营活动产生的现金流量净额 | - |
| IND_NET_INCR_CASH_AND_EQU | double | 间接法-现金及现金等价物净增加额 | - |
| INV_LOSS | double | 投资损失 | - |
| IS_CALCULATION | int | 是否计算报表 | - |
| LESS_OPEN_BAL_CASH | double | 减:现金的期初余额 | - |
| LESS_OPEN_BAL_CASH_EQU | double | 减:现金等价物的期初余额 | - |
| LOSS_DISP_FIOLTA | double | 处置固定、无形资产和其他长期资产的损失 | - |
| LOSS_FAIRVALUE_CHG | double | 公允价值变动损失 | - |
| LOSS_FIXED_ASSETS | double | 固定资产报废损失 | - |
| NET_CASH_FLOW_FIN_ACT | double | 筹资活动产生的现金流量净额 | - |
| NET_CASH_FLOW_INV_ACT | double | 投资活动产生的现金流量净额 | - |
| NET_CASH_FLOW_OPERA_ACT | double | 经营活动产生的现金流量净额 | - |
| NET_CASH_PAID_SOBU | double | 取得子公司及其他营业单位支付的现金净额 | - |
| NET_CASH_RECV_SEC | double | 代理买卖证券收到的现金净额 | - |
| NET_CASH_RECP_DISP_FIOLTA | double | 处置固定资产、无形资产和其他长期资产收回的现金净额 | - |
| NET_CASH_RECP_DISP_SOBU | double | 处置子公司及其他营业单位收到的现金净额 | - |
| NET_CASH_RECP_REINSU_BUS | double | 收到再保业务现金净额 | - |
| NET_INCR_BORR_FUND | double | 拆入资金净增加额 | - |
| NET_INCR_BORR_OFI | double | 向其他金融机构拆入资金净增加额 | - |
| NET_INCR_CASH_AND_CASH_EQU | double | 现金及现金等价物净增加额 | - |
| NET_INCR_CUS_LOAN_ADV | double | 客户贷款及垫款净增加额 | - |
| NET_INCR_DEP_CB_IB | double | 存放央行和同业款项净增加额 | - |
| NET_INCR_DEP_CUS_AND_IB | double | 客户存款和同业存放款项净增加额 | - |
| NET_INCR_DISM_CAPLE | double | 拆出资金净增加额 | - |
| NET_INCR_DISP_FAAS | double | 处置可供出售金融资产净增加额 | - |
| NET_INCR_DISP_TFA | double | 处置交易性金融资产净增加额 | - |
| NET_INCR_INSU_RED_SAVE | double | 保户储金净增加额 | - |
| NET_INCR_INT_AND_CHARGE | double | 收取利息和手续费净增加额 | - |
| NET_INCR_LOANS_CENTRAL_BANK | double | 向中央银行借款净增加额 | - |
| NET_INCR_PLEDGE_LOAN | double | 质押贷款净增加额 | - |
| NET_INCR_REPU_BUS_FUND | double | 回购业务资金净增加额 | - |
| NET_PROFIT | double | 净利润 | - |
| OTH_CASH_PAY_INV_ACT | double | 支付其他与投资活动有关的现金 | - |
| OTH_CASH_PAY_OPERA_ACT | double | 支付其他与经营活动有关的现金 | - |
| OTH_CASH_RECP_INV_ACT | double | 收到其他与投资活动有关的现金 | - |
| OTHER_ASSETS_IMPAIR_LOSS | double | 其他资产减值损失 | - |
| OTHER_CASH_PAY_FIN_ACT | double | 支付其他与筹资活动有关的现金 | - |
| OTHER_CASH_RECP_FIN_ACT | double | 收到其他与筹资活动有关的现金 | - |
| OTHER_CASH_RECP_OPER_ACT | double | 收到其他与经营活动有关的现金 | - |
| OTHERS | double | 其他（废弃） | - |
| PAY_ALL_TAX | double | 支付的各项税费 | - |
| PLUS_ASSETS_DEPRE_PREP | double | 加:资产减值准备 | - |
| PLUS_END_BAL_CASH_EQU | double | 加:现金等价物的期末余额 | - |
| RECP_TAX_REFUND | double | 收到的税费返还 | - |
| SPE_BAL_CASH_INFLOW_FIN_ACT | double | 筹资活动现金流入差额 | - |
| SPE_BAL_CASH_INFLOW_INV_ACT | double | 投资活动现金流入差额 | - |
| SPE_BAL_CASH_INFLOW_OPERA_ACT | double | 经营活动现金流入差额 | - |
| SPE_BAL_CASH_OUTFLOW_FIN | double | 筹资活动现金流出差额 | - |
| SPE_BAL_CASH_OUTFLOW_INV | double | 投资活动现金流出差额 | - |
| SPE_BAL_CASH_OUTFLOW_OPERA | double | 经营活动现金流出差额 | - |
| SPE_BAL_NETCASH_INC_DIFF_IND | double | 间接法-现金净增加额差额 | - |
| SPE_BAL_NETCASH_INCR_DIFF | double | 现金净增加额差额 | - |
| SPE_BAL_NETCASH_OPERA_IND | double | 间接法-经营活动现金流量净额差额 | - |
| TOT_BAL_CASH_INFLOW_FIN_ACT | double | 筹资活动现金流入差额 | - |
| TOT_BAL_CASH_INFLOW_INV_ACT | double | 投资活动现金流入差额 | - |
| TOT_BAL_CASH_INFLOW_OPERA_ACT | double | 经营活动现金流入差额 | - |
| TOT_BAL_CASH_OUTFLOW_FIN | double | 筹资活动现金流出差额 | - |
| TOT_BAL_CASH_OUTFLOW_INV | double | 投资活动现金流出差额 | - |
| TOT_BAL_CASH_OUTFLOW_OPERA | double | 经营活动现金流出差额 | - |
| TOT_BAL_NETCASH_FLOW_FIN | double | 筹资活动产生的现金流量净额差额 | - |
| TOT_BAL_NETCASH_FLOW_INV | double | 投资活动产生的现金流量净额差额 | - |
| TOT_BAL_NETCASH_FLOW_OPERA | double | 经营活动产生的现金流量净额差额 | - |
| TOT_BAL_NETCASH_INC_DIFF_IND | double | 间接法-现金净增加额差额 | - |
| TOT_BAL_NETCASH_INCR_DIFF | double | 现金净增加额差额 | - |
| TOT_BAL_NETCASH_OPERA_IND | double | 间接法-经营活动现金流量净额差额 | - |
| TOT_CASH_INFLOW_FIN_ACT | double | 筹资活动现金流入小计 | - |
| TOT_CASH_INFLOW_INV_ACT | double | 投资活动现金流入小计 | - |
| TOT_CASH_INFLOW_OPER_ACT | double | 经营活动现金流入小计 | - |
| TOT_CASH_OUTFLOW_FIN_ACT | double | 筹资活动现金流出小计 | - |
| TOT_CASH_OUTFLOW_INV_ACT | double | 投资活动现金流出小计 | - |
| TOT_CASH_OUTFLOW_OPER_ACT | double | 经营活动现金流出小计 | - |
| UNCONFIRMED_INV_LOSS | double | 未确认投资损失 | - |
| USE_RIGHT_ASSET_DEP | double | 使用权资产折旧 | - |

#### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "SECURITY_NAME": "平安银行",
  "STATEMENT_TYPE": "合并报表",
  "REPORT_TYPE": "2023年报",
  "REPORTING_PERIOD": "2023-12-31",
  "ANN_DATE": "2024-03-28",
  "ACTUAL_ANN_DATE": "2024-03-28",
  "NET_CASH_FLOW_OPERA_ACT": 250000000000.0,
  "NET_CASH_FLOW_INV_ACT": -80000000000.0,
  "NET_CASH_FLOW_FIN_ACT": -120000000000.0,
  "NET_INCR_CASH_AND_CASH_EQU": 50000000000.0,
  "BEG_BAL_CASH_CASH_EQU": 150000000000.0,
  "END_BAL_CASH_CASH_EQU": 200000000000.0,
  "NET_PROFIT": 380000000000.0,
  "CASH_RECP_SG_AND_RS": 1200000000000.0,
  "CASH_PAY_GOODS_SERVICES": -900000000000.0,
  "PAY_ALL_TAX": -50000000000.0,
  "COMP_TYPE_CODE": 2
}
```

---

### 3. income - 利润表

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_income(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.3 利润表

#### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | 映射到表 symbol |
| SECURITY_NAME | string | 证券简称 | 映射到表 security_name |
| STATEMENT_TYPE | string | 报表类型 | 参看报表类型代码表，映射到表 statement_code |
| REPORT_TYPE | string | 报告期名称 | 参看报告期名称，映射到表 report_type |
| REPORTING_PERIOD | string | 报告期 | YYYY-MM-DD 格式，映射到表 reporting_period |
| ANN_DATE | string | 公告日期 | YYYY-MM-DD 格式，映射到表 ann_date |
| ACTUAL_ANN_DATE | string | 实际公告日期 | YYYY-MM-DD 格式，映射到表 actual_ann_date |
| AMORT_COST_FIN_ASSETS_EAR | float | 以摊余成本计量的金融资产终止确认收益 | - |
| BASIC_EPS | float | 基本每股收益 | - |
| BEG_UNDISTRIBUTED_PRO | float | 年初未分配利润 | - |
| CAPITALIZED_COM_STOCK_DIV | float | 转作股本的普通股股利 | - |
| COMMENTS | string | 备注 | - |
| COMMON_STOCK_DIV_PAYABLE | float | 应付普通股股利 | - |
| COMP_TYPE_CODE | string | 公司类型代码 | 1:非金融类 2:银行 3:保险 4:证券，映射到表 comp_type_code |
| CONTINUED_NET_OPERA_PRO | float | 持续经营净利润 | - |
| CREDIT_IMPAIR_LOSS | float | 信用减值损失 | - |
| CURRENCY_CODE | string | 货币代码 | - |
| DILUTED_EPS | float | 稀释每股收益 | - |
| DISTRIBUTIVE_PRO | float | 可分配利润 | - |
| DISTRIBUTIVE_PRO_SHAREHOLDER | float | 可供股东分配的利润 | - |
| DIV_EXP_INSUR | float | 保户红利支出 | - |
| EBIT | float | 息税前利润 | 正向法 |
| EBITDA | float | 息税折旧摊销前利润 | - |
| EMPLOYEE_WELF | float | 职工奖金福利 | - |
| END_NET_OPERA_PRO | float | 终止经营净利润 | - |
| EXT_INSUR_CONT_RESV | float | 提取保险责任准备金 | - |
| EXT_UNEARNED_PREM_RES | float | 提取未到期责任准备金 | - |
| FIN_EXP_INT_EXP | float | 财务费用:利息费用 | - |
| FIN_EXP_INT_INC | float | 财务费用:利息收入 | - |
| GAIN_DISPOSAL_ASSETS | float | 资产处置收益 | - |
| HANDLING_CHRG_COMM_FEE | float | 手续费及佣金收入 | - |
| INCL_INC_INV_JV_ENTP | float | 其中:对联营企业和合营企业的投资收益 | - |
| INCL_LESS_LOSS_DISP_NCUR_ASSETS | float | 其中:减:非流动资产处置净损失 | - |
| INCL_REINSUR_PREM_INC | float | 其中:分保费收入 | - |
| INCOME_TAX | float | 所得税 | - |
| INSUR_EXP | float | 保险业务支出 | - |
| INSUR_PREM | float | 已赚保费 | - |
| INTEREST_INC | float | 利息收入 | - |
| IS_CALCULATION | float | 是否计算报表 | - |
| LESS_ADMIN_EXP | float | 减:管理费用 | - |
| LESS_AMORT_COMPEN_EXP | float | 减:摊回赔付支出 | - |
| LESS_AMORT_INSUR_CONT_RSRV | float | 减:摊回保险责任准备金 | - |
| LESS_AMORT_REINSUR_EXP | float | 减:摊回分保费用 | - |
| LESS_ASSETS_IMPAIR_LOSS | float | 减:资产减值损失 | - |
| LESS_BUS_TAX_SURCHARGE | float | 减:营业税金及附加 | - |
| LESS_FIN_EXP | float | 减:财务费用 | - |
| LESS_HANDLING_CHRG_COMM_FEE | float | 减:手续费及佣金支出 | - |
| LESS_INTEREST_EXP | float | 减:利息支出 | - |
| LESS_NON_OPER_EXP | float | 减:营业外支出 | - |
| LESS_OPERA_COST | float | 减:营业成本 | - |
| LESS_REINSUR_PREM | float | 减:分出保费 | - |
| LESS_SELLING_EXP | float | 减:销售费用 | - |
| MIN_INT_INC | float | 少数股东损益 | - |
| NET_EXPOSURE_HEDGING_GAIN | float | 净敞口套期收益 | - |
| NET_HANDLING_CHRG_COMM_FEE | float | 手续费及佣金净收入 | - |
| NET_INC_EC_ASSET_MGMT_BUS | float | 受托客户资产管理业务净收入 | - |
| NET_INC_SEC_BROK_BUS | float | 代理买卖证券业务净收入 | - |
| NET_INC_SEC_UW_BUS | float | 证券承销业务净收入 | - |
| NET_INTEREST_INC | float | 利息净收入 | - |
| NET_PRO_AFTER_DED_NR_GL | float | 扣除非经常性损益后净利润（扣除少数股东损益） | - |
| NET_PRO_AFTER_DED_NR_GL_COR | float | 扣除非经常性损益后的净利润(财务重要指标(更正前)) | - |
| NET_PRO_EXCL_MIN_INT_INC | float | 净利润 (不含少数股东损益) | - |
| NET_PRO_INCL_MIN_INT_INC | float | 净利润 (含少数股东损益) | - |
| NET_PRO_UNDER_INT_ACC_STA | float | 国际会计准则净利润 | - |
| OPERA_EXP | float | 营业支出 | - |
| OPERA_PROFIT | float | 营业利润 | - |
| OPERA_REV | float | 营业收入 | - |
| OTH_ASSETS_IMPAIR_LOSS | float | 其他资产减值损失 | - |
| OTH_BUS_COST | float | 其他业务成本 | - |
| OTH_BUS_INC | float | 其他业务收入 | - |
| OTH_COMPRE_IN_C | float | 其他综合收益 | - |
| OTH_INCOME | float | 其他收益 | - |
| OTH_NET_OPERA_INC | float | 其他经营净收益 | - |
| PLUS_NET_FX_INC | float | 加:汇兑净收益 | - |
| PLUS_NET_GAIN_CHG_FV | float | 加:公允价值变动净收益 | - |
| PLUS_NET_INV_INC | float | 加:投资净收益 | - |
| PLUS_NON_OPER_A_REV | float | 加:营业外收入 | - |
| PLUS_OTH_NET_BUS_INC | float | 加:其他业务净收益 | - |
| PREFERRED_SHARE_DIV_PAYABLE | float | 应付优先股股利 | - |
| PREM_BUS_INC | float | 保费业务收入 | - |
| RD_EXP | float | 研发费用 | - |
| REINSURANCE_EXP | float | 分保费用 | - |
| SPE_BAL_NET_PRO_MARG | float | 净利润差额 (特殊报表科目) | - |
| SPE_BAL_OPERA_PRO_MARG | float | 营业利润差额 (特殊报表科目) | - |
| SPE_BAL_TOT_OPERA_COST_DIF | float | 营业总成本差额 (特殊报表科目) | - |
| SPE_BAL_TOT_OPERA_INC_DIF | float | 营业总收入差额 (特殊报表科目) | - |
| SPE_BAL_TOT_PRO_MARG | float | 利润总额差额 (特殊报表科目) | - |
| SPE_TOT_OPERA_COST_DIF_STATE | string | 营业总成本差额说明(特殊报表科目) | - |
| SPE_TOT_OPERA_INC_DIF_STATE | string | 营业总收入差额说明(特殊报表科目) | - |
| SURR_VALUE | float | 退保金 | - |
| TOT_BAL_NET_PRO_MARG | float | 净利润差额 (合计平衡项目) | - |
| TOT_BAL_OPERA_PRO_MARG | float | 营业利润差额 (合计平衡项目) | - |
| TOT_BAL_TOT_PRO_MARG | float | 利润总额差额 (合计平衡项目) | - |
| TOT_COMPEN_EXP | float | 赔付总支出 | - |
| TOT_COMPRE_IN_C | float | 综合收益总额 | - |
| TOT_COMPRE_IN_C_MIN_SHARE | float | 综合收益总额 (少数股东) | - |
| TOT_COMPRE_IN_C_PARENT_COMP | float | 综合收益总额 (母公司) | - |
| TOT_OPERA_COST | float | 营业总成本 | - |
| TOT_OPERA_COST2 | float | 营业总成本2 | - |
| TOT_OPERA_REV | float | 营业总收入 | - |
| TOTAL_PROFIT | float | 利润总额 | - |
| TRANSFER_HOUSING_REVO_FUNDS | float | 住房周转金转入 | - |
| TRANSFER_OTHERS | float | 其他转入 | - |
| TRANSFER_SURPLUS_RESERVE | float | 盈余公积转入 | - |
| UNCONFIRMED_INV_LOSS | float | 未确认投资损失 | - |
| WITHDRAW_ANY_SURPLUS_RESV | float | 提取任意盈余公积金 | - |
| WITHDRAW_ENT_DEVELOP_FUND | float | 提取企业发展基金 | - |
| WITHDRAW_LEG_PUB_WEL_FUND | float | 提取法定公益金 | - |
| WITHDRAW_LEG_SURPLUS | float | 提取法定盈余公积 | - |
| WITHDRAW_RESV_FUND | float | 提取储备基金 | - |

#### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "SECURITY_NAME": "平安银行",
  "STATEMENT_TYPE": "合并报表",
  "REPORT_TYPE": "2023年报",
  "REPORTING_PERIOD": "2023-12-31",
  "ANN_DATE": "2024-03-28",
  "ACTUAL_ANN_DATE": "2024-03-28",
  "TOT_OPERA_REV": 1650000000000.0,
  "TOT_OPERA_COST": 1270000000000.0,
  "OPERA_PROFIT": 380000000000.0,
  "TOTAL_PROFIT": 380000000000.0,
  "NET_PRO_INCL_MIN_INT_INC": 378000000000.0,
  "NET_PRO_EXCL_MIN_INT_INC": 376000000000.0,
  "MIN_INT_INC": 2000000000.0,
  "BASIC_EPS": 1.95,
  "DILUTED_EPS": 1.93,
  "INCOME_TAX": 20000000000.0,
  "INTEREST_INC": 1200000000000.0,
  "FIN_EXP_INT_EXP": -800000000000.0,
  "EBIT": 420000000000.0,
  "EBITDA": 480000000000.0,
  "COMP_TYPE_CODE": 2
}
```

---

### 4. profit_express - 业绩快报

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_profit_express(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.4 业绩快报

#### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | 映射到表 symbol |
| REPORTING_PERIOD | string | 报告期 | 报告内容记录的截止时间点，报告成果的时期，映射到表 reporting_period |
| ANN_DATE | string | 公告日期 | 公告发布当天的日期；有多个阶段的事件，首次披露该事件的日期，映射到表 ann_date |
| ACTUAL_ANN_DATE | string | 实际公告日期 | 实际数据来源公告的日期；更正斯发生公告的日期，映射到表 actual_ann_date |
| TOTAL_ASSETS | float64 | 总资产(元) | 指经济实体拥有或控制的能带来经济利益的全部资产 |
| NET_PRO_EXCL_MIN_INT_INC | float64 | 净利润(元) | 企业合并净利润中归属于母公司股东所有的那部分利润 |
| TOT_OPERA_REV | float64 | 营业总收入(元) | 企业从事销售商品、提供劳务和让渡资产使用权等日常业务过程形成的经济利益的总流入 |
| TOTAL_PROFIT | float64 | 利润总额(元) | 企业一定时期内的纯收入扣除应交纳后的余额 |
| OPERA_PROFIT | float64 | 营业利润(元) | 企业在其全部销售业务中实现的利润 |
| EPS_BASIC | float64 | 每股收益-基本(元) | 企业按照属于普通股股东的当期净利润，除以发行在外普通股的加权平均数计算得到的每股收益 |
| TOT_SHARE_EQUITY_EXCL_MIN_INT | float64 | 股东权益合计 ( 不 含 少 数 股 东 权 益)(元) | 公司集团的所有者权益中归属于母公司所有者权益的部分 |
| IS_AUDIT | float64 | 是否审计 | 1:是 0：否 |
| ROE_WEIGHTED | float64 | 净资产收益率-加权(%) | 经营期间净资产赚取利润的结果的一个动态指标，反应企业净资产创造利润的能力 |
| LAST_YEAR_REVISED_NET_PRO | float64 | 去年同期修正后净利润（元） | - |
| PERFORMANCE_SUMMARY | string | 业绩简要说明 | 针对业绩快报的简单说明 |
| NET_ASSET_PS | float64 | 每股净资产（元） | - |
| MEMO | string | 备注 | 附加的注解说明 |
| YOY_GR_GROSS_PRO | float64 | 同比增长率:% 营业利润 | - |
| YOY_GR_GROSS_REV | float64 | 同比增长率:% 营业总收入 | - |
| YOY_GR_NET_PROFIT_PARENT | float64 | 同比增长率:% 归属母公司股东的净利润 | - |
| YOY_GR_TOT_PROFIT | float64 | 同比增长率:% 利润总额 | - |
| YOY_ID_WAROE | float64 | 同比增减:加权平均净资产收益率% | - |
| YOY_GR_EPS_BASIC | float64 | 同比增长率:% 基本每股收益 | - |
| GROWTH_RATE_EQUITY | float64 | 比年初增长率:归属母公司的股东权益% | - |
| GROWTH_RATE_ASSETS | float64 | 比年初增长率:总资产% | - |
| GROWTH_RATE_NAPS | float64 | 比年初增长率:归属于母公司的每股净资产% | - |
| LAST_YEAR_TOT_OPERA_REV | float64 | 去年同期营业总收入（元） | - |
| LAST_YEAR_TOT_PROFIT | float64 | 去年同期利润总额（元） | - |
| LAST_YEAR_OPERA_PRO | float64 | 去年同期营业利润（元） | - |
| LAST_YEAR_EPS_DILUTED | float64 | 去年同期每股收益（元） | - |
| LAST_YEAR_NET_PROFIT | float64 | 去年同期净利润（元） | - |
| INITIAL_NET_ASSET_PS | float64 | 期初每股净资产（元） | - |
| INITIAL_NET_ASSETS | float64 | 期初净资产（元） | - |

#### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "REPORTING_PERIOD": "2023-12-31",
  "ANN_DATE": "2024-01-20",
  "ACTUAL_ANN_DATE": "2024-01-20",
  "TOTAL_ASSETS": 4553234000000.0,
  "NET_PRO_EXCL_MIN_INT_INC": 376000000000.0,
  "TOT_OPERA_REV": 1650000000000.0,
  "TOTAL_PROFIT": 380000000000.0,
  "OPERA_PROFIT": 380000000000.0,
  "EPS_BASIC": 1.95,
  "TOT_SHARE_EQUITY_EXCL_MIN_INT": 453234000000.0,
  "IS_AUDIT": 0.0,
  "ROE_WEIGHTED": 12.5,
  "LAST_YEAR_REVISED_NET_PRO": 320000000000.0,
  "PERFORMANCE_SUMMARY": "公司2023年度业绩保持稳定增长",
  "NET_ASSET_PS": 23.35,
  "MEMO": "",
  "YOY_GR_GROSS_PRO": 8.5,
  "YOY_GR_GROSS_REV": 6.2,
  "YOY_GR_NET_PROFIT_PARENT": 8.1,
  "YOY_GR_TOT_PROFIT": 7.8,
  "YOY_ID_WAROE": 0.3,
  "YOY_GR_EPS_BASIC": 7.2,
  "GROWTH_RATE_EQUITY": 5.8,
  "GROWTH_RATE_ASSETS": 6.5,
  "GROWTH_RATE_NAPS": 5.2
}
```

---

### 5. profit_notice - 业绩预告

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_profit_notice(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.5 业绩预告

#### data_json 字段结构

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| MARKET_CODE | string | 证券代码 | 映射到表 symbol |
| SECURITY_NAME | string | 证券简称 | 映射到表 security_name |
| P_TYPECODE | string | 业绩预告类型代码 | 1：不确定 2：略减 3：略增 4：扭亏 5：其他 6：首亏 7：续亏 8：续盈 9：预减 10：预增 11：持平 |
| REPORTING_PERIOD | string | 报告期 | 分为年度、半年度、季度，映射到表 reporting_period |
| ANN_DATE | string | 公告日期 | 公告发布当天的日期，映射到表 ann_date |
| P_CHANGE_MAX | float64 | 预告净利润变动幅度上限（%） | 对于净利润金额同比变动幅度预计的最高值 |
| P_CHANGE_MIN | float64 | 预告净利润变动幅度下限（%） | 对于净利润金额同比变动幅度预计的最低值 |
| NET_PROFIT_MAX | float64 | 预告净利润上限（万元） | 对于净利润金额预计的最高值 |
| NET_PROFIT_MIN | float64 | 预告净利润下限（万元） | 对于净利润金额预计的最低值 |
| FIRST_ANN_DATE | string | 首次公告日 | 首次披露本报告期业绩预告内容的公告日期 |
| P_NUMBER | float64 | 公布次数 | 同一报告期的业绩预告公告的披露次数 |
| P_REASON | string | 业绩变动原因 | - |
| P_SUMMARY | string | 业绩预告摘要 | - |
| P_NET_PARENT_FIRM | float64 | 上年同期归母净利润 | 业绩预告中直接公布的上年同期归母净利润 |
| REPORT_TYPE | string | 报告期名称 | 参看报告期名称，映射到表 report_type |

#### 业绩预告类型代码 (P_TYPECODE)

| 类型代码 | 类型说明 |
|----------|----------|
| 1 | 不确定 |
| 2 | 略减 |
| 3 | 略增 |
| 4 | 扭亏 |
| 5 | 其他 |
| 6 | 首亏 |
| 7 | 续亏 |
| 8 | 续盈 |
| 9 | 预减 |
| 10 | 预增 |
| 11 | 持平 |

#### 示例数据

```json
{
  "MARKET_CODE": "000001",
  "SECURITY_NAME": "平安银行",
  "P_TYPECODE": "10",
  "REPORTING_PERIOD": "2023-12-31",
  "ANN_DATE": "2024-01-15",
  "P_CHANGE_MAX": 10.0,
  "P_CHANGE_MIN": 8.0,
  "NET_PROFIT_MAX": 3800000.0,
  "NET_PROFIT_MIN": 3700000.0,
  "FIRST_ANN_DATE": "2023-10-28",
  "P_NUMBER": 2.0,
  "P_REASON": "公司各项业务稳步发展，资产质量持续改善",
  "P_SUMMARY": "预计2023年度归属于上市公司股东的净利润同比增长8%-10%",
  "P_NET_PARENT_FIRM": 3500000.0,
  "REPORT_TYPE": "年报"
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

## 行业指数数据表

### industry_base_info - 行业指数基本信息表

#### 概述

`industry_base_info` 表存储行业指数的基本信息，包括指数代码、行业分类、级别等元数据。数据来源于 AmazingData 的"行业指数数据"类别。

#### 表结构

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

#### 唯一索引

- `uk_industry_base`: (source, index_code)

#### B-tree 索引

- `idx_industry_code`: (industry_code)
- `idx_level_type`: (level_type)

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_base_info()`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.1 行业指数基本信息

#### 字段说明

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

#### 示例数据

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

---

### industry_constituent - 行业指数成分股表

#### 概述

`industry_constituent` 表存储行业指数的成分股信息，记录每个指数包含哪些股票以及纳入/剔除日期。

#### 表结构

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

#### 唯一索引

- `uk_industry_constituent`: (source, index_code, con_code, in_date)

#### B-tree 索引

- `idx_ind_const_index`: (index_code)
- `idx_ind_const_code`: (con_code)
- `idx_ind_const_in_date`: (in_date)

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_constituent(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.2 行业指数成分股

#### 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| INDEX_CODE | string | 指数代码 | - |
| CON_CODE | string | 成份股代码 | 纯代码 |
| INDATE | string | 纳入日期 | YYYY-MM-DD 格式 |
| OUTDATE | string | 剔除日期 | YYYY-MM-DD 格式，未剔除时为空 |
| INDEX_NAME | string | 指数名称 | - |

#### 示例数据

```json
{
  "INDEX_CODE": "801010",
  "CON_CODE": "000001",
  "INDATE": "2024-01-01",
  "OUTDATE": "",
  "INDEX_NAME": "申万农林牧渔"
}
```

---

### industry_weight - 行业指数成分股日权重表

#### 概述

`industry_weight` 表存储行业指数成分股的每日权重数据。

#### 表结构

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

#### 唯一索引

- `uk_industry_weight`: (source, index_code, con_code, trade_date)

#### B-tree 索引

- `idx_ind_weight_index`: (index_code)
- `idx_ind_weight_code`: (con_code)
- `idx_ind_weight_date`: (trade_date)

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_weight(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.3 行业指数成分股日权重

#### 字段说明

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| WEIGHT | float | 权重 | - |
| CON_CODE | string | 成份股代码 | - |
| TRADE_DATE | string | 交易日期 | YYYY-MM-DD 格式 |
| INDEX_CODE | string | 指数代码 | - |

#### 示例数据

```json
{
  "INDEX_CODE": "801010",
  "CON_CODE": "000001",
  "TRADE_DATE": "2024-06-15",
  "WEIGHT": 3.25
}
```

---

### industry_daily - 行业指数日行情表

#### 概述

`industry_daily` 表存储行业指数的每日行情数据，包括 OHLCV、市值、PE/PB 等指标。

#### 表结构

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

#### 唯一索引

- `uk_industry_daily`: (source, index_code, trade_date)

#### B-tree 索引

- `idx_ind_daily_index`: (index_code)
- `idx_ind_daily_date`: (trade_date)

#### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_industry_daily(code_list)`
- **数据类别**: 3.5.13 行业指数数据 → 3.5.13.4 行业指数日行情

#### 字段说明

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

#### 示例数据

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

#### 查询示例

```sql
-- 查询某行业指数的最新成分股
SELECT ic.con_code, ic.in_date, ic.out_date, ibi.index_name
FROM industry_constituent ic
JOIN industry_base_info ibi ON ic.index_code = ibi.index_code
WHERE ic.index_code = '801010' AND (ic.out_date = '' OR ic.out_date IS NULL)
ORDER BY ic.in_date DESC;

-- 查询某指数的日行情
SELECT * FROM industry_daily
WHERE index_code = '801010' AND trade_date >= '2024-01-01'
ORDER BY trade_date DESC;

-- 查询某日期的成分股权重
SELECT iw.con_code, iw.weight, iw.trade_date
FROM industry_weight iw
WHERE iw.index_code = '801010' AND iw.trade_date = '2024-06-15'
ORDER BY iw.weight DESC;
```

---

## 待完善内容

- [x] corporate_action 表数据描述（已完成：dividend, right_issue, bs_dividend）
- [x] financial_statement 表数据描述（已完成：balance_sheet, income, cashflow, profit_express, profit_notice）
- [x] 行业指数数据表描述（已完成：industry_base_info, industry_constituent, industry_weight, industry_daily）
- [x] adjust_factor 表数据描述（已完成：baostock query_adjust_factor）
- [ ] bars 表数据描述
- [ ] security_registry 表数据描述
- [ ] 其他数据表的详细描述
- [ ] 数据质量校验规则
- [ ] 数据刷新计划

---

*文档最后更新: 2026-05-22*
