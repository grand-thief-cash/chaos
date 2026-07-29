package model

type OptionMarketDataFilters struct {
	StartDate string
	EndDate   string
	Symbols   []string
	Exchanges []string
}

type OptionQVIXDaily struct {
	Symbol    string   `gorm:"primaryKey;column:symbol;type:varchar(16)" json:"symbol"`
	TradeDate string   `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	Open      *float64 `gorm:"column:open;type:numeric(20,6)" json:"open"`
	High      *float64 `gorm:"column:high;type:numeric(20,6)" json:"high"`
	Low       *float64 `gorm:"column:low;type:numeric(20,6)" json:"low"`
	Close     *float64 `gorm:"column:close;type:numeric(20,6)" json:"close"`
}

func (OptionQVIXDaily) TableName() string { return "ods.option_qvix_daily" }

type OptionDailyStats struct {
	Exchange                 string   `gorm:"primaryKey;column:exchange;type:varchar(8)" json:"exchange"`
	UnderlyingSymbol         string   `gorm:"primaryKey;column:underlying_symbol;type:varchar(16)" json:"underlying_symbol"`
	TradeDate                string   `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	UnderlyingName           string   `gorm:"column:underlying_name;type:varchar(64)" json:"underlying_name"`
	ContractCount            *int64   `gorm:"column:contract_count" json:"contract_count,omitempty"`
	Turnover                 *int64   `gorm:"column:turnover" json:"turnover,omitempty"`
	Volume                   *int64   `gorm:"column:volume" json:"volume,omitempty"`
	CallVolume               *int64   `gorm:"column:call_volume" json:"call_volume,omitempty"`
	PutVolume                *int64   `gorm:"column:put_volume" json:"put_volume,omitempty"`
	PutCallVolumeRatio       *float64 `gorm:"column:put_call_volume_ratio;type:numeric(20,6)" json:"put_call_volume_ratio,omitempty"`
	OpenInterest             *int64   `gorm:"column:open_interest" json:"open_interest,omitempty"`
	CallOpenInterest         *int64   `gorm:"column:call_open_interest" json:"call_open_interest,omitempty"`
	PutOpenInterest          *int64   `gorm:"column:put_open_interest" json:"put_open_interest,omitempty"`
	PutCallOpenInterestRatio *float64 `gorm:"column:put_call_open_interest_ratio;type:numeric(20,6)" json:"put_call_open_interest_ratio,omitempty"`
}

func (OptionDailyStats) TableName() string { return "ods.option_daily_stats" }
