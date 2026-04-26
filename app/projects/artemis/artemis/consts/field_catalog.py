"""
Field Catalog — the single source of truth for all JSON-stored data field metadata.

Organized by data_domain → data_type → list of FieldEntry.
Used for:
  - Developer reference (import and inspect programmatically)
  - Documentation generation (docs/financial_data_fields.md)
  - Future: UI field selectors, query builders, data validation

Usage:
    from artemis.consts.field_catalog import CATALOG, get_fields, list_domains

    fields = get_fields("financial_statement", "balance_sheet")
    for f in fields:
        print(f.name, f.cn_desc, f.dtype)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FieldEntry:
    """A single data field stored in data_json."""
    name: str          # SDK column name, e.g. 'TOTAL_ASSETS'
    cn_desc: str       # 中文名, e.g. '资产总计'
    dtype: str         # 'float' | 'int' | 'str'
    note: str = ""     # 备注


# ═══════════════════════════════════════════════════════
# Domain: financial_statement
# Table: financial_statement, discriminator: statement_type
# ═══════════════════════════════════════════════════════

# ── balance_sheet ──
_BALANCE_SHEET_FIELDS: List[FieldEntry] = [
    FieldEntry("ACC_PAYABLE", "应付票据及应付账款", "float"),
    FieldEntry("ACC_RECEIVABLE", "应收票据及应收账款", "float"),
    FieldEntry("ACC_RECEIVABLES", "应收款项", "float"),
    FieldEntry("ACCRUED_EXP", "预提费用", "float"),
    FieldEntry("ACCT_PAYABLE", "应付账款", "float"),
    FieldEntry("ACCT_RECEIVABLE", "应收账款", "float"),
    FieldEntry("ACT_TRADING_SEC", "代理买卖证券款", "float"),
    FieldEntry("ACT_UW_SEC", "代理承销证券款", "float"),
    FieldEntry("ADV_PREM", "预收保费", "float"),
    FieldEntry("ADV_RECEIPT", "预收款项", "float"),
    FieldEntry("AGENCY_ASSETS", "代理业务资产", "float"),
    FieldEntry("AGENCY_BUSINESS_LIAB", "代理业务负债", "float"),
    FieldEntry("ANTICIPATION_LIAB", "预计负债", "float"),
    FieldEntry("ASSET_DEP_FUNDS_OTH_FIN_INST", "存放同业和其它金融机构款项", "float"),
    FieldEntry("BONDS_PAYABLE", "应付债券", "float"),
    FieldEntry("CAP_RESV", "资本公积金", "float"),
    FieldEntry("CAP_STOCK", "股本", "float", "金额（元），公布值"),
    FieldEntry("CASH_CENTRAL_BANK_DEPOSITS", "现金及存放中央银行款项", "float"),
    FieldEntry("CED_INSUR_CONT_RESERVES_RCV", "应收分保合同准备金", "float"),
    FieldEntry("CLAIMS_PAYABLE", "应付赔付款", "float"),
    FieldEntry("CLIENTS_FUND_DEPOSIT", "客户资金存款", "float"),
    FieldEntry("CLIENTS_RESERVES", "客户备付金", "float"),
    FieldEntry("CNVD_DIFF_FOREIGN_CURR_STAT", "外币报表折算差额", "float"),
    FieldEntry("CONST_IN_PROC", "在建工程", "float"),
    FieldEntry("CONST_IN_PROC_TOTAL", "在建工程(合计)(元)", "float"),
    FieldEntry("CONSUMP_BIO_ASSETS", "消耗性生物资产", "float"),
    FieldEntry("CONT_ASSETS", "合同资产", "float", "单位（元）"),
    FieldEntry("CONT_LIABILITIES", "合同负债", "float", "单位（元）"),
    FieldEntry("CURRENCY_CAP", "货币资金", "float"),
    FieldEntry("CURRENCY_CODE", "货币代码", "float"),
    FieldEntry("DEBT_INV", "债权投资(元)", "float"),
    FieldEntry("DEFERRED_INC_NONCUR_LIAB", "递延收益-非流动负债", "float"),
    FieldEntry("DEFERRED_INCOME", "递延收益", "float"),
    FieldEntry("DEFERRED_TAX_ASSETS", "递延所得税资产", "float"),
    FieldEntry("DEFERRED_TAX_LIAB", "递延所得税负债", "float"),
    FieldEntry("DEP_RECEIVED_IB_DEP", "吸收存款及同业存放", "float"),
    FieldEntry("DEPOSIT_CAP_RECOG", "存出资本保证金", "float"),
    FieldEntry("DEPOSIT_TAKING", "吸收存款", "float"),
    FieldEntry("DEPOSITS_RECEIVED", "存入保证金", "float"),
    FieldEntry("DER_FIN_ASSETS", "衍生金融资产", "float"),
    FieldEntry("DERI_FIN_LIAB", "衍生金融负债", "float"),
    FieldEntry("DEVELOP_EXP", "开发支出", "float"),
    FieldEntry("DISPOSAL_FIX_ASSETS", "固定资产清理", "float"),
    FieldEntry("DIV_PAYABLE", "应付股利", "float"),
    FieldEntry("DIV_RECEIVABLE", "应收股利", "float"),
    FieldEntry("EMPL_PAY_PAYABLE", "应付职工薪酬", "float"),
    FieldEntry("ENGIN_MAT", "工程物资", "float"),
    FieldEntry("FIN_ASSETS_AVA_FOR_SALE", "可供出售金融资产", "float"),
    FieldEntry("FIN_ASSETS_COST_SHARING", "以摊余成本计量的金融资产", "float"),
    FieldEntry("FIN_ASSETS_FAIR_VALUE", "以公允价值计量且其变动计入其他综合收益的金融资产", "float"),
    FieldEntry("FIXED_ASSETS", "固定资产", "float"),
    FieldEntry("FIXED_ASSETS_TOTAL", "固定资产(合计)(元)", "float"),
    FieldEntry("FIXED_TERM_DEPOSITS", "定期存款", "float"),
    FieldEntry("GOODWILL", "商誉", "float"),
    FieldEntry("GUA_DEPOSITS_PAID", "存出保证金", "float"),
    FieldEntry("GUA_PLEDGE_LOANS", "保户质押贷款", "float"),
    FieldEntry("HOLD_ASSETS_FOR_SALE", "持有待售的资产", "float"),
    FieldEntry("HOLD_TO_MTY_INV", "持有至到期投资", "float"),
    FieldEntry("IND_ACCT_ASSETS", "独立账户资产", "float"),
    FieldEntry("IND_ACCT_LIAB", "独立账户负债", "float"),
    FieldEntry("INSURED_DEPOSIT_INV", "保户储金及投资款", "float"),
    FieldEntry("INSURED_DIV_PAYABLE", "应付保单红利", "float"),
    FieldEntry("INT_RECEIVABLE", "应收利息", "float"),
    FieldEntry("INTANGIBLE_ASSETS", "无形资产", "float"),
    FieldEntry("INTEREST_PAYABLE", "应付利息", "float"),
    FieldEntry("INV", "存货", "float"),
    FieldEntry("INV_REALESTATE", "投资性房地产", "float"),
    FieldEntry("LEASE_LIABILITY", "租赁负债", "float"),
    FieldEntry("LEND_FUNDS", "融出资金", "float"),
    FieldEntry("LENDING_FUNDS", "拆出资金", "float"),
    FieldEntry("LESS_TREASURY_STK", "减:库存股", "float"),
    FieldEntry("LIA_HFS", "持有待售的负债", "float"),
    FieldEntry("LIAB_DEP_FUNDS_OTH_FIN_INST", "同业和其它金融机构存放款项", "float"),
    FieldEntry("LIFE_INSUR_RESV", "寿险责任准备金", "float"),
    FieldEntry("LOAN_CENTRAL_BANK", "向中央银行借款", "float"),
    FieldEntry("LOANS_AND_ADVANCES", "发放贷款及垫款", "float"),
    FieldEntry("LOANS_FROM_OTH_BANKS", "拆入资金", "float"),
    FieldEntry("LT_DEFERRED_EXP", "长期待摊费用", "float"),
    FieldEntry("LT_EMP_COMP_PAY", "长期应付职工薪酬", "float"),
    FieldEntry("LT_EQUITY_INV", "长期股权投资", "float"),
    FieldEntry("LT_HEALTH_INSUR_RESV", "长期健康险责任准备金", "float"),
    FieldEntry("LT_LOAN", "长期借款", "float"),
    FieldEntry("LT_PAYABLE", "长期应付款", "float"),
    FieldEntry("LT_PAYABLE_TOTAL", "长期应付款(合计)(元)", "float"),
    FieldEntry("LT_RECEIVABLES", "长期应收款", "float"),
    FieldEntry("MINORITY_EQUITY", "少数股东权益", "float"),
    FieldEntry("NOM_RISKS_PREP", "一般风险准备", "float"),
    FieldEntry("NONCUR_ASSETS_DUE_WITHIN_1Y", "一年内到期的非流动资产", "float"),
    FieldEntry("NONCUR_LIAB_DUE_WITHIN_1Y", "一年内到期的非流动负债", "float"),
    FieldEntry("NOTES_PAYABLE", "应付票据", "float"),
    FieldEntry("NOTES_RECEIVABLE", "应收票据", "float"),
    FieldEntry("OIL_AND_GAS_ASSETS", "油气资产", "float"),
    FieldEntry("OTH_COMP_INCOME", "其他综合收益", "float"),
    FieldEntry("OTH_EQUITY_TOOLS", "其他权益工具", "float"),
    FieldEntry("OTH_EQUITY_TOOLS_PRE_SHR", "其他权益工具:优先股", "float"),
    FieldEntry("OTH_NONCUR_ASSETS", "其他非流动资产", "float"),
    FieldEntry("OTHER_ASSETS", "其他资产", "float"),
    FieldEntry("OTHER_CUR_ASSETS", "其他流动资产", "float"),
    FieldEntry("OTHER_CUR_LIAB", "其他流动负债", "float"),
    FieldEntry("OTHER_DEBT_INV", "其他债权投资(元)", "float"),
    FieldEntry("OTHER_EQUITY_INV", "其他权益工具投资(元)", "float"),
    FieldEntry("OTHER_LIAB", "其他负债", "float"),
    FieldEntry("OTHER_NONCUR_FIN_ASSETS", "其他非流动金融资产(元)", "float"),
    FieldEntry("OTHER_NONCUR_LIAB", "其他非流动负债", "float"),
    FieldEntry("OTHER_PAYABLE", "其他应付款", "float"),
    FieldEntry("OTHER_PAYABLE_TOTAL", "其他应付款(合计)(元)", "float"),
    FieldEntry("OTHER_RCV_TOTAL", "其他应收款(合计)（元）", "float"),
    FieldEntry("OTHER_RECEIVABLE", "其他应收款", "float"),
    FieldEntry("OTHER_SUSTAIN_BOND", "其他权益工具:永续债(元)", "float"),
    FieldEntry("PAYABLE", "应付款项", "float"),
    FieldEntry("PAYABLE_FOR_REINSURER", "应付分保账款", "float"),
    FieldEntry("PRECIOUS_METAL", "贵金属", "float"),
    FieldEntry("PREPAYMENT", "预付款项", "float"),
    FieldEntry("PROD_BIO_ASSETS", "生产性生物资产", "float"),
    FieldEntry("RCV_FINANCING", "应收款项融资", "float"),
    FieldEntry("RCV_INV", "应收款项类投资", "float"),
    FieldEntry("RECEIVABLE_PREM", "应收保费", "float"),
    FieldEntry("RED_MON_CAP_FOR_SALE", "买入返售金融资产", "float"),
    FieldEntry("REINSURANCE_ACC_RCV", "应收分保账款", "float"),
    FieldEntry("RSRV_FUND_INSUR_CONT", "保险合同准备金", "float"),
    FieldEntry("SELL_REPO_FIN_ASSETS", "卖出回购金融资产款", "float"),
    FieldEntry("SETTLE_FUNDS", "结算备付金", "float"),
    FieldEntry("SPECIAL_PAYABLE", "专项应付款", "float"),
    FieldEntry("SPECIAL_RESV", "专项储备", "float"),
    FieldEntry("ST_BONDS_PAYABLE", "应付短期债券", "float"),
    FieldEntry("ST_BORROWING", "短期借款", "float"),
    FieldEntry("ST_FIN_PAYABLE", "应付短期融资款", "float"),
    FieldEntry("SURPLUS_RESV", "盈余公积金", "float"),
    FieldEntry("TAX_PAYABLE", "应交税费", "float"),
    FieldEntry("TOT_NONCUR_ASSETS", "非流动资产合计", "float"),
    FieldEntry("TOT_SHARE", "期末总股本", "float", "单位（股）"),
    FieldEntry("TOT_SHARE_EQUITY_EXCL_MIN_INT", "股东权益合计(不含少数股东权益)", "float"),
    FieldEntry("TOT_SHARE_EQUITY_INCL_MIN_INT", "股东权益合计(含少数股东权益)", "float"),
    FieldEntry("TOTAL_ASSETS", "资产总计", "float"),
    FieldEntry("TOTAL_CUR_ASSETS", "流动资产合计", "float"),
    FieldEntry("TOTAL_CUR_LIAB", "流动负债合计", "float"),
    FieldEntry("TOTAL_LIAB", "负债合计", "float"),
    FieldEntry("TOTAL_LIAB_SHARE_EQUITY", "负债及股东权益总计", "float"),
    FieldEntry("TOTAL_NONCUR_LIAB", "非流动负债合计", "float"),
    FieldEntry("TRADING_FIN_LIAB", "交易性金融负债", "float"),
    FieldEntry("TRADING_FINASSETS", "交易性金融资产", "float"),
    FieldEntry("UNDISTRIBUTED_PRO", "未分配利润", "float"),
    FieldEntry("USE_RIGHT_ASSETS", "使用权资产", "float"),
]

# ── income ──
_INCOME_FIELDS: List[FieldEntry] = [
    FieldEntry("BASIC_EPS", "基本每股收益", "float"),
    FieldEntry("DILUTED_EPS", "稀释每股收益", "float"),
    FieldEntry("OPERA_REV", "营业收入", "float"),
    FieldEntry("TOT_OPERA_REV", "营业总收入", "float"),
    FieldEntry("TOT_OPERA_COST", "营业总成本", "float"),
    FieldEntry("LESS_OPERA_COST", "减:营业成本", "float"),
    FieldEntry("LESS_SELLING_EXP", "减:销售费用", "float"),
    FieldEntry("LESS_ADMIN_EXP", "减:管理费用", "float"),
    FieldEntry("LESS_FIN_EXP", "减:财务费用", "float"),
    FieldEntry("RD_EXP", "研发费用", "float"),
    FieldEntry("LESS_ASSETS_IMPAIR_LOSS", "减:资产减值损失", "float"),
    FieldEntry("CREDIT_IMPAIR_LOSS", "信用减值损失", "float"),
    FieldEntry("PLUS_NET_INV_INC", "加:投资净收益", "float"),
    FieldEntry("PLUS_NET_GAIN_CHG_FV", "加:公允价值变动净收益", "float"),
    FieldEntry("PLUS_NON_OPERA_REV", "加:营业外收入", "float"),
    FieldEntry("LESS_NON_OPERA_EXP", "减:营业外支出", "float"),
    FieldEntry("OPERA_PROFIT", "营业利润", "float"),
    FieldEntry("TOTAL_PROFIT", "利润总额", "float"),
    FieldEntry("INCOME_TAX", "所得税", "float"),
    FieldEntry("NET_PRO_INCL_MIN_INT_INC", "净利润(含少数股东损益)", "float"),
    FieldEntry("NET_PRO_EXCL_MIN_INT_INC", "净利润(不含少数股东损益)", "float"),
    FieldEntry("MIN_INT_INC", "少数股东损益", "float"),
    FieldEntry("NET_PRO_AFTER_DED_NR_GL", "扣除非经常性损益后净利润", "float"),
    FieldEntry("TOT_COMPRE_INC", "综合收益总额", "float"),
    FieldEntry("TOT_COMPRE_INC_PARENT_COMP", "综合收益总额(母公司)", "float"),
    FieldEntry("OTH_COMPRE_INC", "其他综合收益", "float"),
    FieldEntry("OTH_INCOME", "其他收益", "float"),
    FieldEntry("GAIN_DISPOSAL_ASSETS", "资产处置收益", "float"),
    FieldEntry("FIN_EXP_INT_EXP", "财务费用:利息费用", "float"),
    FieldEntry("FIN_EXP_INT_INC", "财务费用:利息收入", "float"),
    FieldEntry("EBIT", "息税前利润", "float"),
    FieldEntry("EBITDA", "息税折旧摊销前利润", "float"),
    FieldEntry("LESS_BUS_TAX_SURCHARGE", "减:营业税金及附加", "float"),
    FieldEntry("IS_CALCULATION", "是否计算报表", "float"),
    FieldEntry("CURRENCY_CODE", "货币代码", "str"),
]

# ── cashflow ──
_CASHFLOW_FIELDS: List[FieldEntry] = [
    FieldEntry("CASH_RECP_SG_AND_RS", "销售商品、提供劳务收到的现金", "float"),
    FieldEntry("RECP_TAX_REFUND", "收到的税费返还", "float"),
    FieldEntry("OTHER_CASH_RECP_OPER_ACT", "收到其他与经营活动有关的现金", "float"),
    FieldEntry("TOT_CASH_INFLOW_OPER_ACT", "经营活动现金流入小计", "float"),
    FieldEntry("CASH_PAY_GOODS_SERVICES", "购买商品、接受劳务支付的现金", "float"),
    FieldEntry("CASH_PAY_EMPLOYEE", "支付给职工以及为职工支付的现金", "float"),
    FieldEntry("PAY_ALL_TAX", "支付的各项税费", "float"),
    FieldEntry("OTH_CASH_PAY_OPERA_ACT", "支付其他与经营活动有关的现金", "float"),
    FieldEntry("TOT_CASH_OUTFLOW_OPERA_ACT", "经营活动现金流出小计", "float"),
    FieldEntry("NET_CASH_FLOWS_OPERA_ACT", "经营活动产生的现金流量净额", "float"),
    FieldEntry("CASH_RECP_RECOV_INV", "收回投资收到的现金", "float"),
    FieldEntry("CASH_RECP_INV_INCOME", "取得投资收益收到的现金", "float"),
    FieldEntry("NET_CASH_RECP_DISP_FIOLTA", "处置固定资产、无形资产和其他长期资产收回的现金净额", "float"),
    FieldEntry("TOT_CASH_INFLOW_INV_ACT", "投资活动现金流入小计", "float"),
    FieldEntry("CASH_PAID_INV", "投资支付的现金", "float"),
    FieldEntry("CASH_PAID_PUR_CONST_FIOLTA", "购建固定资产、无形资产和其他长期资产支付的现金", "float"),
    FieldEntry("TOT_CASH_OUTFLOW_INV_ACT", "投资活动现金流出小计", "float"),
    FieldEntry("NET_CASH_FLOWS_INV_ACT", "投资活动产生的现金流量净额", "float"),
    FieldEntry("CASH_RECE_BORROW", "取得借款收到的现金", "float"),
    FieldEntry("CASH_RECE_ISSUE_BONDS", "发行债券收到的现金", "float"),
    FieldEntry("ABSORB_CASH_RECP_INV", "吸收投资收到的现金", "float"),
    FieldEntry("TOT_CASH_INFLOW_FIN_ACT", "筹资活动现金流入小计", "float"),
    FieldEntry("CASH_PAY_FOR_DEBT", "偿还债务支付的现金", "float"),
    FieldEntry("CASH_PAY_DIST_DIV_PRO_INT", "分配股利、利润或偿付利息支付的现金", "float"),
    FieldEntry("TOT_CASH_OUTFLOW_FIN_ACT", "筹资活动现金流出小计", "float"),
    FieldEntry("NET_CASH_FLOWS_FIN_ACT", "筹资活动产生的现金流量净额", "float"),
    FieldEntry("EFF_FX_FLUC_CASH", "汇率变动对现金的影响", "float"),
    FieldEntry("NET_INCR_CASH_AND_CASH_EQU", "现金及现金等价物净增加额", "float"),
    FieldEntry("BEG_BAL_CASH_CASH_EQU", "期初现金及现金等价物余额", "float"),
    FieldEntry("END_BAL_CASH_CASH_EQU", "期末现金及现金等价物余额", "float"),
    FieldEntry("NET_PROFIT", "净利润", "float"),
    FieldEntry("DEPRE_FA_OGA_PBA", "固定资产折旧、油气资产折耗、生产性生物资产折旧", "float"),
    FieldEntry("AMORT_INTAN_ASSETS", "无形资产摊销", "float"),
    FieldEntry("AMORT_LT_DEFERRED_EXP", "长期待摊费用摊销", "float"),
    FieldEntry("FINANCIAL_EXP", "财务费用", "float"),
    FieldEntry("INV_LOSS", "投资损失", "float"),
    FieldEntry("DECR_INVENTORY", "存货的减少", "float"),
    FieldEntry("DECR_OPERA_RECEIVABLE", "经营性应收项目的减少", "float"),
    FieldEntry("INCR_OPERA_PAYABLE", "经营性应付项目的增加", "float"),
    FieldEntry("FREE_CASH_FLOW", "企业自由现金流量", "float"),
    FieldEntry("IS_CALCULATION", "是否计算报表", "int"),
    FieldEntry("CURRENCY_CODE", "货币代码", "str"),
]

# ── profit_express ──
_PROFIT_EXPRESS_FIELDS: List[FieldEntry] = [
    FieldEntry("TOTAL_ASSETS", "总资产(元)", "float"),
    FieldEntry("NET_PRO_EXCL_MIN_INT_INC", "净利润(元)", "float"),
    FieldEntry("TOT_OPERA_REV", "营业总收入(元)", "float"),
    FieldEntry("TOTAL_PROFIT", "利润总额(元)", "float"),
    FieldEntry("OPERA_PROFIT", "营业利润(元)", "float"),
    FieldEntry("EPS_BASIC", "每股收益基本(元)", "float"),
    FieldEntry("TOT_SHARE_EQU_EXCL_MIN_INT", "股东权益合计(不含少数股东权益)(元)", "float"),
    FieldEntry("IS_AUDIT", "是否审计", "float", "1:是 0:否"),
    FieldEntry("ROE_WEIGHTED", "净资产收益率-加权(%)", "float"),
    FieldEntry("NET_ASSET_PS", "每股净资产", "float"),
    FieldEntry("PERFORMANCE_SUMMARY", "业绩简要说明", "str"),
    FieldEntry("MEMO", "备注", "str"),
    FieldEntry("YOY_GR_NET_PROFIT_PARENT", "同比增长率:归属母公司股东的净利润(%)", "float"),
    FieldEntry("YOY_GR_GROSS_REV", "同比增长率:营业总收入(%)", "float"),
    FieldEntry("YOY_GR_GROSS_PRO", "同比增长率:营业利润(%)", "float"),
    FieldEntry("YOY_GR_TOT_PRO", "同比增长率:利润总额(%)", "float"),
    FieldEntry("YOY_GR_EPS_BASIC", "同比增长率:基本每股收益(%)", "float"),
    FieldEntry("YOY_ID_WAROE", "同比增减:加权平均净资产收益率(%)", "float"),
    FieldEntry("GROWTH_RATE_EQUITY", "比年初增长率:归属母公司的股东权益(%)", "float"),
    FieldEntry("GROWTH_RATE_ASSETS", "比年初增长率:总资产(%)", "float"),
    FieldEntry("GROWTH_RATE_NAPS", "比年初增长率:归属于母公司股东的每股净资产(%)", "float"),
    FieldEntry("LAST_YEAR_REVISED_NET_PRO", "去年同期修正后净利润(元)", "float"),
    FieldEntry("LAST_YEAR_TOT_OPERA_REV", "去年同期营业总收入(元)", "float"),
    FieldEntry("LAST_YEAR_TOTAL_PROFIT", "去年同期利润总额(元)", "float"),
    FieldEntry("LAST_YEAR_OPERA_PRO", "去年同期营业利润(元)", "float"),
    FieldEntry("LAST_YEAR_EPS_DILUTED", "去年同期每股收益(元)", "float"),
    FieldEntry("LAST_YEAR_NET_PROFIT", "去年同期净利润(元)", "float"),
    FieldEntry("INITIAL_NET_ASSET_PS", "期初每股净资产(元)", "float"),
    FieldEntry("INITIAL_NET_ASSETS", "期初净资产(元)", "float"),
]

# ── profit_notice ──
_PROFIT_NOTICE_FIELDS: List[FieldEntry] = [
    FieldEntry("P_TYPECODE", "业绩预告类型代码", "str", "1不确定 2略减 3略增 4扭亏 5其他 6首亏 7续亏 8续盈 9预减 10预增 11持平"),
    FieldEntry("P_CHANGE_MAX", "预告净利润变动幅度上限(%)", "float"),
    FieldEntry("P_CHANGE_MIN", "预告净利润变动幅度下限(%)", "float"),
    FieldEntry("NET_PROFIT_MAX", "预告净利润上限(万元)", "float"),
    FieldEntry("NET_PROFIT_MIN", "预告净利润下限(万元)", "float"),
    FieldEntry("FIRST_ANN_DATE", "首次公告日", "str"),
    FieldEntry("P_NUMBER", "公布次数", "float"),
    FieldEntry("P_REASON", "业绩变动原因", "str"),
    FieldEntry("P_SUMMARY", "业绩预告摘要", "str"),
    FieldEntry("P_NET_PARENT_FIRM", "上年同期归母净利润", "float"),
]

# ═══════════════════════════════════════════════════════
# Domain: corporate_action
# Table: corporate_action, discriminator: action_type
# ═══════════════════════════════════════════════════════

# ── dividend ──
_DIVIDEND_FIELDS: List[FieldEntry] = [
    FieldEntry("DVD_PER_SHARE_STK", "每股送转", "float"),
    FieldEntry("DVD_PER_SHARE_PRE_TAX_CASH", "每股派息(税前)(元)", "float"),
    FieldEntry("DVD_PER_SHARE_AFTER_TAX_CASH", "每股派息(税后)(元)", "float"),
    FieldEntry("DATE_EQY_RECORD", "股权登记日", "str"),
    FieldEntry("DATE_EX", "除权除息日", "str"),
    FieldEntry("DATE_DVD_PAYOUT", "派息日", "str"),
    FieldEntry("LISTINGDATE_OF_DVD_SHR", "红股上市日", "str"),
    FieldEntry("DIV_PRELANDATE", "预案公告日", "str", "董事会预案公告日期"),
    FieldEntry("DIV_SMTGDATE", "股东大会公告日", "str"),
    FieldEntry("DATE_DVD_ANN", "分红实施公告日", "str"),
    FieldEntry("DIV_BASEDATE", "基准日期", "str"),
    FieldEntry("DIV_BASESHARE", "基准股本(万股)", "float"),
    FieldEntry("CURRENCY_CODE", "货币代码", "str"),
    FieldEntry("IS_CHANGED", "方案是否变更", "int", "1:有变更 0:未变更"),
    FieldEntry("DIV_CHANGE", "方案变更说明", "str"),
    FieldEntry("DIV_BONUSRATE", "每股送股比例", "float"),
    FieldEntry("DIV_CONVERSEDRATE", "每股转增比例", "float"),
    FieldEntry("REMARK", "备注", "str"),
    FieldEntry("DIV_PREANN_DATE", "预案预披露公告日", "str"),
    FieldEntry("DIV_TARGET", "分红对象", "str"),
]

# ── right_issue ──
_RIGHT_ISSUE_FIELDS: List[FieldEntry] = [
    FieldEntry("PRICE", "配股价格(元)", "float"),
    FieldEntry("RATIO", "配股比例", "float"),
    FieldEntry("AMT_PLAN", "配股计划数量(万股)", "float"),
    FieldEntry("AMT_REAL", "配股实际数量(万股)", "float"),
    FieldEntry("COLLECTION_FUND", "募集资金(元)", "float"),
    FieldEntry("SHAREB_REG_DATE", "股权登记日", "str"),
    FieldEntry("EX_DIVIDEND_DATE", "除权日", "str"),
    FieldEntry("LISTED_DATE", "配股上市日", "str"),
    FieldEntry("PAY_START_DATE", "缴款起始日", "str"),
    FieldEntry("PAY_END_DATE", "缴款终止日", "str"),
    FieldEntry("PREPLAN_DATE", "预案公告日", "str"),
    FieldEntry("SMTG_ANN_DATE", "股东大会公告日", "str"),
    FieldEntry("PASS_DATE", "发审委通过公告日", "str"),
    FieldEntry("APPROVED_DATE", "证监会核准公告日", "str"),
    FieldEntry("EXECUTE_DATE", "配股实施公告日", "str"),
    FieldEntry("RESULT_DATE", "配股结果公告日", "str"),
    FieldEntry("LIST_ANN_DATE", "上市公告日", "str"),
    FieldEntry("GUARANTOR", "基准年度", "str"),
    FieldEntry("GUARTYPE", "基准股本(万股)", "float"),
    FieldEntry("RIGHTSISSUE_CODE", "配售代码", "str"),
    FieldEntry("RIGHTSISSUE_DESC", "配股说明", "str"),
    FieldEntry("RIGHTSISSUE_NAME", "配股简称", "str"),
    FieldEntry("RATIO_DENOMINATOR", "配股比例分母", "float"),
    FieldEntry("RATIO_MOLECULAR", "配股比例分子", "float"),
    FieldEntry("SUBS_METHOD", "认购方式", "str"),
    FieldEntry("EXPECTED_FUND_RAISING", "预计募集资金(元)", "float"),
]


# ═══════════════════════════════════════════════════════
# Catalog Registry
# ═══════════════════════════════════════════════════════

@dataclass
class DomainMeta:
    """Metadata for a data domain."""
    table: str               # PhoenixA table name
    type_column: str          # discriminator column name
    api_prefix: str           # PhoenixA API prefix
    cn_name: str              # 中文域名
    types: Dict[str, List[FieldEntry]]  # data_type → fields


CATALOG: Dict[str, DomainMeta] = {
    "financial_statement": DomainMeta(
        table="financial_statement",
        type_column="statement_type",
        api_prefix="/api/v2/financial",
        cn_name="财务报表",
        types={
            "balance_sheet": _BALANCE_SHEET_FIELDS,
            "income": _INCOME_FIELDS,
            "cashflow": _CASHFLOW_FIELDS,
            "profit_express": _PROFIT_EXPRESS_FIELDS,
            "profit_notice": _PROFIT_NOTICE_FIELDS,
        },
    ),
    "corporate_action": DomainMeta(
        table="corporate_action",
        type_column="action_type",
        api_prefix="/api/v2/corporate-action",
        cn_name="公司行为",
        types={
            "dividend": _DIVIDEND_FIELDS,
            "right_issue": _RIGHT_ISSUE_FIELDS,
        },
    ),
}


# ═══════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════

def list_domains() -> List[str]:
    """Return all registered data domain names."""
    return list(CATALOG.keys())


def list_types(domain: str) -> List[str]:
    """Return all data type names for a domain."""
    meta = CATALOG.get(domain)
    return list(meta.types.keys()) if meta else []


def get_fields(domain: str, data_type: str) -> List[FieldEntry]:
    """Return field definitions for a specific domain + type."""
    meta = CATALOG.get(domain)
    if not meta:
        return []
    return meta.types.get(data_type, [])


def get_field_names(domain: str, data_type: str) -> List[str]:
    """Return just the field names for a specific domain + type."""
    return [f.name for f in get_fields(domain, data_type)]


def get_field_map(domain: str, data_type: str) -> Dict[str, FieldEntry]:
    """Return a dict of field_name → FieldEntry for quick lookup."""
    return {f.name: f for f in get_fields(domain, data_type)}

