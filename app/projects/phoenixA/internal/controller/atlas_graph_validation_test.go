package controller

import "testing"

func TestValidateProjectionRejectsDanglingClaim(t *testing.T) {
	entities := []map[string]any{{
		"id":             "af99c598-e49b-48a9-b0c6-30c61ae362e4",
		"canonical_name": "公司A", "entity_type": "COMPANY",
	}}
	claims := []map[string]any{{
		"id":                "91d7072c-0ee4-4cca-a577-8e00e166dfac",
		"subject_entity_id": "af99c598-e49b-48a9-b0c6-30c61ae362e4",
		"object_entity_id":  "missing", "canonical_predicate": "SUPPLIES",
		"assertion_type": "OBSERVED_FACT", "polarity": "AFFIRMED",
		"status": "ACCEPTED",
	}}
	if err := validateProjection(entities, claims); err == nil {
		t.Fatal("expected dangling claim to be rejected")
	}
}

func TestValidateProjectionRejectsOpinionClaim(t *testing.T) {
	subjectID := "af99c598-e49b-48a9-b0c6-30c61ae362e4"
	objectID := "139b347f-3291-4e03-92bc-6927b488c5c3"
	entities := []map[string]any{
		{"id": subjectID, "canonical_name": "A", "entity_type": "COMPANY"},
		{"id": objectID, "canonical_name": "B", "entity_type": "COMPANY"},
	}
	claims := []map[string]any{{
		"id":                  "91d7072c-0ee4-4cca-a577-8e00e166dfac",
		"subject_entity_id":   subjectID,
		"object_entity_id":    objectID,
		"canonical_predicate": "SUPPLIES",
		"assertion_type":      "ANALYST_OPINION",
		"polarity":            "AFFIRMED",
		"status":              "ACCEPTED",
	}}
	if err := validateProjection(entities, claims); err == nil {
		t.Fatal("expected analyst opinion to be rejected from fact projection")
	}
}
