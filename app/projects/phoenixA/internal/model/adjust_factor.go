package model

// AdjustFactor stores market adjust factor rows used to reconstruct adjusted bars.
// Table: adjust_factor
// Unique key: (source, symbol, market, divid_operate_date)
type AdjustFactor struct {
	ID               uint64   `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	Source           string   `gorm:"type:varchar(32);not null;uniqueIndex:uk_adjust_factor" json:"source"`
	Symbol           string   `gorm:"type:varchar(32);not null;uniqueIndex:uk_adjust_factor;index:idx_af_symbol_date" json:"symbol"`
	Market           string   `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_adjust_factor" json:"market"`
	DividOperateDate string   `gorm:"column:divid_operate_date;type:varchar(10);not null;uniqueIndex:uk_adjust_factor;index:idx_af_symbol_date;index:idx_af_operate_date" json:"divid_operate_date"`
	ForeAdjustFactor *float64 `gorm:"column:fore_adjust_factor;type:numeric(20,8)" json:"fore_adjust_factor,omitempty"`
	BackAdjustFactor *float64 `gorm:"column:back_adjust_factor;type:numeric(20,8)" json:"back_adjust_factor,omitempty"`
	AdjustFactor     *float64 `gorm:"column:adjust_factor;type:numeric(20,8)" json:"adjust_factor,omitempty"`
}

func (AdjustFactor) TableName() string { return "ods.adjust_factor" }

type AdjustFactorFilters struct {
	Symbol    string
	Symbols   []string
	Market    string
	StartDate string
	EndDate   string
	Fields    []string
}
