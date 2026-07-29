package controller

import (
	"net/http"
	"strings"
)

func dailyDateRange(r *http.Request) (string, string) {
	return normalizeDateYYYYMMDD(r.URL.Query().Get("start_date")),
		normalizeDateYYYYMMDD(r.URL.Query().Get("end_date"))
}

func splitDailyQueryValues(value string) []string {
	var result []string
	for _, item := range strings.Split(value, ",") {
		if item = strings.TrimSpace(item); item != "" {
			result = append(result, item)
		}
	}
	return result
}
