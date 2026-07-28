package controller

import (
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestValidateSecurityEntityLinks(t *testing.T) {
	valid := []*model.AtlasSecurityEntityLink{{
		EntityID:         "af99c598-e49b-48a9-b0c6-30c61ae362e4",
		SecurityID:       42,
		Confidence:       0.95,
		ResolutionMethod: "SECURITY_REGISTRY_EXACT",
	}}
	if err := validateSecurityEntityLinks(valid); err != nil {
		t.Fatalf("expected valid link, got %v", err)
	}

	invalid := []*model.AtlasSecurityEntityLink{{
		EntityID:         "not-a-uuid",
		SecurityID:       0,
		Confidence:       1.1,
		ResolutionMethod: "",
	}}
	if err := validateSecurityEntityLinks(invalid); err == nil {
		t.Fatal("expected invalid link to be rejected")
	}
}

func TestValidateAtlasEntities(t *testing.T) {
	valid := []*model.AtlasKnowledgeEntity{{
		ID:              "af99c598-e49b-48a9-b0c6-30c61ae362e4",
		CanonicalName:   "Company A",
		NormalizedName:  "companya",
		EntityType:      "COMPANY",
		ResolutionState: "PROVISIONAL",
		Attributes:      []byte(`{}`),
	}}
	if err := validateAtlasEntities(valid); err != nil {
		t.Fatalf("expected valid entity, got %v", err)
	}
	valid[0].NormalizedName = ""
	if err := validateAtlasEntities(valid); err == nil {
		t.Fatal("expected entity without normalized name to be rejected")
	}
}

func TestValidateEntityAliases(t *testing.T) {
	valid := []*model.AtlasEntityAlias{{
		EntityID:        "af99c598-e49b-48a9-b0c6-30c61ae362e4",
		Alias:           "NVIDIA",
		NormalizedAlias: "nvidia",
		Source:          "REPORT_EASTMONEY",
	}}
	if err := validateEntityAliases(valid); err != nil {
		t.Fatalf("expected valid alias, got %v", err)
	}
	valid[0].NormalizedAlias = ""
	if err := validateEntityAliases(valid); err == nil {
		t.Fatal("expected empty normalized alias to be rejected")
	}
}

func TestValidateAtlasClaims(t *testing.T) {
	subjectID := "af99c598-e49b-48a9-b0c6-30c61ae362e4"
	objectID := "65698804-504f-48dc-89fc-72689230d632"
	valid := []*model.AtlasClaim{{
		ID:                 "46f2b508-fd84-4d82-a8c2-dc13fa9700a1",
		ClaimType:          "RELATION",
		SourceDocumentID:   "eastmoney:report-1",
		SubjectEntityID:    &subjectID,
		ObjectEntityID:     &objectID,
		CanonicalPredicate: "SUPPLIES_TO",
		AssertionType:      "OBSERVED_FACT",
		Status:             "ACCEPTED",
		Payload:            []byte(`{"evidence_quote":"Company A supplies Company B"}`),
	}}
	if err := validateAtlasClaims(valid); err != nil {
		t.Fatalf("expected valid claim, got %v", err)
	}

	invalid := *valid[0]
	invalid.AssertionType = "MADE_UP"
	if err := validateAtlasClaims([]*model.AtlasClaim{&invalid}); err == nil {
		t.Fatal("expected unknown assertion type to be rejected")
	}

	invalid = *valid[0]
	invalid.Payload = []byte(`[]`)
	if err := validateAtlasClaims([]*model.AtlasClaim{&invalid}); err == nil {
		t.Fatal("expected non-object claim payload to be rejected")
	}
}
