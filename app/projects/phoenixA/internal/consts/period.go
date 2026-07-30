package consts

import "strings"

// Unified period values used across all projects.
// Use "period" as the canonical field name (not freq/timeframe).
const (
	PERIOD_MIN1    = "min1"
	PERIOD_MIN5    = "min5"
	PERIOD_MIN15   = "min15"
	PERIOD_MIN30   = "min30"
	PERIOD_MIN60   = "min60"
	PERIOD_DAILY   = "daily"
	PERIOD_WEEKLY  = "weekly"
	PERIOD_MONTHLY = "monthly"
)

// NormalizePeriod converts SDK/UI aliases to the cross-service canonical
// period values. New storage tables and cache paths must only use canonical
// values so that 5min and min5 cannot create parallel physical trees.
func NormalizePeriod(raw string) (string, bool) {
	value := strings.ToLower(strings.TrimSpace(raw))
	switch value {
	case "1min", "1m", PERIOD_MIN1:
		return PERIOD_MIN1, true
	case "5min", "5m", PERIOD_MIN5:
		return PERIOD_MIN5, true
	case "15min", "15m", PERIOD_MIN15:
		return PERIOD_MIN15, true
	case "30min", "30m", PERIOD_MIN30:
		return PERIOD_MIN30, true
	case "60min", "60m", PERIOD_MIN60:
		return PERIOD_MIN60, true
	case "d", PERIOD_DAILY:
		return PERIOD_DAILY, true
	case "w", PERIOD_WEEKLY:
		return PERIOD_WEEKLY, true
	case "m", PERIOD_MONTHLY:
		return PERIOD_MONTHLY, true
	default:
		return "", false
	}
}

func IsIntradayPeriod(period string) bool {
	normalized, ok := NormalizePeriod(period)
	if !ok {
		return false
	}
	switch normalized {
	case PERIOD_MIN1, PERIOD_MIN5, PERIOD_MIN15, PERIOD_MIN30, PERIOD_MIN60:
		return true
	default:
		return false
	}
}
