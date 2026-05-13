# financial_statement - 财务报表数据表

## 概述

`financial_statement` 表存储上市公司的各类财务报表数据，包括资产负债表、利润表、现金流量表、业绩快报和业绩预告。数据来源于 AmazingData 的"财务数据"类别。

## 表结构

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

## 唯一索引

- `uk_fin_stmt`: (source, symbol, market, statement_type, reporting_period, report_type, statement_code)

## B-tree 索引

- `idx_fs_symbol_type`: (symbol, statement_type)
- `idx_fs_report_period`: (reporting_period)
- `idx_fs_ann_date`: (ann_date) WHERE ann_date != ''
- `idx_fs_comp_type`: (comp_type_code) WHERE comp_type_code > 0

## GIN 索引

- `idx_fs_data_gin`: (data_json) - 支持高效的 JSONB 查询（@>, ?, ?| 操作符）

## statement_type 报表类型

| 值 | 说明 | 数据来源 |
|----|------|----------|
| balance_sheet | 资产负债表 | AmazingData - get_balance_sheet() |
| income | 利润表 | AmazingData - get_income() |
| cashflow | 现金流量表 | AmazingData - get_cash_flow() |
| profit_express | 业绩快报 | AmazingData - get_profit_express() |
| profit_notice | 业绩预告 | AmazingData - get_profit_notice() |

## comp_type_code 公司类型代码

| 值 | 说明 |
|----|------|
| 1 | 非金融类 |
| 2 | 银行 |
| 3 | 保险 |
| 4 | 证券 |

---

## 1. balance_sheet - 资产负债表

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_balance_sheet(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.1 资产负债表

### data_json 字段结构

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

### 示例数据

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

## 2. cashflow - 现金流量表

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_cash_flow(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.2 现金流量表

### data_json 字段结构

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
| TOT_BAL_CASH_INFLOW_OPER_ACT | double | 经营活动现金流入差额 | - |
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

### 示例数据

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

## 3. income - 利润表

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_income(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.3 利润表

### data_json 字段结构

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

### 示例数据

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

## 4. profit_express - 业绩快报

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_profit_express(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.4 业绩快报

### data_json 字段结构

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

### 示例数据

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

## 5. profit_notice - 业绩预告

### 数据来源

- **数据源**: AmazingData
- **接口函数**: `info_data_object.get_profit_notice(code_list)`
- **数据类别**: 3.5.5 财务数据 → 3.5.5.5 业绩预告

### data_json 字段结构

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

### 业绩预告类型代码 (P_TYPECODE)

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

### 示例数据

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

```sql
-- 查询某股票的所有资产负债表
SELECT * FROM financial_statement
WHERE symbol = '000001' AND statement_type = 'balance_sheet'
ORDER BY reporting_period DESC;

-- 查询某年度的所有利润表
SELECT * FROM financial_statement
WHERE statement_type = 'income' AND report_type LIKE '%2023%'
ORDER BY ann_date DESC;
```

---

*文档最后更新: 2026-05-12*
