package dao

func getHistDataTableName(frequency, adjust string) string {
	return "stock_zh_a_hist_" + frequency + "_" + adjust
}
