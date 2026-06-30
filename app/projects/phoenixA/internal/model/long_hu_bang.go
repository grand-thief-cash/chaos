package model

// LongHuBang stores A-share long hu bang (龙虎榜) detail rows.
// Table: long_hu_bang
// Unique granularity: source + symbol + market + trade_date + reason_type + trader_name + flow_mark.
type LongHuBang struct {
	Source         string  `gorm:"type:varchar(32);not null;uniqueIndex:uk_long_hu_bang" json:"source"`
	Symbol         string  `gorm:"type:varchar(32);not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_symbol_date" json:"symbol"`
	Market         string  `gorm:"type:varchar(16);not null;default:'zh_a';uniqueIndex:uk_long_hu_bang;index:idx_lhb_symbol_date" json:"market"`
	TradeDate      string  `gorm:"type:varchar(10);not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_symbol_date;index:idx_lhb_trade_date;index:idx_lhb_reason_date" json:"trade_date"`
	SecurityName   string  `gorm:"type:varchar(128);not null;default:''" json:"security_name"`
	ReasonType     string  `gorm:"type:varchar(32);not null;uniqueIndex:uk_long_hu_bang;index:idx_lhb_reason_date" json:"reason_type"`
	ReasonTypeName string  `gorm:"type:varchar(256);not null;default:''" json:"reason_type_name"`
	TraderName     string  `gorm:"type:varchar(256);not null;uniqueIndex:uk_long_hu_bang" json:"trader_name"`
	FlowMark       int     `gorm:"type:smallint;not null;default:0;uniqueIndex:uk_long_hu_bang;index:idx_lhb_reason_date" json:"flow_mark"`
	ChangeRange    float64 `gorm:"type:numeric(20,6);not null;default:0" json:"change_range"`
	BuyAmount      float64 `gorm:"type:numeric(24,4);not null;default:0" json:"buy_amount"`
	SellAmount     float64 `gorm:"type:numeric(24,4);not null;default:0" json:"sell_amount"`
	TotalAmount    float64 `gorm:"type:numeric(24,4);not null;default:0" json:"total_amount"`
	TotalVolume    float64 `gorm:"type:numeric(24,4);not null;default:0" json:"total_volume"`
}

func (LongHuBang) TableName() string { return "ods.long_hu_bang" }

// LongHuBangFilters for querying long hu bang rows.
type LongHuBangFilters struct {
	Symbol     string
	Symbols    []string
	Market     string
	TradeDate  string
	StartDate  string
	EndDate    string
	ReasonType string
	TraderName string
	FlowMark   *int
	Fields     []string
}
