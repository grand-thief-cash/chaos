package model

import (
	"encoding/json"
	"time"
)

// ResearchReport is the download-state tracker for a research-report PDF that
// artemis downloads from Eastmoney and sinks to MinIO. It is scoped to the
// DOWNLOAD TASK ONLY: enough to drive the full/incremental download lifecycle
// (what to fetch, where the PDF was stored, status) plus the few fields the
// user explicitly asked to record (source, pdf name, security_id, which
// brokerage produced it, report type). Research-report business content
// (ratings, predictions, industry, researcher, …) is captured in the Extra
// JSONB column as a convenience at list time - it is NOT modelled as typed
// columns.
//
// Table: ods.research_report_download_record
// resource_id is the source-defined report id (eastmoney infoCode).
// report_type: stock | industry | other (CHECK-constrained).
// The subject is held in TWO columns:
//   - SubjectSourceCode: raw subject code from the source (stock→symbol,
//     industry→industry code). Non-empty for stock/industry (CHECK-constrained). Used for the MinIO path and
//     for back-filling SubjectID.
//   - SubjectID: resolved project surrogate id (stock→security_registry.id,
//     industry→taxonomy_category.id). Both BIGINT. NULLable — NULL until the
//     subject is resolved from SubjectSourceCode. artemis does NOT skip
//     reports whose subject is unregistered (subject_id=NULL), so the list
//     cursor still advances past them and they are tracked.
type ResearchReport struct {
	ID                uint64          `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source            string          `gorm:"type:varchar(32);not null;uniqueIndex:uk_research_report_download_record" json:"source"`
	ResourceID        string          `gorm:"column:resource_id;type:varchar(64);not null;uniqueIndex:uk_research_report_download_record" json:"resource_id"` // source-defined report id (eastmoney infoCode)
	ReportType        string          `gorm:"column:report_type;type:varchar(16);not null;default:'stock'" json:"report_type"`                                // stock | industry | other
	SubjectID         *uint64         `gorm:"column:subject_id;index:idx_rrdlrec_subject_id" json:"subject_id,omitempty"`                                     // nullable — namespace per report_type (stock→security_id, industry→category_id)
	SubjectSourceCode string          `gorm:"column:subject_source_code;type:varchar(32);not null;default:''" json:"subject_source_code"`                     // raw subject code from source (always populated)
	PublishDate       string          `gorm:"type:varchar(10);not null;default:''" json:"publish_date"`                                                       // YYYY-MM-DD
	Title             string          `gorm:"type:varchar(512);not null;default:''" json:"title"`
	OrgName           string          `gorm:"type:varchar(128);not null;default:''" json:"org_name"` // which brokerage produced it
	DetailURL         string          `gorm:"column:detail_url;type:varchar(512);not null;default:''" json:"detail_url"`
	PDFURL            string          `gorm:"column:pdf_url;type:varchar(512);not null;default:''" json:"pdf_url"`                // filled after download
	PDFObjectKey      string          `gorm:"column:pdf_object_key;type:varchar(512);not null;default:''" json:"pdf_object_key"`  // MinIO object key
	Status            string          `gorm:"type:varchar(24);not null;default:'pending';index:idx_rrdlrec_status" json:"status"` // pending / downloaded / no_pdf / detail_error / pdf_error
	LastError         string          `gorm:"type:text;not null;default:''" json:"last_error"`
	Extra             json.RawMessage `gorm:"type:jsonb;not null;default:'{}'" json:"extra"` // report-content metadata (rating, predictions, industry, ...) as a JSONB object
	CreatedAt         time.Time       `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt         time.Time       `gorm:"autoUpdateTime" json:"updated_at"`
}

func (ResearchReport) TableName() string { return "ods.research_report_download_record" }

// ResearchReportFilters for querying research-report download records.
type ResearchReportFilters struct {
	SubjectID        uint64
	SubjectIDs       []uint64 // batch query for multiple subjects
	ResourceID       string
	ReportType       string
	Status           string
	PublishDateStart string // range: >= this (YYYY-MM-DD)
	PublishDateEnd   string // range: <= this (YYYY-MM-DD)
	Fields           []string
}
