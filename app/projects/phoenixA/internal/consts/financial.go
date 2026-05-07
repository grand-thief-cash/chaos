package consts

// Financial statement types stored in financial_statement.statement_type
const (
	FIN_STMT_BALANCE_SHEET  = "balance_sheet"
	FIN_STMT_INCOME         = "income"
	FIN_STMT_CASHFLOW       = "cashflow"
	FIN_STMT_PROFIT_EXPRESS = "profit_express"
	FIN_STMT_PROFIT_NOTICE  = "profit_notice"
)

// REPORT_TYPE codes — maps to REPORTING_PERIOD quarter.
// Value stored in financial_statement.report_type as string.
//
//	"1" = Q1 (3月)
//	"2" = H1 (6月)
//	"3" = Q3 (9月)
//	"4" = Annual (12月)
const (
	REPORT_TYPE_Q1     = "1"
	REPORT_TYPE_H1     = "2"
	REPORT_TYPE_Q3     = "3"
	REPORT_TYPE_ANNUAL = "4"
)

// STATEMENT_TYPE codes — report variant.
// Value stored in financial_statement.statement_code as string.
// Only the most commonly used codes are listed here; full list has 91+ entries.
const (
	STMT_CODE_CONSOLIDATED            = "1"  // 合并报表
	STMT_CODE_CONSOLIDATED_SINGLE_Q   = "2"  // 合并报表(单季度)
	STMT_CODE_CONSOLIDATED_SINGLE_ADJ = "3"  // 合并报表(单季度调整)
	STMT_CODE_CONSOLIDATED_ADJ        = "4"  // 合并报表(调整)
	STMT_CODE_CONSOLIDATED_PRE_CORR   = "5"  // 合并报表(更正前)
	STMT_CODE_PARENT                  = "6"  // 母公司报表
	STMT_CODE_PARENT_SINGLE_Q         = "7"  // 母公司报表(单季度)
	STMT_CODE_PARENT_SINGLE_ADJ       = "8"  // 母公司报表(单季度调整)
	STMT_CODE_PARENT_ADJ              = "9"  // 母公司报表(调整)
	STMT_CODE_PARENT_PRE_CORR         = "10" // 母公司报表(更正前)
)

// Profit notice type codes (P_TYPECODE in profit_notice data).
const (
	PROFIT_NOTICE_UNCERTAIN   = "1"  // 不确定
	PROFIT_NOTICE_SLIGHT_DN   = "2"  // 略减
	PROFIT_NOTICE_SLIGHT_UP   = "3"  // 略增
	PROFIT_NOTICE_TURNAROUND  = "4"  // 扭亏
	PROFIT_NOTICE_OTHER       = "5"  // 其他
	PROFIT_NOTICE_FIRST_LOSS  = "6"  // 首亏
	PROFIT_NOTICE_CONT_LOSS   = "7"  // 续亏
	PROFIT_NOTICE_CONT_PROF   = "8"  // 续盈
	PROFIT_NOTICE_FORECAST_DN = "9"  // 预减
	PROFIT_NOTICE_FORECAST_UP = "10" // 预增
	PROFIT_NOTICE_FLAT        = "11" // 持平
)
