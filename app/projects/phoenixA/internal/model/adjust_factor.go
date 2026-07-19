package model

// AdjustFactor stores market adjust factor rows used to reconstruct adjusted bars.
// Table: adjust_factor
// Unique key: (security_id, source, divid_operate_date)
// security_id is a logical FK to ods.security_registry.id (no real FK constraint, refactor §6 R9).
type AdjustFactor struct {
	ID               uint64   `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID       uint64   `gorm:"column:security_id;not null;uniqueIndex:uk_adjust_factor;index:idx_af_security_date" json:"security_id"`
	Source           string   `gorm:"type:varchar(32);not null;uniqueIndex:uk_adjust_factor" json:"source"`
	DividOperateDate string   `gorm:"column:divid_operate_date;type:varchar(10);not null;uniqueIndex:uk_adjust_factor;index:idx_af_security_date;index:idx_af_operate_date" json:"divid_operate_date"`
	ForeAdjustFactor *float64 `gorm:"column:fore_adjust_factor;type:numeric(20,8)" json:"fore_adjust_factor,omitempty"`
	BackAdjustFactor *float64 `gorm:"column:back_adjust_factor;type:numeric(20,8)" json:"back_adjust_factor,omitempty"`
	AdjustFactor     *float64 `gorm:"column:adjust_factor;type:numeric(20,8)" json:"adjust_factor,omitempty"`
}

func (AdjustFactor) TableName() string { return "ods.adjust_factor" }

type AdjustFactorFilters struct {
	SecurityID  uint64
	SecurityIDs []uint64
	StartDate   string
	EndDate     string
	Fields      []string
}
