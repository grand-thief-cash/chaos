package consts

import "testing"

func TestNormalizePeriodAliases(t *testing.T) {
	tests := map[string]string{
		"1min":  PERIOD_MIN1,
		"min1":  PERIOD_MIN1,
		"5min":  PERIOD_MIN5,
		"min5":  PERIOD_MIN5,
		"15m":   PERIOD_MIN15,
		"daily": PERIOD_DAILY,
	}
	for input, expected := range tests {
		actual, ok := NormalizePeriod(input)
		if !ok || actual != expected {
			t.Fatalf("NormalizePeriod(%q) = %q, %v; want %q, true", input, actual, ok, expected)
		}
	}
	if _, ok := NormalizePeriod("min2"); ok {
		t.Fatal("unsupported period must fail closed")
	}
}

func TestIsIntradayPeriod(t *testing.T) {
	if !IsIntradayPeriod("5min") || !IsIntradayPeriod(PERIOD_MIN1) {
		t.Fatal("minute aliases must be intraday")
	}
	if IsIntradayPeriod(PERIOD_DAILY) || IsIntradayPeriod("invalid") {
		t.Fatal("daily/invalid periods must not be intraday")
	}
}
