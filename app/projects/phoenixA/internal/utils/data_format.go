package utils

import "time"

func NormalizedToYYYYMMDD(date string) string {
	// Normalize to YYYY-MM-DD
	var res string
	if len(date) >= 10 {
		if t1, err1 := time.Parse(time.RFC3339, date); err1 == nil {
			res = t1.Format("2006-01-02")
		} else if t2, err2 := time.Parse("2006-01-02 15:04:05", date); err2 == nil {
			res = t2.Format("2006-01-02")
		} else {
			res = date[:10]
		}
	} else {
		res = date
	}
	return res
}
