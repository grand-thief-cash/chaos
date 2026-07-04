package model

import "time"

// ─── Per-security data coverage models ───
//
// Returned by GET /api/v2/catalog/securities/{security_id}/datasets/summary.
// Describes how many rows of each dataset/data_type exist for a given security,
// plus the time range. This is a generic data-discovery API — not BI-specific.
// Callers (e.g., artemis BI layer) use it to show "this company has N quarterly
// balance sheets, M annual income statements" without running raw queries.

// CatalogSecurityCoverage is the top-level response.
type CatalogSecurityCoverage struct {
	GeneratedAt time.Time                `json:"generated_at"`
	SecurityID  uint64                   `json:"security_id"`
	Datasets    []CatalogDatasetCoverage `json:"datasets"`
}

// CatalogDatasetCoverage groups data_type stats under one dataset.
type CatalogDatasetCoverage struct {
	Dataset   string                    `json:"dataset"`
	Source    string                    `json:"source"`
	DataTypes []CatalogDataTypeCoverage `json:"data_types"`
}

// CatalogDataTypeCoverage holds row_count + time range for one data_type.
// For financial_statement, ByReportType breaks down further by report_type
// (1=Q1, 2=H1, 3=Q3, 4=FY). Other datasets leave ByReportType empty.
type CatalogDataTypeCoverage struct {
	DataType       string                    `json:"data_type"`
	TotalRows      int                       `json:"total_rows"`
	EarliestPeriod string                    `json:"earliest_period,omitempty"`
	LatestPeriod   string                    `json:"latest_period,omitempty"`
	LatestAnnDate  string                    `json:"latest_ann_date,omitempty"`
	ByReportType   []CatalogReportTypeBucket `json:"by_report_type,omitempty"`
}

// CatalogReportTypeBucket is a per-report_type row-count bucket.
type CatalogReportTypeBucket struct {
	ReportType     string `json:"report_type"`
	RowCount       int    `json:"row_count"`
	EarliestPeriod string `json:"earliest_period,omitempty"`
	LatestPeriod   string `json:"latest_period,omitempty"`
	LatestAnnDate  string `json:"latest_ann_date,omitempty"`
}
