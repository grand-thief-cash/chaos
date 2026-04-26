# 财务数据字段手册

> 自动生成自 `artemis/consts/field_catalog.py`，更新日期：2026-04-26

本文档列出了所有通过 AmazingData SDK 下载并存储到 PhoenixA 数据库的字段。
数据以 JSON 格式存储在 `data_json` 列中，下面按数据域和数据类型分类。

---

## 数据存储结构

| 数据域 | PhoenixA 表 | 类型字段 | API 前缀 |
|--------|------------|---------|----------|
| 财务报表 | `financial_statement` | `statement_type` | `/api/v2/financial` |
| 公司行为 | `corporate_action` | `action_type` | `/api/v2/corporate-action` |

### 结构化字段（非 data_json）

**financial_statement 表：**

| 字段 | 说明 | 类型 |
|------|------|------|
| `source` | 数据来源 (amazing_data) | varchar(32) |
| `symbol` | 证券代码 | varchar(32) |
| `market` | 市场 (zh_a) | varchar(16) |
| `statement_type` | 报表类型 | varchar(32) |
| `reporting_period` | 报告期 YYYYMMDD | varchar(10) |
| `report_type` | 报告期名称 (1=Q1, 2=H1, 3=Q3, 4=Annual) | varchar(32) |
| `statement_code` | 报表类型代码 (1=合并报表, 6=母公司报表...) | varchar(32) |
| `security_name` | 证券简称 | varchar(128) |
| `ann_date` | 公告日期 | varchar(10) |
| `actual_ann_date` | 实际公告日期 | varchar(10) |
| `comp_type_code` | 公司类型 (1非金融 2银行 3保险 4证券) | int |

**corporate_action 表：**

| 字段 | 说明 | 类型 |
|------|------|------|
| `source` | 数据来源 | varchar(32) |
| `symbol` | 证券代码 | varchar(32) |
| `market` | 市场 | varchar(16) |
| `action_type` | 行为类型 (dividend/right_issue) | varchar(32) |
| `report_period` | 分红/配股年度 | varchar(10) |
| `ann_date` | 公告日期 | varchar(10) |
| `progress_code` | 方案进度代码 | varchar(8) |

---

## 1. 财务报表 (financial_statement)

### 1.1 资产负债表 (balance_sheet)

SDK 接口：`get_balance_sheet` | 调度：每周六 06:00

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `TOTAL_ASSETS` | 资产总计 | float | |
| `TOTAL_LIAB` | 负债合计 | float | |
| `TOTAL_CUR_ASSETS` | 流动资产合计 | float | |
| `TOTAL_CUR_LIAB` | 流动负债合计 | float | |
| `TOT_NONCUR_ASSETS` | 非流动资产合计 | float | |
| `TOTAL_NONCUR_LIAB` | 非流动负债合计 | float | |
| `TOTAL_LIAB_SHARE_EQUITY` | 负债及股东权益总计 | float | |
| `TOT_SHARE_EQUITY_EXCL_MIN_INT` | 股东权益合计(不含少数股东权益) | float | |
| `TOT_SHARE_EQUITY_INCL_MIN_INT` | 股东权益合计(含少数股东权益) | float | |
| `CURRENCY_CAP` | 货币资金 | float | |
| `TRADING_FINASSETS` | 交易性金融资产 | float | |
| `NOTES_RECEIVABLE` | 应收票据 | float | |
| `ACCT_RECEIVABLE` | 应收账款 | float | |
| `ACC_RECEIVABLE` | 应收票据及应收账款 | float | |
| `PREPAYMENT` | 预付款项 | float | |
| `OTHER_RECEIVABLE` | 其他应收款 | float | |
| `INV` | 存货 | float | |
| `OTHER_CUR_ASSETS` | 其他流动资产 | float | |
| `FIXED_ASSETS` | 固定资产 | float | |
| `CONST_IN_PROC` | 在建工程 | float | |
| `INTANGIBLE_ASSETS` | 无形资产 | float | |
| `GOODWILL` | 商誉 | float | |
| `LT_EQUITY_INV` | 长期股权投资 | float | |
| `DEFERRED_TAX_ASSETS` | 递延所得税资产 | float | |
| `OTH_NONCUR_ASSETS` | 其他非流动资产 | float | |
| `ST_BORROWING` | 短期借款 | float | |
| `NOTES_PAYABLE` | 应付票据 | float | |
| `ACCT_PAYABLE` | 应付账款 | float | |
| `ADV_RECEIPT` | 预收款项 | float | |
| `CONT_LIABILITIES` | 合同负债 | float | 单位（元） |
| `EMPL_PAY_PAYABLE` | 应付职工薪酬 | float | |
| `TAX_PAYABLE` | 应交税费 | float | |
| `NONCUR_LIAB_DUE_WITHIN_1Y` | 一年内到期的非流动负债 | float | |
| `LT_LOAN` | 长期借款 | float | |
| `BONDS_PAYABLE` | 应付债券 | float | |
| `LEASE_LIABILITY` | 租赁负债 | float | |
| `DEFERRED_TAX_LIAB` | 递延所得税负债 | float | |
| `CAP_STOCK` | 股本 | float | 金额（元），公布值 |
| `CAP_RESV` | 资本公积金 | float | |
| `SURPLUS_RESV` | 盈余公积金 | float | |
| `UNDISTRIBUTED_PRO` | 未分配利润 | float | |
| `MINORITY_EQUITY` | 少数股东权益 | float | |
| `TOT_SHARE` | 期末总股本 | float | 单位（股） |
| `USE_RIGHT_ASSETS` | 使用权资产 | float | |
| `INV_REALESTATE` | 投资性房地产 | float | |
| ... | *(共 140+ 字段，完整列表见 field_catalog.py)* | | |

### 1.2 利润表 (income)

SDK 接口：`get_income` | 调度：每周六 07:00

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `OPERA_REV` | 营业收入 | float | |
| `TOT_OPERA_REV` | 营业总收入 | float | |
| `TOT_OPERA_COST` | 营业总成本 | float | |
| `LESS_OPERA_COST` | 减:营业成本 | float | |
| `LESS_SELLING_EXP` | 减:销售费用 | float | |
| `LESS_ADMIN_EXP` | 减:管理费用 | float | |
| `LESS_FIN_EXP` | 减:财务费用 | float | |
| `RD_EXP` | 研发费用 | float | |
| `LESS_ASSETS_IMPAIR_LOSS` | 减:资产减值损失 | float | |
| `CREDIT_IMPAIR_LOSS` | 信用减值损失 | float | |
| `PLUS_NET_INV_INC` | 加:投资净收益 | float | |
| `PLUS_NET_GAIN_CHG_FV` | 加:公允价值变动净收益 | float | |
| `OPERA_PROFIT` | 营业利润 | float | |
| `TOTAL_PROFIT` | 利润总额 | float | |
| `INCOME_TAX` | 所得税 | float | |
| `NET_PRO_INCL_MIN_INT_INC` | 净利润(含少数股东损益) | float | |
| `NET_PRO_EXCL_MIN_INT_INC` | 净利润(不含少数股东损益) | float | |
| `BASIC_EPS` | 基本每股收益 | float | |
| `DILUTED_EPS` | 稀释每股收益 | float | |
| `EBIT` | 息税前利润 | float | |
| `EBITDA` | 息税折旧摊销前利润 | float | |
| `OTH_INCOME` | 其他收益 | float | |
| `GAIN_DISPOSAL_ASSETS` | 资产处置收益 | float | |
| `TOT_COMPRE_INC` | 综合收益总额 | float | |
| `NET_PRO_AFTER_DED_NR_GL` | 扣除非经常性损益后净利润 | float | |

### 1.3 现金流量表 (cashflow)

SDK 接口：`get_cash_flow` | 调度：每周六 06:30

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `CASH_RECP_SG_AND_RS` | 销售商品、提供劳务收到的现金 | float | |
| `CASH_PAY_GOODS_SERVICES` | 购买商品、接受劳务支付的现金 | float | |
| `CASH_PAY_EMPLOYEE` | 支付给职工以及为职工支付的现金 | float | |
| `PAY_ALL_TAX` | 支付的各项税费 | float | |
| `NET_CASH_FLOWS_OPERA_ACT` | 经营活动产生的现金流量净额 | float | |
| `CASH_PAID_INV` | 投资支付的现金 | float | |
| `CASH_PAID_PUR_CONST_FIOLTA` | 购建固定资产、无形资产和其他长期资产支付的现金 | float | |
| `NET_CASH_FLOWS_INV_ACT` | 投资活动产生的现金流量净额 | float | |
| `CASH_RECE_BORROW` | 取得借款收到的现金 | float | |
| `CASH_PAY_FOR_DEBT` | 偿还债务支付的现金 | float | |
| `CASH_PAY_DIST_DIV_PRO_INT` | 分配股利、利润或偿付利息支付的现金 | float | |
| `NET_CASH_FLOWS_FIN_ACT` | 筹资活动产生的现金流量净额 | float | |
| `NET_INCR_CASH_AND_CASH_EQU` | 现金及现金等价物净增加额 | float | |
| `END_BAL_CASH_CASH_EQU` | 期末现金及现金等价物余额 | float | |
| `FREE_CASH_FLOW` | 企业自由现金流量 | float | |
| `NET_PROFIT` | 净利润 | float | |
| `DEPRE_FA_OGA_PBA` | 固定资产折旧、油气资产折耗、生产性生物资产折旧 | float | |

### 1.4 业绩快报 (profit_express)

SDK 接口：`get_profit_express` | 调度：每周六 07:30

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `TOTAL_ASSETS` | 总资产(元) | float | |
| `NET_PRO_EXCL_MIN_INT_INC` | 净利润(元) | float | |
| `TOT_OPERA_REV` | 营业总收入(元) | float | |
| `TOTAL_PROFIT` | 利润总额(元) | float | |
| `OPERA_PROFIT` | 营业利润(元) | float | |
| `EPS_BASIC` | 每股收益基本(元) | float | |
| `TOT_SHARE_EQU_EXCL_MIN_INT` | 股东权益合计(不含少数股东权益)(元) | float | |
| `ROE_WEIGHTED` | 净资产收益率-加权(%) | float | |
| `PERFORMANCE_SUMMARY` | 业绩简要说明 | str | |
| `YOY_GR_NET_PROFIT_PARENT` | 同比增长率:归属母公司股东的净利润(%) | float | |
| `YOY_GR_GROSS_REV` | 同比增长率:营业总收入(%) | float | |

### 1.5 业绩预告 (profit_notice)

SDK 接口：`get_profit_notice` | 调度：每周六 08:00

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `P_TYPECODE` | 业绩预告类型代码 | str | 1不确定 2略减 3略增 4扭亏 5其他 6首亏 7续亏 8续盈 9预减 10预增 11持平 |
| `P_CHANGE_MAX` | 预告净利润变动幅度上限(%) | float | |
| `P_CHANGE_MIN` | 预告净利润变动幅度下限(%) | float | |
| `NET_PROFIT_MAX` | 预告净利润上限(万元) | float | |
| `NET_PROFIT_MIN` | 预告净利润下限(万元) | float | |
| `FIRST_ANN_DATE` | 首次公告日 | str | |
| `P_NUMBER` | 公布次数 | float | |
| `P_REASON` | 业绩变动原因 | str | |
| `P_SUMMARY` | 业绩预告摘要 | str | |
| `P_NET_PARENT_FIRM` | 上年同期归母净利润 | float | |

---

## 2. 公司行为 (corporate_action)

### 2.1 分红 (dividend)

SDK 接口：`get_dividend` | 调度：每周六 08:30

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `DVD_PER_SHARE_STK` | 每股送转 | float | |
| `DVD_PER_SHARE_PRE_TAX_CASH` | 每股派息(税前)(元) | float | |
| `DVD_PER_SHARE_AFTER_TAX_CASH` | 每股派息(税后)(元) | float | |
| `DATE_EQY_RECORD` | 股权登记日 | str | |
| `DATE_EX` | 除权除息日 | str | |
| `DATE_DVD_PAYOUT` | 派息日 | str | |
| `DIV_PRELANDATE` | 预案公告日 | str | 董事会预案公告日期 |
| `DIV_SMTGDATE` | 股东大会公告日 | str | |
| `DATE_DVD_ANN` | 分红实施公告日 | str | |
| `DIV_BASESHARE` | 基准股本(万股) | float | |
| `CURRENCY_CODE` | 货币代码 | str | |
| `IS_CHANGED` | 方案是否变更 | int | 1:有变更 0:未变更 |
| `DIV_BONUSRATE` | 每股送股比例 | float | |
| `DIV_CONVERSEDRATE` | 每股转增比例 | float | |
| `DIV_TARGET` | 分红对象 | str | |

### 2.2 配股 (right_issue)

SDK 接口：`get_right_issue` | 调度：每周六 09:00

| 字段名 | 中文名 | 类型 | 备注 |
|--------|--------|------|------|
| `PRICE` | 配股价格(元) | float | |
| `RATIO` | 配股比例 | float | |
| `AMT_PLAN` | 配股计划数量(万股) | float | |
| `AMT_REAL` | 配股实际数量(万股) | float | |
| `COLLECTION_FUND` | 募集资金(元) | float | |
| `SHAREB_REG_DATE` | 股权登记日 | str | |
| `EX_DIVIDEND_DATE` | 除权日 | str | |
| `LISTED_DATE` | 配股上市日 | str | |
| `RIGHTSISSUE_CODE` | 配售代码 | str | |
| `RIGHTSISSUE_NAME` | 配股简称 | str | |
| `RATIO_DENOMINATOR` | 配股比例分母 | float | |
| `RATIO_MOLECULAR` | 配股比例分子 | float | |
| `EXPECTED_FUND_RAISING` | 预计募集资金(元) | float | |

---

## 3. 查询示例

### 3.1 通过 PhoenixA API 查询

```bash
# 查询某只股票的资产负债表
GET /api/v2/financial/amazing_data/balance_sheet?symbol=000001.SZ&period_start=20230101

# 查询分红数据
GET /api/v2/corporate-action/amazing_data/dividend?symbol=600519.SH

# 发现某种报表实际存储了哪些字段（动态查询）
GET /api/v2/schema/fields?domain=financial_statement&type=balance_sheet
```

### 3.2 在 Artemis 中使用字段目录

```python
from artemis.consts.field_catalog import get_fields, get_field_names, CATALOG

# 获取资产负债表所有字段
fields = get_fields("financial_statement", "balance_sheet")
for f in fields:
    print(f"{f.name:40s} {f.cn_desc}")

# 获取字段名列表（用于 pandas 列筛选）
names = get_field_names("financial_statement", "income")

# 查看所有可用域和类型
for domain, meta in CATALOG.items():
    print(f"\n{meta.cn_name} ({domain}):")
    for dtype in meta.types:
        count = len(meta.types[dtype])
        print(f"  {dtype}: {count} fields")
```

---

## 4. 数据更新频率

| 数据类型 | 调度表达式 | 说明 |
|----------|-----------|------|
| balance_sheet | `0 0 6 ? * SAT` | 每周六 06:00 |
| cashflow | `0 30 6 ? * SAT` | 每周六 06:30 |
| income | `0 0 7 ? * SAT` | 每周六 07:00 |
| profit_express | `0 30 7 ? * SAT` | 每周六 07:30 |
| profit_notice | `0 0 8 ? * SAT` | 每周六 08:00 |
| dividend | `0 30 8 ? * SAT` | 每周六 08:30 |
| right_issue | `0 0 9 ? * SAT` | 每周六 09:00 |

