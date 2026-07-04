package model

import "time"

// LongHuBang stores A-share long hu bang (龙虎榜) detail rows.
// Table: long_hu_bang
// Unique granularity: security_id + source + trade_date + reason_type + trader_name + flow_mark.
// security_id is a logical FK to ods.security_registry.id (no real FK constraint, refactor §6 R9).
type LongHuBang struct {
	ID             uint64    `gorm:"primaryKey;autoIncrement" json:"id,omitempty"`
	SecurityID     uint64    `gorm:"column:security_id;not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_security_date" json:"security_id"`
	Source         string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_long_hu_bang" json:"source"`
	TradeDate      string    `gorm:"type:varchar(10);not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_security_date;index:idx_lhb_trade_date;index:idx_lhb_reason_date" json:"trade_date"`
	SecurityName   string    `gorm:"type:varchar(128);not null;default:''" json:"security_name"`
	ReasonType     string    `gorm:"type:varchar(32);not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_reason_date" json:"reason_type"`
	ReasonTypeName string    `gorm:"type:varchar(256);not null;default:''" json:"reason_type_name"`
	TraderName     string    `gorm:"type:varchar(256);not null;uniqueIndex:uk_long_hu_bang" json:"trader_name"`
	FlowMark       int       `gorm:"type:smallint;not null;default:0;uniqueIndex:uk_long_hu_bang;index:idx_lhb_reason_date" json:"flow_mark"`
	ChangeRange    float64   `gorm:"type:numeric(20,6);not null;default:0" json:"change_range"`
	BuyAmount      float64   `gorm:"type:numeric(24,4);not null;default:0" json:"buy_amount"`
	SellAmount     float64   `gorm:"type:numeric(24,4);not null;default:0" json:"sell_amount"`
	TotalAmount    float64   `gorm:"type:numeric(24,4);not null;default:0" json:"total_amount"`
	TotalVolume    float64   `gorm:"type:numeric(24,4);not null;default:0" json:"total_volume"`
	CreatedAt      time.Time `gorm:"autoCreateTime" json:"created_at"`
	UpdatedAt      time.Time `gorm:"autoUpdateTime" json:"updated_at"`
}

func (LongHuBang) TableName() string { return "ods.long_hu_bang" }

// LongHuBangFilters for querying long hu bang rows.
type LongHuBangFilters struct {
	SecurityID  uint64
	SecurityIDs []uint64
	TradeDate   string
	StartDate   string
	EndDate     string
	ReasonType  string
	TraderName  string
	FlowMark    *int
	Fields      []string
}
