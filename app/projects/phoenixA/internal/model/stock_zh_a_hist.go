package model

// StockZhAHistDaily represents daily stock history (Day).
// Table nomenclature: stock_zh_a_hist_daily_{adjust}
type StockZhAHistDaily struct {
	Date      string  `gorm:"primaryKey;type:date" json:"date"`
	Code      string  `gorm:"primaryKey;column:code;type:char(6)" json:"code"`
	Open      float64 `gorm:"type:decimal(20,2)" json:"open"`
	High      float64 `gorm:"type:decimal(20,2)" json:"high"`
	Low       float64 `gorm:"type:decimal(20,2)" json:"low"`
	Close     float64 `gorm:"type:decimal(20,2)" json:"close"`
	Preclose  float64 `gorm:"type:decimal(20,2)" json:"preclose"`
	Volume    int64   `json:"volume"`
	Amount    int64   `gorm:"type:bigint" json:"amount"`
	Turn      float64 `gorm:"type:decimal(20,2)" json:"turn"`
	PctChg    float64 `gorm:"column:pct_chg;type:decimal(20,2)" json:"pctChg"`
	PeTTM     float64 `gorm:"column:pe_ttm;type:decimal(20,2)" json:"peTTM"`
	PsTTM     float64 `gorm:"column:ps_ttm;type:decimal(20,2)" json:"psTTM"`
	PcfNcfTTM float64 `gorm:"column:pcf_ncf_ttm;type:decimal(20,2)" json:"pcfNcfTTM"`
	PbMRQ     float64 `gorm:"column:pb_mrq;type:decimal(20,2)" json:"pbMRQ"`
}

// StockZhAHistWeeklyMonthly represents weekly and monthly stock history.
// Table nomenclature: stock_zh_a_hist_{frequency}_{adjust}
// Frequency: weekly, monthly
type StockZhAHistWeeklyMonthly struct {
	Date   string  `gorm:"primaryKey;type:date" json:"date"`
	Code   string  `gorm:"primaryKey;column:code;type:char(6)" json:"code"`
	Open   float64 `gorm:"type:decimal(20,2)" json:"open"`
	High   float64 `gorm:"type:decimal(20,2)" json:"high"`
	Low    float64 `gorm:"type:decimal(20,2)" json:"low"`
	Close  float64 `gorm:"type:decimal(20,2)" json:"close"`
	Volume int64   `json:"volume"`
	Amount int64   `gorm:"type:bigint" json:"amount"`
	Turn   float64 `gorm:"type:decimal(20,2)" json:"turn"`
	PctChg float64 `gorm:"column:pct_chg;type:decimal(20,2)" json:"pctChg"`
}

// StockZhAHistMin represents minute-level stock history (5, 15, 30, 60).
// Table nomenclature: stock_zh_a_hist_min{frequency}_{adjust}
type StockZhAHistMin struct {
	Date   string  `gorm:"primaryKey;type:date" json:"date"`
	Time   string  `gorm:"primaryKey;column:time;type:varchar(20)" json:"time"` // YYYYMMDDHHMMSSsss
	Code   string  `gorm:"primaryKey;column:code;type:char(6)" json:"code"`
	Open   float64 `gorm:"type:decimal(20,2)" json:"open"`
	High   float64 `gorm:"type:decimal(20,2)" json:"high"`
	Low    float64 `gorm:"type:decimal(20,2)" json:"low"`
	Close  float64 `gorm:"type:decimal(20,2)" json:"close"`
	Volume int64   `json:"volume"`
	Amount int64   `gorm:"type:bigint" json:"amount"`
}
