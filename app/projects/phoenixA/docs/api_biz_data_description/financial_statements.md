# Financial Statements API - 财务报表数据

## 概述

提供上市公司财务报表数据查询，包括资产负债表、利润表、现金流量表、业绩快报、业绩预告。

## API 端点

| 方法 | 端点 | 说明 |
|------|-------|------|
| GET | `/api/v2/financial/{source}/{statement_type}` | 查询财务数据 |

## 查询参数

| 参数名 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| symbols | string | 否 | 证券代码列表（逗号分隔） |
| start_date | string | 否 | 起始报告期（格式 YYYY-MM-DD） |
| end_date | string | 否 | 截止报告期（格式 YYYY-MM-DD） |
| report_type | string | 否 | 按报告期名称过滤（年报、半年报、季报） |
| ann_date_before | string | 否 | 公告日期前过滤（Point-in-Time 查询） |
| reporting_periods | string | 否 | 报告期列表（逗号分隔，用于 TTM 计算） |
| **fields** | **string** | **否** | **返回字段列表（逗号分隔），支持常规字段和 JSONB 嵌套字段（见下文说明）** |
| limit | integer | 否 | 返回数量限制 |
| offset | integer | 否 | 分页偏移量 |

### fields 参数说明

`fields` 参数允许指定返回的字段，减少数据传输量。

**格式**: `fields=字段1,字段2,字段3`

**支持的字段类型**:
1. **常规字段**: 直接使用表字段名，如 `symbol`, `reporting_period`, `ann_date`
2. **JSONB 嵌套字段**: 使用 `data_json.字段名` 格式，如 `data_json.TOTAL_ASSETS`, `data_json.DVD_PER_SHARE_PRE_TAX_CASH`

**示例**:
- `fields=symbol,reporting_period,ann_date` - 只返回基本字段
- `fields=symbol,data_json.TOTAL_ASSETS,data_json.TOT_OPERA_REV` - 返回特定 JSONB 字段
- `fields=data_json.DVD_PER_SHARE_PRE_TAX_CASH,data_json.DATE_EQY_RECORD` - 返回分红相关 JSONB 字段

## 路径参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| source | string | 数据源（amazing_data, baostock 等） |
| statement_type | string | 报表类型（balance_sheet, income, cashflow, profit_express, profit_notice） |

## statement_type 说明

| 值 | 说明 |
|----|------|
| balance_sheet | 资产负债表 |
| income | 利润表 |
| cashflow | 现金流量表 |
| profit_express | 业绩快报 |
| profit_notice | 业绩预告 |

## 响应格式

```json
{
  "data": [...],
  "total": 1000
}
```

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| data | array | 财务报表对象数组 |
| total | integer | 总记录数 |

## 响应数据

### 财务报表对象

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| id | integer | 主键 ID |
| source | string | 数据源 |
| symbol | string | 证券代码（纯代码） |
| market | string | 市场标识 |
| statement_type | string | 报表类型 |
| report_period | string | 报告期（格式 YYYY-MM-DD） |
| report_type | string | 报告期名称 |
| statement_code | string | 报表类型代码 |
| security_name | string | 证券简称 |
| ann_date | string | 公告日期（格式 YYYY-MM-DD） |
| actual_ann_date | string | 实际公告日期（格式 YYYY-MM-DD） |
| comp_type_code | integer | 公司类型代码 |
| data_json | object | 财务详情数据（内容随 statement_type 而不同） |
| created_at | string | 创建时间（ISO 8601 格式） |
| updated_at | string | 更新时间（ISO 8601 格式） |

## data_json 字段说明

### balance_sheet（资产负债表）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| STATEMENT_TYPE | string | 报表类型 |
| REPORT_TYPE | string | 报告期名称 |
| REPORTING_PERIOD | string | 报告期 |
| ANN_DATE | string | 公告日期 |
| ACTUAL_ANN_DATE | string | 实际公告日期 |
| ACC_PAYABLE | float64 | 应付票据及应付账款（元） |
| ACC_RECEIVABLE | float64 | 应收票据及应收账款（元） |
| ACC_RECEIVABLES | float64 | 应收款项（元） |
| ACCRUED_EXP | float64 | 预提费用（元） |
| ACCT_PAYABLE | float64 | 应付账款（元） |
| ACCT_RECEIVABLE | float64 | 应收账款（元） |
| ACT_TRADING_SEC | float64 | 代理买卖证券款（元） |
| ACT_UW_SEC | float64 | 代理承销证券款（元） |
| ADV_PREM | float64 | 预收保费（元） |
| ADV_RECEIPT | float64 | 预收款项（元） |
| AGENCY_ASSETS | float64 | 代理业务资产（元） |
| AGENCY_BUSINESS_LIAB | float64 | 代理业务负债（元） |
| ANTICIPATION_LIAB | float64 | 预计负债（元） |
| ASSET_DEP_FUNDS_OTHER_FIN_INST | float64 | 存放同业和其它金融机构款项（元） |
| BONDS_PAYABLE | float64 | 应付债券（元） |
| CAP_RESV | float64 | 资本公积金（元） |
| CAP_STOCK | float64 | 股本（金额，元） |
| CASH_CENTRAL_BANK_DEPOSITS | float64 | 现金及存放中央银行款项（元） |
| CED_INSUR_CONT_RESERVES_RCV | float64 | 应收分保合同准备金（元） |
| CLAIMS_PAYABLE | float64 | 应付赔付款（元） |
| CLIENTS_FUND_DEPOSIT | float64 | 客户资金存款（元） |
| CLIENTS_RESERVES | float64 | 客户备付金（元） |
| CNVD_DIFF_FOREIGN_CURR_STAT | float64 | 外币报表折算差额（元） |
| COMP_TYPE_CODE | integer | 公司类型代码（1:非金融 2:银行 3:保险 4:证券） |
| CONST_IN_PROC | float64 | 在建工程（元） |
| CONST_IN_PROC_TOTAL | float64 | 在建工程（合计，元） |
| CONSUMP_BIO_ASSETS | float64 | 消耗性生物资产（元） |
| CONT_ASSETS | float64 | 合同资产（元） |
| CONT_LIABILITIES | float64 | 合同负债（元） |
| CURRENCY_CAP | float64 | 货币资金（元） |
| CURRENCY_CODE | string | 货币代码 |
| DEBT_INV | float64 | 债权投资（元） |
| DEFERRED_INC_NONCUR_LIAB | float64 | 递延收益-非流动负债（元） |
| DEFERRED_INCOME | float64 | 递延收益（元） |
| DEFERRED_TAX_ASSETS | float64 | 递延所得税资产（元） |
| DEFERRED_TAX_LIAB | float64 | 递延所得税负债（元） |
| DEP_RECEIVED_IB_DEP | float64 | 吸收存款及同业存放（元） |
| DEPOSIT_CAP_RECOG | float64 | 存出资本保证金（元） |
| DEPOSIT_TAKING | float64 | 吸收存款（元） |
| DEPOSITS_RECEIVED | float64 | 存入保证金（元） |
| DER_FIN_ASSETS | float64 | 衍生金融资产（元） |
| DERI_FIN_LIAB | float64 | 衍生金融负债（元） |
| DEVELOP_EXP | float64 | 开发支出（元） |
| DISPOSAL_FIX_ASSET | float64 | 固定资产清理（元） |
| DIV_PAYABLE | float64 | 应付股利（元） |
| DIV_RECEIVABLE | float64 | 应收股利（元） |
| EMPL_PAY_PAYABLE | float64 | 应付职工薪酬（元） |
| ENGIN_MAT | float64 | 工程物资（元） |
| FIN_ASSETS_AVA_FOR_SALE | float64 | 可供出售金融资产（元） |
| FIN_ASSETS_COST_SHARING | float64 | 以摊余成本计量的金融资产（元） |
| FIN_ASSETS_FAIR_VALUE | float64 | 以公允价值计量且其变动计入其他综合收益的金融资产（元） |
| FIXED_ASSETS | float64 | 固定资产（元） |
| FIXED_ASSETS_TOTAL | float64 | 固定资产（合计，元） |
| FIXED_TERM_DEPOSIT | float64 | 定期存款（元） |
| GOODWILL | float64 | 商誉（元） |
| GUA_DEPOSITS_PAID | float64 | 存出保证金（元） |
| GUA_PLEDGE_LOANS | float64 | 保户质押贷款（元） |
| HOLD_ASSETS_FOR_SALE | float64 | 持有待售的资产（元） |
| HOLD_TO_MTY_INV | float64 | 持有至到期投资（元） |
| INC_PLEDGE_LOAN | float64 | 其中:质押借款（元） |
| INCL_TRADING_SEAT_FEES | float64 | 其中:交易席位费（元） |
| IND_ACCT_ASSETS | float64 | 独立账户资产（元） |
| IND_ACCT_LIAB | float64 | 独立账户负债（元） |
| INSURED_DEPOSIT_IN | float64 | 保户储金及投资款（元） |
| INSURED_DIV_PAYABLE | float64 | 应付保单红利（元） |
| INT_RECEIVABLE | float64 | 应收利息（元） |
| INTANGIBLE_ASSETS | float64 | 无形资产（元） |
| INTEREST_PAYABLE | float64 | 应付利息（元） |
| INV | float64 | 存货（元） |
| INV_REALESTATE | float64 | 投资性房地产（元） |
| LEASE_LIABILITY | float64 | 租赁负债（元） |
| LEND_FUNDS | float64 | 融出资金（元） |
| LENDING_FUNDS | float64 | 拆出资金（元） |
| LESS_TREASURY_STK | float64 | 减:库存股（元） |
| LIA_HFS | float64 | 持有待售的负债（元） |
| LIAB_DEP_FUNDS_OTHER_FIN_INST | float64 | 同业和其它金融机构存放款项（元） |
| LIFE_INSUR_RESV | float64 | 寿险责任准备金（元） |
| LOAN_CENTRAL_BANK | float64 | 向中央银行借款（元） |
| LOANS_AND_ADVANCES | float64 | 发放贷款及垫款（元） |
| LOANS_FROM_OTHER_BANKS | float64 | 拆入资金（元） |
| LT_DEFERRED_EXP | float64 | 长期待摊费用（元） |
| LT_EMP_COMP_PAY | float64 | 长期应付职工薪酬（元） |
| LT_EQUITY_INV | float64 | 长期股权投资（元） |
| LT_HEALTH_INSUR_RESV | float64 | 长期健康险责任准备金（元） |
| LT_LOAN | float64 | 长期借款（元） |
| LT_PAYABLE | float64 | 长期应付款（元） |
| LT_PAYABLE_TOTAL | float64 | 长期应付款（合计，元） |
| LT_RECEIVABLES | float64 | 长期应收款（元） |
| MINORITY_EQUITY | float64 | 少数股东权益（元） |
| NOM_RISKS_PREP | float64 | 一般风险准备（元） |
| NONCUR_ASSETS_DUE_WITHIN_1Y | float64 | 一年内到期的非流动资产（元） |
| NONCUR_LIAB_DUE_WITHIN_1Y | float64 | 一年内到期的非流动负债（元） |
| NOTES_PAYABLE | float64 | 应付票据（元） |
| NOTES_RECEIVABLE | float64 | 应收票据（元） |
| OIL_AND_GAS_ASSETS | float64 | 油气资产（元） |
| OTH_COMP_INCOME | float64 | 其他综合收益（元） |
| OTH_EQUITY_TOOLS | float64 | 其他权益工具（元） |
| OTH_EQUITY_TOOLS_PRE_SHR | float64 | 其他权益工具:优先股（元） |
| OTH_NONCUR_ASSETS | float64 | 其他非流动资产（元） |
| OTHER_ASSETS | float64 | 其他资产（元） |
| OTHER_CUR_ASSETS | float64 | 其他流动资产（元） |
| OTHER_CUR_LIAB | float64 | 其他流动负债（元） |
| OTHER_DEBT_INV | float64 | 其他债权投资（元） |
| OTHER_EQUITY_INV | float64 | 其他权益工具投资（元） |
| OTHER_LIAB | float64 | 其他负债（元） |
| OTHER_NONCUR_FIN_ASSETS | float64 | 其他非流动金融资产（元） |
| OTHER_NONCUR_LIAB | float64 | 其他非流动负债（元） |
| OTHER_PAYABLE | float64 | 其他应付款（元） |
| OTHER_PAYABLE_TOTAL | float64 | 其他应付款（合计，元） |
| OTHER_RCV_TOTAL | float64 | 其他应收款（合计，元） |
| OTHER_RECEIVABLE | float64 | 其他应收款（元） |
| OTHER_SUSTAIN_BONDS | float64 | 其他权益工具:永续债（元） |
| OUT_LOSS_RESV | float64 | 未决赔款准备金（元） |
| PAYABLE | float64 | 应付款项（元） |
| PAYABLE_FOR_REINSURANCE | float64 | 应付分保账款（元） |
| PRECIOUS_METAL | float64 | 贵金属（元） |
| PREPAYMENT | float64 | 预付款项（元） |
| PROD_BIO_ASSETS | float64 | 生产性生物资产（元） |
| RCV_CED_CLAIM_RESV | float64 | 应收分保未决赔款准备金（元） |
| RCV_CED_LIFE_INSUR_RESV | float64 | 应收分保寿险责任准备金（元） |
| RCV_CED_LT_HEALTH_INSUR_RESV | float64 | 应收分保长期健康险责任准备金（元） |
| RCV_CED_UNEARNED_PREM_RESV | float64 | 应收分保未到期责任准备金（元） |
| RCV_FINANCING | float64 | 应收款项融资（元） |
| RCV_INV | float64 | 应收款项类投资（元） |
| RECEIVABLE_PREM | float64 | 应收保费（元） |
| RED_MON_CAP_FOR_SALE | float64 | 买入返售金融资产（元） |
| REINSURANCE_ACC_RCV | float64 | 应收分保账款（元） |
| RSRV_FUND_INSUR_CONT | float64 | 保险合同准备金（元） |
| SELL_REPO_FIN_ASSETS | float64 | 卖出回购金融资产款（元） |
| SERVICE_CHARGE_COMM_PAYABLE | float64 | 应付手续费及佣金（元） |
| SETTLE_FUNDS | float64 | 结算备付金（元） |
| SPE_ASSETS_BAL_DIFF | float64 | 资产差额（特殊报表科目）（元） |
| SPE_CUR_ASSETS_DIFF | float64 | 流动资产差额（特殊报表科目）（元） |
| SPE_CUR_LIAB_DIFF | float64 | 流动负债差额（特殊报表科目）（元） |
| SPE_LIAB_BAL_DIFF | float64 | 负债差额（特殊报表科目）（元） |
| SPE_LIAB_EQUITY_BAL_DIFF | float64 | 负债及股东权益差额（特殊报表项目）（元） |
| SPE_NONCUR_ASSETS_DIFF | float64 | 非流动资产差额（特殊报表科目）（元） |
| SPE_NONCUR_LIAB_DIFF | float64 | 非流动负债差额（特殊报表科目）（元） |
| SPE_SHARE_EQUITY_BAL_DIFF | float64 | 股东权益差额（特殊报表科目）（元） |
| SPECIAL_PAYABLE | float64 | 专项应付款（元） |
| SPECIAL_RESV | float64 | 专项储备（元） |
| ST_BONDS_PAYABLE | float64 | 应付短期债券（元） |
| ST_BORROWING | float64 | 短期借款（元） |
| ST_FIN_PAYABLE | float64 | 应付短期融资款（元） |
| SUBR_RCV | float64 | 应收代位追偿款（元） |
| SURPLUS_RESV | float64 | 盈余公积金（元） |
| TAX_PAYABLE | float64 | 应交税费（元） |
| TOT_ASSETS_BAL_DIFF | float64 | 资产差额（合计平衡项目）（元） |
| TOT_CUR_ASSETS_DIFF | float64 | 流动资产差额（合计平衡项目）（元） |
| TOT_CUR_LIAB_DIFF | float64 | 流动负债差额（合计平衡项目）（元） |
| TOT_LIAB_BAL_DIFF | float64 | 负债差额（合计平衡项目）（元） |
| TOT_LIAB_EQUITY_BAL_DIFF | float64 | 负债及股东权益差额（合计平衡项目）（元） |
| TOT_NONCUR_ASSETS | float64 | 非流动资产合计（元） |
| TOT_NONCUR_ASSETS_DIFF | float64 | 非流动资产差额（合计平衡项目）（元） |
| TOT_NONCUR_LIAB_DIFF | float64 | 非流动负债差额（合计平衡项目）（元） |
| TOT_SHARE | float64 | 期末总股本（股） |
| TOT_SHARE_EQUITY_BAL_DIFF | float64 | 股东权益差额（合计平衡项目）（元） |
| TOT_SHARE_EQUITY_EXCL_MIN_INT | float64 | 股东权益合计（不含少数股东权益）（元） |
| TOT_SHARE_EQUITY_INCL_MIN_INT | float64 | 股东权益合计（含少数股东权益）（元） |
| TOTAL_ASSETS | float64 | 资产总计（元） |
| TOTAL_CUR_ASSETS | float64 | 流动资产合计（元） |
| TOTAL_CUR_LIAB | float64 | 流动负债合计（元） |
| TOTAL_LIAB | float64 | 负债合计（元） |
| TOTAL_LIAB_SHARE_EQUITY | float64 | 负债及股东权益总计（元） |
| TOTAL_NONCUR_LIAB | float64 | 非流动负债合计（元） |
| TRADING_FIN_LIAB | float64 | 交易性金融负债（元） |
| TRADING_FINASSETS | float64 | 交易性金融资产（元） |
| UNAMORTIZED_EXP | float64 | 待摊费用（元） |
| UNCONFIRMED_INV_LOSS | float64 | 未确认的投资损失（元） |
| UNDISTRIBUTED_PRO | float64 | 未分配利润（元） |
| UNEARNED_PREM_RESV | float64 | 未到期责任准备金（元） |
| USE_RIGHT_ASSETS | float64 | 使用权资产（元） |

### cashflow（现金流量表）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| STATEMENT_TYPE | string | 报表类型 |
| REPORT_TYPE | string | 报告期名称 |
| REPORTING_PERIOD | string | 报告期 |
| ANN_DATE | string | 公告日期 |
| ACTUAL_ANN_DATE | string | 实际公告日期 |
| ABSORB_CASH_RECP_INV | float64 | 吸收投资收到的现金（元） |
| AMORT_INTAN_ASSETS | float64 | 无形资产摊销（元） |
| AMORT_LT_DEFERRED_EXP | float64 | 长期待摊费用摊销（元） |
| BEG_BAL_CASH_CASH_EQU | float64 | 期初现金及现金等价物余额（元） |
| CASH_END_BAL | float64 | 现金的期末余额（元） |
| CASH_FOR_CHARGE | float64 | 支付手续费的现金（元） |
| CASH_PAID_INSUR_POLICY | float64 | 支付保单红利的现金（元） |
| CASH_PAID_INV | float64 | 投资支付的现金（元） |
| CASH_PAID_PUR_CONST_FIOLTA | float64 | 购建固定资产、无形资产和其他长期资产支付的现金（元） |
| CASH_PAY_CLAIMS_OIC | float64 | 支付原保险合同赔付款项的现金（元） |
| CASH_PAY_DIST_DIV_PRO_INT | float64 | 分配股利、利润或偿付利息支付的现金（元） |
| CASH_PAY_EMPLOYEE | float64 | 支付给职工以及为职工支付的现金（元） |
| CASH_PAY_FOR_DEBT | float64 | 偿还债务支付的现金（元） |
| CASH_PAY_GOODS_SERVICES | float64 | 购买商品、接受劳务支付的现金（元） |
| CASH_RECE_BORROW | float64 | 取得借款收到的现金（元） |
| CASH_RECE_ISSUE_BONDS | float64 | 发行债券收到的现金（元） |
| CASH_RECP_INV_INCOME | float64 | 取得投资收益收到的现金（元） |
| CASH_RECP_PREM_OIC | float64 | 收到原保险合同保费取得的现金（元） |
| CASH_RECP_RECOV_INV | float64 | 收回投资收到的现金（元） |
| CASH_RECP_SG_AND_RS | float64 | 销售商品、提供劳务收到的现金（元） |
| COMP_TYPE_CODE | integer | 公司类型代码（1:非金融 2:银行 3:保险 4:证券） |
| CONV_CORP_BONDS_DUE_WITHIN_1Y | float64 | 一年内到期的可转换公司债券（元） |
| CONV_DEBT_INT_O_CAP | float64 | 债务转为资本（元） |
| CREDIT_IMPAIR_LOSS | float64 | 信用减值损失（元） |
| CURRENCY_CODE | string | 货币代码 |
| DECR_DEFER_INC_TAX_ASSETS | float64 | 递延所得税资产减少（元） |
| DECR_DEFERRED_EXPENSE | float64 | 待摊费用减少（元） |
| DECR_INVENTORY | float64 | 存货的减少（元） |
| DECR_OPERA_RECEIVABLE | float64 | 经营性应收项目的减少（元） |
| DEPRE_FA_OGA_PBA | float64 | 固定资产折旧、油气资产折耗、生产性生物资产折旧（元） |
| EFF_FX_FLUC_CASH | float64 | 汇率变动对现金的影响（元） |
| END_BAL_CASH_CASH_EQU | float64 | 期末现金及现金等价物余额（元） |
| FINANCIAL_EXP | float64 | 财务费用（元） |
| FIXED_ASSETS_F_IN_LEASE | float64 | 融资租入固定资产（元） |
| FREE_CASH_FLOW | float64 | 企业自由现金流量（元） |
| INCL_CASH_RECP_SAIMS | float64 | 其中:子公司吸收少数股东投资收到的现金（元） |
| INCL_DIV_PRO_PAID_SMS | float64 | 其中:子公司支付给少数股东的股利、利润（元） |
| INCR_ACCRUED_EXP | float64 | 预提费用增加（元） |
| INCR_DEFE_INC_TAX_LIAB | float64 | 递延所得税负债增加（元） |
| INCR_OPERA_PAYABLE | float64 | 经营性应付项目的增加（元） |
| IND_NET_CASH_FLOWS_OPERA_ACT | float64 | 间接法-经营活动产生的现金流量净额（元） |
| IND_NET_INCR_CASH_AND_EQU | float64 | 间接法-现金及现金等价物净增加额（元） |
| INV_LOSS | float64 | 投资损失（元） |
| IS_CALCULATION | integer | 是否计算报表（0:否 1:是） |
| LESS_OPEN_BAL_CASH | float64 | 减:现金的期初余额（元） |
| LESS_OPEN_BAL_CASH_EQU | float64 | 减:现金等价物的期初余额（元） |
| LOSS_DISP_FIOLTA | float64 | 处置固定、无形资产和其他长期资产的损失（元） |
| LOSS_FAIRVALUE_CHG | float64 | 公允价值变动损失（元） |
| LOSS_FIXED_ASSETS | float64 | 固定资产报废损失（元） |
| NET_CASH_FLOW_FIN_ACT | float64 | 筹资活动产生的现金流量净额（元） |
| NET_CASH_FLOW_INV_ACT | float64 | 投资活动产生的现金流量净额（元） |
| NET_CASH_FLOW_OPERA_ACT | float64 | 经营活动产生的现金流量净额（元） |
| NET_CASH_PAID_SOBU | float64 | 取得子公司及其他营业单位支付的现金净额（元） |
| NET_CASH_RECP_DISP_FIOLTA | float64 | 处置固定资产、无形资产和其他长期资产收回的现金净额（元） |
| NET_CASH_RECP_DISP_SOBU | float64 | 处置子公司及其他营业单位收到的现金净额（元） |
| NET_CASH_RECP_REINSU_BUS | float64 | 收到再保业务现金净额（元） |
| NET_INCR_BORR_FUND | float64 | 拆入资金净增加额（元） |
| NET_INCR_BORR_OFI | float64 | 向其他金融机构拆入资金净增加额（元） |
| NET_INCR_CASH_AND_CASH_EQU | float64 | 现金及现金等价物净增加额（元） |
| NET_INCR_CUS_LOAN_ADV | float64 | 客户贷款及垫款净增加额（元） |
| NET_INCR_DEP_CB_IB | float64 | 存放央行和同业款项净增加额（元） |
| NET_INCR_DEP_CUS_AND_IB | float64 | 客户存款和同业存放款项净增加额（元） |
| NET_INCR_DISM_CAPLE | float64 | 拆出资金净增加额（元） |
| NET_INCR_DISP_FAAS | float64 | 处置可供出售金融资产净增加额（元） |
| NET_INCR_DISP_TFA | float64 | 处置交易性金融资产净增加额（元） |
| NET_INCR_INSU_RED_SAVE | float64 | 保户储金净增加额（元） |
| NET_INCR_INT_AND_CHARGE | float64 | 收取利息和手续费净增加额（元） |
| NET_INCR_LOANS_CENTRAL_BANK | float64 | 向中央银行借款净增加额（元） |
| NET_INCR_PLEDGE_LOAN | float64 | 质押贷款净增加额（元） |
| NET_INCR_REPU_BUS_FUND | float64 | 回购业务资金净增加额（元） |
| NET_PROFIT | float64 | 净利润（元） |
| OTH_CASH_PAY_INV_ACT | float64 | 支付其他与投资活动有关的现金（元） |
| OTH_CASH_PAY_OPERA_ACT | float64 | 支付其他与经营活动有关的现金（元） |
| OTH_CASH_RECP_INV_ACT | float64 | 收到其他与投资活动有关的现金（元） |
| OTHER_ASSETS_IMPAIR_LOSS | float64 | 其他资产减值损失（元） |
| OTHER_CASH_PAY_FIN_ACT | float64 | 支付其他与筹资活动有关的现金（元） |
| OTHER_CASH_RECP_FIN_ACT | float64 | 收到其他与筹资活动有关的现金（元） |
| OTHER_CASH_RECP_OPER_ACT | float64 | 收到其他与经营活动有关的现金（元） |
| OTHERS | float64 | 其他（废弃）（元） |
| PAY_ALL_TAX | float64 | 支付的各项税费（元） |
| PLUS_ASSETS_DEPRE_PREP | float64 | 加:资产减值准备（元） |
| PLUS_END_BAL_CASH_EQU | float64 | 加:现金等价物的期末余额（元） |
| RECP_TAX_REFUND | float64 | 收到的税费返还（元） |
| SPE_BAL_CASH_INFLOW_FIN_ACT | float64 | 筹资活动现金流入差额（元） |
| SPE_BAL_CASH_INFLOW_INV_ACT | float64 | 投资活动现金流入差额（元） |
| SPE_BAL_CASH_INFLOW_OPERA_ACT | float64 | 经营活动现金流入差额（元） |
| SPE_BAL_CASH_OUTFLOW_FIN | float64 | 筹资活动现金流出差额（元） |
| SPE_BAL_CASH_OUTFLOW_INV | float64 | 投资活动现金流出差额（元） |
| SPE_BAL_CASH_OUTFLOW_OPERA | float64 | 经营活动现金流出差额（元） |
| SPE_BAL_NETCASH_INC_DIFF_IND | float64 | 间接法-现金净增加额差额（元） |
| SPE_BAL_NETCASH_INCR_DIFF | float64 | 现金净增加额差额（元） |
| SPE_BAL_NETCASH_OPERA_IND | float64 | 间接法-经营活动现金流量净额差额（元） |
| TOT_BAL_CASH_INFLOW_FIN_ACT | float64 | 筹资活动现金流入差额（元） |
| TOT_BAL_CASH_INFLOW_INV_ACT | float64 | 投资活动现金流入差额（元） |
| TOT_BAL_CASH_INFLOW_OPER_ACT | float64 | 经营活动现金流入差额（元） |
| TOT_BAL_CASH_OUTFLOW_FIN | float64 | 筹资活动现金流出差额（元） |
| TOT_BAL_CASH_OUTFLOW_INV | float64 | 投资活动现金流出差额（元） |
| TOT_BAL_CASH_OUTFLOW_OPERA | float64 | 经营活动现金流出差额（元） |
| TOT_BAL_NETCASH_FLOW_FIN | float64 | 筹资活动产生的现金流量净额差额（元） |
| TOT_BAL_NETCASH_FLOW_INV | float64 | 投资活动产生的现金流量净额差额（元） |
| TOT_BAL_NETCASH_FLOW_OPERA | float64 | 经营活动产生的现金流量净额差额（元） |
| TOT_BAL_NETCASH_INC_DIFF_IND | float64 | 间接法-现金净增加额差额（元） |
| TOT_BAL_NETCASH_INCR_DIFF | float64 | 现金净增加额差额（元） |
| TOT_BAL_NETCASH_OPERA_IND | float64 | 间接法-经营活动现金流量净额差额（元） |
| TOT_CASH_INFLOW_FIN_ACT | float64 | 筹资活动现金流入小计（元） |
| TOT_CASH_INFLOW_INV_ACT | float64 | 投资活动现金流入小计（元） |
| TOT_CASH_INFLOW_OPER_ACT | float64 | 经营活动现金流入小计（元） |
| TOT_CASH_OUTFLOW_FIN_ACT | float64 | 筹资活动现金流出小计（元） |
| TOT_CASH_OUTFLOW_INV_ACT | float64 | 投资活动现金流出小计（元） |
| TOT_CASH_OUTFLOW_OPER_ACT | float64 | 经营活动现金流出小计（元） |
| UNCONFIRMED_INV_LOSS | float64 | 未确认投资损失（元） |
| USE_RIGHT_ASSET_DEP | float64 | 使用权资产折旧（元） |

### income（利润表）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| STATEMENT_TYPE | string | 报表类型 |
| REPORT_TYPE | string | 报告期名称 |
| REPORTING_PERIOD | string | 报告期 |
| ANN_DATE | string | 公告日期 |
| ACTUAL_ANN_DATE | string | 实际公告日期 |
| AMORT_COST_FIN_ASSETS_EAR | float64 | 以摊余成本计量的金融资产终止确认收益（元） |
| BASIC_EPS | float64 | 基本每股收益（元/股） |
| BEG_UNDISTRIBUTED_PRO | float64 | 年初未分配利润（元） |
| CAPITALIZED_COM_STOCK_DIV | float64 | 转作股本的普通股股利（元） |
| COMMENTS | string | 备注 |
| COMMON_STOCK_DIV_PAYABLE | float64 | 应付普通股股利（元） |
| COMP_TYPE_CODE | integer | 公司类型代码（1:非金融 2:银行 3:保险 4:证券） |
| CONTINUED_NET_OPERA_PRO | float64 | 持续经营净利润（元） |
| CREDIT_IMPAIR_LOSS | float64 | 信用减值损失（元） |
| CURRENCY_CODE | string | 货币代码 |
| DILUTED_EPS | float64 | 稀释每股收益（元/股） |
| DISTRIBUTIVE_PRO | float64 | 可分配利润（元） |
| DISTRIBUTIVE_PRO_SHAREHOLDER | float64 | 可供股东分配的利润（元） |
| DIV_EXP_INSUR | float64 | 保户红利支出（元） |
| EBIT | float64 | 息税前利润（正向法）（元） |
| EBITDA | float64 | 息税折旧摊销前利润（元） |
| EMPLOYEE_WELF | float64 | 职工奖金福利（元） |
| END_NET_OPERA_PRO | float64 | 终止经营净利润（元） |
| EXT_INSUR_CONT_RESV | float64 | 提取保险责任准备金（元） |
| EXT_UNEARNED_PREM_RES | float64 | 提取未到期责任准备金（元） |
| FIN_EXP_INT_EXP | float64 | 财务费用:利息费用（元） |
| FIN_EXP_INT_INC | float64 | 财务费用:利息收入（元） |
| GAIN_DISPOSAL_ASSETS | float64 | 资产处置收益（元） |
| HANDLING_CHRG_COMM_FEE | float64 | 手续费及佣金收入（元） |
| INCL_INC_INV_JV_ENTP | float64 | 其中:对联营企业和合营企业的投资收益（元） |
| INCL_LESS_LOSS_DISP_NCUR_ASSETS | float64 | 其中:减:非流动资产处置净损失（元） |
| INCL_REINSUR_PREM_INC | float64 | 其中:分保费收入（元） |
| INCOME_TAX | float64 | 所得税（元） |
| INSUR_EXP | float64 | 保险业务支出（元） |
| INSUR_PREM | float64 | 已赚保费（元） |
| INTEREST_INC | float64 | 利息收入（元） |
| IS_CALCULATION | integer | 是否计算报表（0:否 1:是） |
| LESS_ADMIN_EXP | float64 | 减:管理费用（元） |
| LESS_AMORT_COMPEN_EXP | float64 | 减:摊回赔付支出（元） |
| LESS_AMORT_INSUR_CONT_RSRV | float64 | 减:摊回保险责任准备金（元） |
| LESS_AMORT_REINSUR_EXP | float64 | 减:摊回分保费用（元） |
| LESS_ASSETS_IMPAIR_LOSS | float64 | 减:资产减值损失（元） |
| LESS_BUS_TAX_SURCHARGE | float64 | 减:营业税金及附加（元） |
| LESS_FIN_EXP | float64 | 减:财务费用（元） |
| LESS_HANDLING_CHRG_COMM_FEE | float64 | 减:手续费及佣金支出（元） |
| LESS_INTEREST_EXP | float64 | 减:利息支出（元） |
| LESS_NON_OPER_EXP | float64 | 减:营业外支出（元） |
| LESS_OPERA_COST | float64 | 减:营业成本（元） |
| LESS_REINSUR_PREM | float64 | 减:分出保费（元） |
| LESS_SELLING_EXP | float64 | 减:销售费用（元） |
| MIN_INT_INC | float64 | 少数股东损益（元） |
| NET_EXPOSURE_HEDGING_GAIN | float64 | 净敞口套期收益（元） |
| NET_HANDLING_CHRG_COMM_FEE | float64 | 手续费及佣金净收入（元） |
| NET_INC_EC_ASSET_MGMT_BUS | float64 | 受托客户资产管理业务净收入（元） |
| NET_INC_SEC_BROK_BUS | float64 | 代理买卖证券业务净收入（元） |
| NET_INTEREST_INC | float64 | 利息净收入（元） |
| NET_PRO_AFTER_DED_NR_GL | float64 | 扣除非经常性损益后净利润（扣除少数股东损益）（元） |
| NET_PRO_AFTER_DED_NR_GL_COR | float64 | 扣除非经常性损益后的净利润(财务重要指标(更正前))（元） |
| NET_PRO_EXCL_MIN_INT_INC | float64 | 净利润 (不含少数股东损益)（元） |
| NET_PRO_INCL_MIN_INT_INC | float64 | 净利润 (含少数股东损益)（元） |
| NET_PRO_UNDER_INT_ACC_STA | float64 | 国际会计准则净利润（元） |
| OPERA_EXP | float64 | 营业支出（元） |
| OPERA_PROFIT | float64 | 营业利润（元） |
| OPERA_REV | float64 | 营业收入（元） |
| OTH_ASSETS_IMPAIR_LOSS | float64 | 其他资产减值损失（元） |
| OTH_BUS_COST | float64 | 其他业务成本（元） |
| OTH_BUS_INC | float64 | 其他业务收入（元） |
| OTH_COMPRE_IN_C | float64 | 其他综合收益（元） |
| OTH_EQUITY_TOOLS | float64 | 其他权益工具（元） |
| OTH_INCOME | float64 | 其他收益（元） |
| OTH_NET_OPERA_INC | float64 | 其他经营净收益（元） |
| PLUS_NET_FX_INC | float64 | 加:汇兑净收益（元） |
| PLUS_NET_GAIN_CHG_FV | float64 | 加:公允价值变动净收益（元） |
| PLUS_NET_INV_INC | float64 | 加:投资净收益（元） |
| PLUS_NON_OPER_A_REV | float64 | 加:营业外收入（元） |
| PLUS_OTH_NET_BUS_INC | float64 | 加:其他业务净收益（元） |
| PREFERRED_SHARE_DIV_PAYABLE | float64 | 应付优先股股利（元） |
| PREM_BUS_INC | float64 | 保费业务收入（元） |
| RD_EXP | float64 | 研发费用（元） |
| REINSURANCE_EXP | float64 | 分保费用（元） |
| SPE_BAL_NET_PRO_MARG | float64 | 净利润差额 (特殊报表科目)（元） |
| SPE_BAL_OPERA_PRO_MARG | float64 | 营业利润差额 (特殊报表科目)（元） |
| SPE_BAL_TOT_OPERA_COST_DIF | float64 | 营业总成本差额 (特殊报表科目)（元） |
| SPE_BAL_TOT_OPERA_INC_DIF | float64 | 营业总收入差额 (特殊报表科目)（元） |
| SPE_BAL_TOT_PRO_MARG | float64 | 利润总额差额 (特殊报表科目)（元） |
| SPE_BAL_TOT_OPERA_COST_DIF_STATE | string | 营业总成本差额说明(特殊报表科目) |
| SPE_BAL_TOT_OPERA_INC_DIF_STATE | string | 营业总收入差额说明(特殊报表科目) |
| SURR_VALUE | float64 | 退保金（元） |
| TOT_BAL_NET_PRO_MARG | float64 | 净利润差额 (合计平衡项目)（元） |
| TOT_BAL_OPERA_PRO_MARG | float64 | 营业利润差额 (合计平衡项目)（元） |
| TOT_BAL_TOT_PRO_MARG | float64 | 利润总额差额 (合计平衡项目)（元） |
| TOT_COMPEN_EXP | float64 | 嵌付总支出（元） |
| TOT_COMPRE_IN_C | float64 | 综合收益总额（元） |
| TOT_COMPRE_IN_C_MIN_SHARE | float64 | 综合收益总额 (少数股东)（元） |
| TOT_COMPRE_IN_C_PARENT_COMP | float64 | 综合收益总额 (母公司)（元） |
| TOT_OPERA_COST | float64 | 营业总成本（元） |
| TOT_OPERA_COST2 | float64 | 营业总成本2（元） |
| TOT_OPERA_REV | float64 | 营业总收入（元） |
| TOTAL_PROFIT | float64 | 利润总额（元） |
| TRANSFER_HOUSING_REVO_FUNDS | float64 | 住房周转金转入（元） |
| TRANSFER_OTHERS | float64 | 其他转入（元） |
| TRANSFER_SURPLUS_RESERVE | float64 | 盈余公积转入（元） |
| UNCONFIRMED_INV_LOSS | float64 | 未确认投资损失（元） |
| WITHDRAW_ANY_SURPLUS_RESV | float64 | 提取任意盈余公积金（元） |
| WITHDRAW_ENT_DEVELOP_FUND | float64 | 提取企业发展基金（元） |
| WITHDRAW_LEG_PUB_WEL_FUND | float64 | 提取法定公益金（元） |
| WITHDRAW_LEG_SURPLUS | float64 | 提取法定盈余公积（元） |
| WITHDRAW_RESV_FUND | float64 | 提取储备基金（元） |

### profit_express（业绩快报）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| REPORTING_PERIOD | string | 报告期 |
| ANN_DATE | string | 公告日期 |
| ACTUAL_ANN_DATE | string | 实际公告日期 |
| TOTAL_ASSETS | float64 | 总资产（元） |
| NET_PRO_EXCL_MIN_INT_INC | float64 | 净利润（元） |
| TOT_OPERA_REV | float64 | 营业总收入（元） |
| TOTAL_PROFIT | float64 | 利润总额（元） |
| OPERA_PROFIT | float64 | 营业利润（元） |
| EPS_BASIC | float64 | 每股收益-基本（元/股） |
| TOT_SHARE_EQUITY_EXCL_MIN_INT | float64 | 股东权益合计 (不含少数股东权益)（元） |
| IS_AUDIT | integer | 是否审计（0:否 1:是） |
| ROE_WEIGHTED | float64 | 净资产收益率-加权（%） |
| LAST_YEAR_REVISED_NET_PRO | float64 | 去年同期修正后净利润（元） |
| PERFORMANCE_SUMMARY | string | 业绩简要说明 |
| NET_ASSET_PS | float64 | 每股净资产（元/股） |
| MEMO | string | 备注 |
| YOY_GR_GROSS_PRO | float64 | 同比增长率:% 营业利润 |
| YOY_GR_GROSS_REV | float64 | 同比增长率:% 营业总收入 |
| YOY_GR_NET_PROFIT_PARENT | float64 | 同比增长率:% 归属母公司股东的净利润 |
| YOY_GR_TOT_PROFIT | float64 | 同比增长率:% 利润总额 |
| YOY_ID_WAROE | float64 | 同比增减:加权平均净资产收益率% |
| YOY_GR_EPS_BASIC | float64 | 同比增长率:% 基本每股收益 |
| GROWTH_RATE_EQUITY | float64 | 比年初增长率:归属母公司的股东权益% |
| GROWTH_RATE_ASSETS | float64 | 比年初增长率:总资产% |
| GROWTH_RATE_NAPS | float64 | 比年初增长率:归属于母公司的每股净资产% |
| LAST_YEAR_TOT_OPERA_REV | float64 | 去年同期营业总收入（元） |
| LAST_YEAR_TOT_PROFIT | float64 | 去年同期利润总额（元） |
| LAST_YEAR_OPERA_PRO | float64 | 去年同期营业利润（元） |
| LAST_YEAR_EPS_DILUTED | float64 | 去年同期每股收益（元/股） |
| LAST_YEAR_NET_PROFIT | float64 | 去年同期净利润（元） |
| INITIAL_NET_ASSET_PS | float64 | 期初每股净资产（元/股） |
| INITIAL_NET_ASSETS | float64 | 期初净资产（元） |

### profit_notice（业绩预告）

| 字段名 | JSON 类型 | 说明 |
|--------|----------|------|
| MARKET_CODE | string | 证券代码 |
| SECURITY_NAME | string | 证券简称 |
| P_TYPECODE | string | 业绩预告类型代码（1:不确定, 2:略减, 3:略增, 4:扭亏, 5:其他, 6:首亏, 7:续亏, 8:续盈, 9:预减, 10:预增, 11:持平） |
| REPORTING_PERIOD | string | 报告期 |
| ANN_DATE | string | 公告日期 |
| REPORT_TYPE | string | 报告期名称 |
| P_CHANGE_MAX | float64 | 预告净利润变动幅度上限（%） |
| P_CHANGE_MIN | float64 | 预告净利润变动幅度下限（%） |
| NET_PROFIT_MAX | float64 | 预告净利润上限（万元） |
| NET_PROFIT_MIN | float64 | 预告净利润下限（万元） |
| FIRST_ANN_DATE | string | 首次公告日 |
| P_NUMBER | integer | 公布次数 |
| P_REASON | string | 业绩变动原因 |
| P_SUMMARY | string | 业绩预告摘要 |
| P_NET_PARENT_FIRM | float64 | 上年同期归母净利润（万元） |

## 响应示例

### 查询利润表数据

**请求**: `GET /api/v2/financial/amazing_data/income?symbol=000001&page=1&page_size=10`

```json
[
  {
    "id": 500001,
    "source": "amazing_data",
    "symbol": "000001",
    "market": "zh_a",
    "statement_type": "income",
    "report_period": "2023-12-31",
    "report_type": "2023年报",
    "statement_code": "合并报表",
    "security_name": "平安银行",
    "ann_date": "2024-03-28",
    "actual_ann_date": "2024-03-28",
    "comp_type_code": 2,
    "data_json": {
      "MARKET_CODE": "000001",
      "SECURITY_NAME": "平安银行",
      "TOT_OPERA_REV": 1650000000000,
      "TOT_OPERA_COST": 1270000000000,
      "OPERA_PROFIT": 380000000000,
      "TOTAL_PROFIT": 380000000000,
      "NET_PRO_INCL_MIN_INT_INC": 378000000000,
      "NET_PRO_EXCL_MIN_INT_INC": 376000000000,
      "BASIC_EPS": 1.95,
      "DILUTED_EPS": 1.93,
      "INCOME_TAX": 20000000000,
      "INTEREST_INC": 1200000000000,
      "EBIT": 420000000000,
      "EBITDA": 480000000000,
      "COMP_TYPE_CODE": 2
    },
    "created_at": "2024-03-29T00:00:00Z",
    "updated_at": "2024-03-29T00:00:00Z"
  }
]
```

### 查询利润表数据（使用 fields 参数过滤字段）

**请求**: `GET /api/v2/financial/amazing_data/income?symbol=000001&fields=symbol,reporting_period,data_json.TOT_OPERA_REV,data_json.NET_PRO_EXCL_MIN_INT_INC,data_json.EBITDA`

```json
[
  {
    "symbol": "000001",
    "reporting_period": "2023-12-31",
    "data_json->'TOT_OPERA_REV'": "data_json.TOT_OPERA_REV",
    "data_json->'NET_PRO_EXCL_MIN_INT_INC'": "data_json.NET_PRO_EXCL_MIN_INT_INC",
    "data_json->'EBITDA'": "data_json.EBITDA"
  }
]
```

---

*文档最后更新: 2026-05-13*
