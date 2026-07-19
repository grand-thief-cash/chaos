package service

import (
	"strings"
	"testing"

	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

func validManifestForTest() model.FeatureManifest {
	return model.FeatureManifest{
		Feature: model.FeatureDefinitionSpec{
			Code: "platform.security.constant_one", DisplayName: "Constant One",
			Kind: "metric", ValueType: "number", Tags: []string{"smoke", "control"},
		},
		Version: model.FeatureVersionSpec{Number: 1},
		Implementation: model.FeatureImplementationSpec{
			Kind: "python", ProducerService: "artemis", Backend: "pandas",
			Entrypoint: "features.constant_one", Config: map[string]any{"value": 1},
		},
	}
}

func TestNormalizeAndValidateManifestCanonicalizesStableChecksum(t *testing.T) {
	first := validManifestForTest()
	second := validManifestForTest()
	second.Feature.Tags = []string{"control", "smoke"}

	firstSnapshot, err := normalizeAndValidateManifest(&first)
	if err != nil {
		t.Fatalf("normalize first manifest: %v", err)
	}
	secondSnapshot, err := normalizeAndValidateManifest(&second)
	if err != nil {
		t.Fatalf("normalize second manifest: %v", err)
	}
	if first.Version.ManifestChecksum != second.Version.ManifestChecksum {
		t.Fatalf("canonical checksums differ: %s != %s", first.Version.ManifestChecksum, second.Version.ManifestChecksum)
	}
	if string(firstSnapshot) != string(secondSnapshot) {
		t.Fatalf("canonical snapshots differ:\n%s\n%s", firstSnapshot, secondSnapshot)
	}
	if first.Feature.EntityType != "security" || first.Version.Status != "draft" || first.Version.Frequency != "on_demand" {
		t.Fatalf("defaults were not applied: %#v %#v", first.Feature, first.Version)
	}
	if !isSHA256(first.Implementation.Checksum) || !isSHA256(first.Version.ManifestChecksum) {
		t.Fatal("implementation and manifest checksums must be SHA-256")
	}
	withoutTags := validManifestForTest()
	withoutTags.Feature.Tags = nil
	snapshot, err := normalizeAndValidateManifest(&withoutTags)
	if err != nil || strings.Contains(string(snapshot), `"tags":null`) {
		t.Fatalf("omitted tags must normalize to a JSON array: %s, %v", snapshot, err)
	}
}

func TestNormalizeAndValidateManifestRejectsCallerChecksumMismatch(t *testing.T) {
	manifest := validManifestForTest()
	manifest.Version.ManifestChecksum = strings.Repeat("f", 64)
	_, err := normalizeAndValidateManifest(&manifest)
	assertFeatureErrorCode(t, err, "MANIFEST_CHECKSUM_MISMATCH")
}

func TestNormalizeAndValidateManifestRejectsSensitiveConfig(t *testing.T) {
	manifest := validManifestForTest()
	manifest.Implementation.Config = map[string]any{"nested": map[string]any{"api_token": "secret"}}
	_, err := normalizeAndValidateManifest(&manifest)
	assertFeatureErrorCode(t, err, "SENSITIVE_CONFIG_FORBIDDEN")

	manifest = validManifestForTest()
	manifest.Implementation.Config = map[string]any{"api_token_ref": "vault/path"}
	if _, err := normalizeAndValidateManifest(&manifest); err != nil {
		t.Fatalf("secret references should be allowed: %v", err)
	}
}

func TestNormalizeAndValidateManifestRequiresExactDependencies(t *testing.T) {
	manifest := validManifestForTest()
	manifest.Dependencies = []model.FeatureDependencySpec{{Kind: "feature", FeatureCode: "platform.security.upstream"}}
	_, err := normalizeAndValidateManifest(&manifest)
	assertFeatureErrorCode(t, err, "FEATURE_DEPENDENCY_INVALID")

	manifest = validManifestForTest()
	manifest.Dependencies = []model.FeatureDependencySpec{
		{Kind: "data_field", Source: "vendor", Dataset: "financial", DataType: "balance", RawField: "assets"},
	}
	_, err = normalizeAndValidateManifest(&manifest)
	assertFeatureErrorCode(t, err, "DATA_FIELD_DEPENDENCY_INVALID")
}

func assertFeatureErrorCode(t *testing.T, err error, want string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected %s error", want)
	}
	typed, ok := err.(*model.FeaturePlatformError)
	if !ok || typed.Code != want {
		t.Fatalf("error = %#v, want FeaturePlatformError code %s", err, want)
	}
}
