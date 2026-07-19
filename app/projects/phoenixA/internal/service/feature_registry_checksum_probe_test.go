package service

import (
	"encoding/json"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func TestArtemisPhaseTwoChecksumProbe(t *testing.T) {
	raw := `{"feature":{"code":"platform.security.constant_one","display_name":"Platform Constant One","description":"Feature Platform end-to-end acceptance probe. It emits 1.0 for every frozen RunSubject and must not be used for research, selection or backtests.","kind":"metric","entity_type":"security","value_type":"number","unit":"scalar","category":"platform","owner":"platform","tags":["internal","smoke"]},"version":{"number":1,"status":"published","frequency":"on_demand","as_of_semantics":"snapshot","missing_policy":"explicit_missing","manifest_checksum":"6761eb8c0652bc3bf7609fe145d6d5e1b17bf75d7e319dd066bcd62251a26492"},"implementation":{"kind":"python","producer_service":"artemis","backend":"python","entrypoint":"artemis.feature_platform.plugins.smoke.constant_one:ConstantOneFeature","implementation_revision":1,"config":{},"checksum":"f310bb02dd170455d24d8370ee3aa706e213224ab81afc0024cb6555324108cf","status":"active"},"dependencies":[]}`
	var manifest model.FeatureManifest
	if err := json.Unmarshal([]byte(raw), &manifest); err != nil {
		t.Fatal(err)
	}
	if _, err := normalizeAndValidateManifest(&manifest); err != nil {
		t.Fatalf("Artemis checksum projection rejected: %v", err)
	}
}
