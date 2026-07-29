package controller

import (
	"net/http/httptest"
	"reflect"
	"testing"
)

func TestMarketObservationFiltersSecurityIDsAreOptional(t *testing.T) {
	req := httptest.NewRequest(
		"GET",
		"/api/v2/market-observations/akshare?start_date=2026-07-28",
		nil,
	)

	filters, err := marketObservationFilters(req)
	if err != nil {
		t.Fatalf("marketObservationFilters() unexpected error: %v", err)
	}
	if len(filters.SecurityIDs) != 0 {
		t.Fatalf("expected no security ID filter, got %v", filters.SecurityIDs)
	}
}

func TestMarketObservationFiltersValidatesProvidedSecurityIDs(t *testing.T) {
	req := httptest.NewRequest(
		"GET",
		"/api/v2/market-observations/akshare?security_ids=11,12",
		nil,
	)

	filters, err := marketObservationFilters(req)
	if err != nil {
		t.Fatalf("marketObservationFilters() unexpected error: %v", err)
	}
	if want := []uint64{11, 12}; !reflect.DeepEqual(filters.SecurityIDs, want) {
		t.Fatalf("security IDs = %v, want %v", filters.SecurityIDs, want)
	}

	invalid := httptest.NewRequest(
		"GET",
		"/api/v2/market-observations/akshare?security_ids=",
		nil,
	)
	if _, err := marketObservationFilters(invalid); err == nil {
		t.Fatal("expected an error for an explicitly empty security_ids filter")
	}
}
