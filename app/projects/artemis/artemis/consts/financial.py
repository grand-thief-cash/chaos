"""
Financial statement reference codes for AmazingData SDK.

These constants document the meaning of coded values in financial statement data.
"""


class FinancialStatementType:
    """Values for financial_statement.statement_type"""
    BALANCE_SHEET = "balance_sheet"
    INCOME = "income"
    CASHFLOW = "cashflow"
    PROFIT_EXPRESS = "profit_express"
    PROFIT_NOTICE = "profit_notice"


class ReportType:
    """
    REPORT_TYPE codes — maps to REPORTING_PERIOD quarter.
    Stored in financial_statement.report_type.
    """
    Q1 = "1"       # 3月 (一季报)
    H1 = "2"       # 6月 (半年报)
    Q3 = "3"       # 9月 (三季报)
    ANNUAL = "4"    # 12月 (年报)


class StatementCode:
    """
    STATEMENT_TYPE codes — report variant / consolidation type.
    Stored in financial_statement.statement_code.
    Only the most commonly used codes are listed; full list has 91+ entries.
    """
    CONSOLIDATED = "1"              # 合并报表
    CONSOLIDATED_SINGLE_Q = "2"     # 合并报表(单季度)
    CONSOLIDATED_SINGLE_ADJ = "3"   # 合并报表(单季度调整)
    CONSOLIDATED_ADJ = "4"          # 合并报表(调整)
    CONSOLIDATED_PRE_CORR = "5"     # 合并报表(更正前)
    PARENT = "6"                    # 母公司报表
    PARENT_SINGLE_Q = "7"           # 母公司报表(单季度)
    PARENT_SINGLE_ADJ = "8"         # 母公司报表(单季度调整)
    PARENT_ADJ = "9"                # 母公司报表(调整)
    PARENT_PRE_CORR = "10"          # 母公司报表(更正前)


class ProfitNoticeType:
    """
    P_TYPECODE in profit_notice data — 业绩预告类型代码.
    """
    UNCERTAIN = "1"       # 不确定
    SLIGHT_DECREASE = "2" # 略减
    SLIGHT_INCREASE = "3" # 略增
    TURNAROUND = "4"      # 扭亏
    OTHER = "5"           # 其他
    FIRST_LOSS = "6"      # 首亏
    CONTINUED_LOSS = "7"  # 续亏
    CONTINUED_PROFIT = "8" # 续盈
    FORECAST_DECREASE = "9"  # 预减
    FORECAST_INCREASE = "10" # 预增
    FLAT = "11"           # 持平


class CorporateActionType:
    """Values for corporate_action.action_type"""
    DIVIDEND = "dividend"
    RIGHT_ISSUE = "right_issue"


class DividendProgress:
    """DIV_PROGRESS codes — 股票分红进度代码."""
    BOARD_PLAN = "1"       # 董事会预案
    AGM_APPROVED = "2"     # 股东大会通过
    IMPLEMENTED = "3"      # 实施
    REJECTED = "4"         # 未通过
    STOPPED = "12"         # 停止实施
    SH_PROPOSAL = "17"     # 股东提议
    PRE_DISCLOSURE = "19"  # 董事会预案预披露


class RightIssueProgress:
    """PROGRESS codes — 股票配股进度代码."""
    BOARD_PLAN = "1"       # 董事会预案
    AGM_APPROVED = "2"     # 股东大会通过
    IMPLEMENTED = "3"      # 实施
    REJECTED = "4"         # 未通过
    CSRC_APPROVED = "5"    # 证监会核准
    STOPPED = "12"         # 停止实施
    SH_PROPOSAL = "17"     # 股东提议
    PRE_DISCLOSURE = "19"  # 董事会预案预披露
    REVIEW_PASSED = "20"   # 发审委通过
    REVIEW_FAILED = "21"   # 发审委未通过
    AGM_REJECTED = "22"    # 股东大会未通过


