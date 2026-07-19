package dao

import (
	"reflect"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestNormalizeSecurityForUpsertCanonicalizesNaturalKey(t *testing.T) {
	row := &model.SecurityRegistry{
		ID:       999,
		Exchange: " sz ",
		Symbol:   " 000001 ",
		Name:     " 平安银行 ",
	}

	normalizeSecurityForUpsert(row)

	if row.ID != 0 {
		t.Fatalf("client-supplied ID must be discarded, got %d", row.ID)
	}
	if row.Exchange != "SZ" || row.Symbol != "000001" {
		t.Fatalf("natural key not canonicalized: exchange=%q symbol=%q", row.Exchange, row.Symbol)
	}
	if row.AssetType != "stock" || row.Market != "zh_a" || row.Status != "active" {
		t.Fatalf("defaults not applied: asset_type=%q market=%q status=%q", row.AssetType, row.Market, row.Status)
	}
	if row.Name != "平安银行" {
		t.Fatalf("name not trimmed: %q", row.Name)
	}
}

func TestSecurityUpsertPreservesPermanentIDContract(t *testing.T) {
	upsert := securityUpsertOnConflict()

	gotConflictColumns := make([]string, 0, len(upsert.Columns))
	for _, column := range upsert.Columns {
		gotConflictColumns = append(gotConflictColumns, column.Name)
	}
	wantConflictColumns := []string{"exchange", "asset_type", "symbol"}
	if !reflect.DeepEqual(gotConflictColumns, wantConflictColumns) {
		t.Fatalf("conflict target = %v, want %v", gotConflictColumns, wantConflictColumns)
	}

	for _, assignment := range upsert.DoUpdates {
		switch assignment.Column.Name {
		case "id", "exchange", "asset_type", "symbol":
			t.Fatalf("stable identity column %q must not be updated on conflict", assignment.Column.Name)
		}
	}
}
