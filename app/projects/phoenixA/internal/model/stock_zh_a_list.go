package model

// StockZhAList represents an A-share stock basic info list.
//
// Table schema constraints (see migrations/0001_init.sql):
// - code: CHAR(6), primary key
// - exchange: CHAR(2) with values SH/SZ/BJ
// - no soft delete
// - no created_at/updated_at
//
// NOTE: keep field names and tags consistent with migrations.
type StockZhAList struct {
	Code     string `gorm:"primaryKey;type:char(6);not null" json:"code"`
	Company  string `gorm:"type:varchar(128);not null;default:''" json:"company"`
	Exchange string `gorm:"type:char(2);not null" json:"exchange"`
}

func (StockZhAList) TableName() string { return "stock_zh_a_list" }

// StockZhAListFilters provides optional list query conditions.
type StockZhAListFilters struct {
	Exchange string
	Code     string
	Codes    []string
	Company  string
}
