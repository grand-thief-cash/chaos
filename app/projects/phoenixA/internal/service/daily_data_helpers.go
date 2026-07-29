package service

func dailyDataQueryLimit(limit int) int {
	if limit <= 0 || limit > 5000 {
		return 1000
	}
	return limit
}
