package service

import (
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestTaxonomyCategoryFilterToken_DefaultUsesStableAllMarker(t *testing.T) {
	token := taxonomyCategoryFilterToken(nil)
	if token != "all" {
		t.Fatalf("unexpected token: %s", token)
	}
}

func TestTaxonomyCategoryFilterToken_SortsAttrsContainsKeys(t *testing.T) {
	name := "银行"
	level := uint8(1)
	f := &model.TaxonomyCategoryFilters{
		ParentCode: &name,
		Level:      &level,
		AttrsContains: map[string]interface{}{
			"b": 2,
			"a": 1,
		},
	}

	token := taxonomyCategoryFilterToken(f)
	expected := "parent_code=银行&level=1&attrs_contains.a=1&attrs_contains.b=2"
	if token != expected {
		t.Fatalf("unexpected token: %s", token)
	}
}

func TestPaginateItems_ReturnsStableWindow(t *testing.T) {
	items := []int{1, 2, 3, 4, 5}
	got := paginateItems(items, 2, 2)
	if len(got) != 2 || got[0] != 3 || got[1] != 4 {
		t.Fatalf("unexpected page slice: %+v", got)
	}
}
