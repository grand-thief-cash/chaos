package dao

func getHistDataTableName(period, adjust string) string {
	return "stock_zh_a_hist_" + period + "_" + adjust
}
