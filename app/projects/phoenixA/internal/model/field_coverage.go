package model

import "time"

// FieldCoverageObservation is one row in data_field_coverage_observation.
// It records that `observed_key` was seen in `storage_table.data_json` for
// (dataset, source), and whether the field dictionary governs it.
type FieldCoverageObservation struct {
	Dataset      string    `gorm:"column:dataset" json:"dataset"`
	Source       string    `gorm:"column:source" json:"source"`
	StorageTable string    `gorm:"column:storage_table" json:"storage_table"`
	ObservedKey  string    `gorm:"column:observed_key" json:"observed_key"`
	Status       string    `gorm:"column:status" json:"status"` // governed | ungoverned
	SampleCount  int64     `gorm:"column:sample_count" json:"sample_count"`
	FirstSeenAt  time.Time `gorm:"column:first_seen_at" json:"first_seen_at"`
	LastSeenAt   time.Time `gorm:"column:last_seen_at" json:"last_seen_at"`
}

func (FieldCoverageObservation) TableName() string { return "govern.data_field_coverage_observation" }

// FieldCoverageScanResult summarizes a single dataset scan.
type FieldCoverageScanResult struct {
	Dataset         string   `json:"dataset"`
	Source          string   `json:"source"`
	StorageTable    string   `json:"storage_table"`
	RowsScanned     int64    `json:"rows_scanned"`
	DistinctKeys    int64    `json:"distinct_keys"`
	GovernedCount   int64    `json:"governed_count"`
	UngovernedCount int64    `json:"ungoverned_count"`
	UngovernedKeys  []string `json:"ungoverned_keys"`
	// Error is set when the scan for this dataset failed. Other datasets in
	// the same batch still complete; this lets callers see partial results.
	Error string `json:"error,omitempty"`
}

// FieldCoverageListResponse is the payload for GET /field-coverage.
type FieldCoverageListResponse struct {
	GeneratedAt  time.Time                  `json:"generated_at"`
	Dataset      string                     `json:"dataset,omitempty"`
	StatusFilter string                     `json:"status_filter,omitempty"`
	Count        int                        `json:"count"`
	Observations []FieldCoverageObservation `json:"observations"`
}
