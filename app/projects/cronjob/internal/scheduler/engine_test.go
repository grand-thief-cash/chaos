package scheduler

import (
	"testing"
	"time"
)

func TestShouldFire(t *testing.T) {
	ts := time.Date(2025, 10, 14, 12, 34, 56, 0, time.UTC)
	if !shouldFire(ts, "56 34 12 * * *") {
		t.Fatalf("expected fire")
	}
	if shouldFire(ts, "55 34 12 * * *") {
		t.Fatalf("should not fire")
	}
}
