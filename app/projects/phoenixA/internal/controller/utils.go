package controller

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type apiError struct {
	Error string `json:"error"`
}

type apiResponse[T any] struct {
	Data T `json:"data"`
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func parseLimitOffset(r *http.Request) (limit, offset int) {
	q := r.URL.Query()
	if s := q.Get("limit"); s != "" {
		if v, err := strconv.Atoi(s); err == nil {
			limit = v
		}
	}
	if s := q.Get("offset"); s != "" {
		if v, err := strconv.Atoi(s); err == nil {
			offset = v
		}
	}
	return
}

// normalizeDateYYYYMMDD normalizes a date string to YYYY-MM-DD for JSON output.
func normalizeDateYYYYMMDD(s string) string {
	s = strings.TrimSpace(s)
	if s == "" {
		return s
	}
	// already YYYY-MM-DD or prefixed with it
	if len(s) >= 10 && s[4] == '-' && s[7] == '-' {
		return s[:10]
	}
	// try RFC3339 / RFC3339Nano (e.g. 2026-01-05T00:00:00+08:00)
	if t, err := time.Parse(time.RFC3339Nano, s); err == nil {
		return t.Format("2006-01-02")
	}
	if t, err := time.Parse(time.RFC3339, s); err == nil {
		return t.Format("2006-01-02")
	}
	return s
}

func parseFieldsParam(raw string) []string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	seen := make(map[string]struct{})
	for _, f := range parts {
		f = strings.TrimSpace(f)
		if f == "" {
			continue
		}
		if _, ok := seen[f]; ok {
			continue
		}
		seen[f] = struct{}{}
		out = append(out, f)
	}
	return out
}
