package model

import "encoding/json"

type MarketObservationFilters struct {
	StartDate        string
	EndDate          string
	SecurityIDs      []uint64
	ObservationTypes []string
}

// MarketObservationDaily stores scalar time series vertically. Tradable
// instruments with OHLC data use the standard bars tables instead.
type MarketObservationDaily struct {
	SecurityID      uint64          `gorm:"primaryKey;column:security_id" json:"security_id"`
	TradeDate       string          `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	ObservationType string          `gorm:"primaryKey;column:observation_type;type:varchar(32)" json:"observation_type"`
	Source          string          `gorm:"primaryKey;column:source;type:varchar(32)" json:"source,omitempty"`
	Value           float64         `gorm:"column:value;type:numeric(30,10)" json:"value"`
	Unit            string          `gorm:"column:unit;type:varchar(32)" json:"unit"`
	ExtraJSON       json.RawMessage `gorm:"column:extra_json;type:jsonb" json:"extra_json,omitempty"`
}

func (MarketObservationDaily) TableName() string {
	return "ods.market_observation_daily"
}
