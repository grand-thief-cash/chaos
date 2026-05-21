package dao

import (
	"context"
	"testing"
)

func TestWithSchemaCacheBypassMarksContext(t *testing.T) {
	ctx := WithSchemaCacheBypass(context.Background())
	if !shouldBypassSchemaCache(ctx) {
		t.Fatalf("expected schema cache bypass flag to be set")
	}
	if shouldBypassSchemaCache(context.Background()) {
		t.Fatalf("expected plain background context not to bypass schema cache")
	}
}
