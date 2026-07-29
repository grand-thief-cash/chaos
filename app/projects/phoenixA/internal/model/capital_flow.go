package model

type CapitalFlowFilters struct {
	StartDate string
	EndDate   string
	Symbols   []string
}

type MarginSummaryDaily struct {
	TradeDate            string   `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	FinancingBalance     *float64 `gorm:"column:financing_balance;type:numeric(30,4)" json:"financing_balance,omitempty"`
	FinancingBuy         *float64 `gorm:"column:financing_buy;type:numeric(30,4)" json:"financing_buy,omitempty"`
	FinancingRepay       *float64 `gorm:"column:financing_repay;type:numeric(30,4)" json:"financing_repay,omitempty"`
	SecuritiesBalance    *float64 `gorm:"column:securities_balance;type:numeric(30,4)" json:"securities_balance,omitempty"`
	SecuritiesSellVolume *float64 `gorm:"column:securities_sell_volume;type:numeric(30,4)" json:"securities_sell_volume,omitempty"`
	MarginTotalBalance   *float64 `gorm:"column:margin_total_balance;type:numeric(30,4)" json:"margin_total_balance,omitempty"`
}

func (MarginSummaryDaily) TableName() string { return "ods.margin_summary_daily" }

type HSGTDaily struct {
	Symbol             string   `gorm:"primaryKey;column:symbol;type:varchar(16)" json:"symbol"`
	TradeDate          string   `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	NetBuy             *float64 `gorm:"column:net_buy;type:numeric(30,4)" json:"net_buy,omitempty"`
	BuyAmount          *float64 `gorm:"column:buy_amount;type:numeric(30,4)" json:"buy_amount,omitempty"`
	SellAmount         *float64 `gorm:"column:sell_amount;type:numeric(30,4)" json:"sell_amount,omitempty"`
	CumulativeNetBuy   *float64 `gorm:"column:cumulative_net_buy;type:numeric(30,4)" json:"cumulative_net_buy,omitempty"`
	CapitalInflow      *float64 `gorm:"column:capital_inflow;type:numeric(30,4)" json:"capital_inflow,omitempty"`
	QuotaBalance       *float64 `gorm:"column:quota_balance;type:numeric(30,4)" json:"quota_balance,omitempty"`
	HoldingMarketValue *float64 `gorm:"column:holding_market_value;type:numeric(30,4)" json:"holding_market_value,omitempty"`
	LeadingStockName   *string  `gorm:"column:leading_stock_name;type:varchar(64)" json:"leading_stock_name,omitempty"`
	LeadingStockSymbol *string  `gorm:"column:leading_stock_symbol;type:varchar(32)" json:"leading_stock_symbol,omitempty"`
	LeadingStockPctChg *float64 `gorm:"column:leading_stock_pct_chg;type:numeric(20,6)" json:"leading_stock_pct_chg,omitempty"`
	BenchmarkValue     *float64 `gorm:"column:benchmark_value;type:numeric(20,6)" json:"benchmark_value,omitempty"`
	BenchmarkPctChg    *float64 `gorm:"column:benchmark_pct_chg;type:numeric(20,6)" json:"benchmark_pct_chg,omitempty"`
}

func (HSGTDaily) TableName() string { return "ods.hsgt_daily" }
