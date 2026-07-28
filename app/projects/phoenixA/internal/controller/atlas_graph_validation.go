package controller

import (
	"fmt"

	"github.com/google/uuid"
)

func validateProjection(entities, claims []map[string]any) error {
	if len(entities) > 5000 || len(claims) > 10000 {
		return fmt.Errorf("projection batch exceeds limit")
	}
	entityIDs := make(map[string]bool, len(entities))
	for _, entity := range entities {
		id, _ := entity["id"].(string)
		name, _ := entity["canonical_name"].(string)
		entityType, _ := entity["entity_type"].(string)
		if uuid.Validate(id) != nil || name == "" || entityType == "" {
			return fmt.Errorf("every entity requires id, canonical_name and entity_type")
		}
		entityIDs[id] = true
	}
	for _, claim := range claims {
		id, _ := claim["id"].(string)
		subject, _ := claim["subject_entity_id"].(string)
		object, _ := claim["object_entity_id"].(string)
		predicate, _ := claim["canonical_predicate"].(string)
		assertionType, _ := claim["assertion_type"].(string)
		polarity, _ := claim["polarity"].(string)
		status, _ := claim["status"].(string)
		projectableAssertion := assertionType == "OBSERVED_FACT" ||
			assertionType == "COMPANY_DISCLOSURE"
		if uuid.Validate(id) != nil ||
			!entityIDs[subject] ||
			!entityIDs[object] ||
			predicate == "" ||
			!projectableAssertion ||
			polarity != "AFFIRMED" ||
			status != "ACCEPTED" {
			return fmt.Errorf(
				"claim must be an accepted affirmative fact with in-batch entities",
			)
		}
	}
	return nil
}
