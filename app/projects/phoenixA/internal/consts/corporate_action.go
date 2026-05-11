package consts

// Corporate action types stored in corporate_action.action_type
const (
	CORP_ACTION_DIVIDEND    = "dividend"
	CORP_ACTION_RIGHT_ISSUE = "right_issue"
	CORP_ACTION_BS_DIVIDEND = "bs_dividend" // baostock 除权除息
)

// Dividend progress codes (DIV_PROGRESS).
const (
	DIV_PROGRESS_BOARD_PLAN     = "1"  // 董事会预案
	DIV_PROGRESS_AGM_APPROVED   = "2"  // 股东大会通过
	DIV_PROGRESS_IMPLEMENTED    = "3"  // 实施
	DIV_PROGRESS_REJECTED       = "4"  // 未通过
	DIV_PROGRESS_STOPPED        = "12" // 停止实施
	DIV_PROGRESS_SH_PROPOSAL    = "17" // 股东提议
	DIV_PROGRESS_PRE_DISCLOSURE = "19" // 董事会预案预披露
)

// Right issue progress codes (PROGRESS).
const (
	RI_PROGRESS_BOARD_PLAN     = "1"  // 董事会预案
	RI_PROGRESS_AGM_APPROVED   = "2"  // 股东大会通过
	RI_PROGRESS_IMPLEMENTED    = "3"  // 实施
	RI_PROGRESS_REJECTED       = "4"  // 未通过
	RI_PROGRESS_CSRC_APPROVED  = "5"  // 证监会核准
	RI_PROGRESS_STOPPED        = "12" // 停止实施
	RI_PROGRESS_SH_PROPOSAL    = "17" // 股东提议
	RI_PROGRESS_PRE_DISCLOSURE = "19" // 董事会预案预披露
	RI_PROGRESS_REVIEW_PASSED  = "20" // 发审委通过
	RI_PROGRESS_REVIEW_FAILED  = "21" // 发审委未通过
	RI_PROGRESS_AGM_REJECTED   = "22" // 股东大会未通过
)
