package controller

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDecodeFeatureJSONRequiresExactlyOneValue(t *testing.T) {
	tests := []struct {
		name       string
		body       string
		wantOK     bool
		wantStatus int
	}{
		{name: "single value", body: `{"value":1}`, wantOK: true, wantStatus: http.StatusOK},
		{name: "trailing value", body: `{"value":1}{"value":2}`, wantStatus: http.StatusBadRequest},
		{name: "unknown field", body: `{"other":1}`, wantStatus: http.StatusBadRequest},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(tt.body))
			recorder := httptest.NewRecorder()
			var target struct {
				Value int `json:"value"`
			}
			got := decodeFeatureJSON(recorder, req, &target)
			if got != tt.wantOK {
				t.Fatalf("decodeFeatureJSON() = %t, want %t", got, tt.wantOK)
			}
			if recorder.Code != tt.wantStatus {
				t.Fatalf("status = %d, want %d; body=%s", recorder.Code, tt.wantStatus, recorder.Body.String())
			}
		})
	}
}
