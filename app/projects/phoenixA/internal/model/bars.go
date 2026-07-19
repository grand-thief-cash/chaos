package model

import "encoding/json"

// StandardBar is the universal OHLCV bar structure used across all asset types.
// Table naming: bars_{asset_type}_{market}_{period}_{adjust}
//
// security_id is a response-only decoration (gorm:"-", refactor §10.b): bars_*
// physical tables keep symbol as their primary key (§3.2 permanent-storage
// exception), so the controller resolves security_id → symbol at the API
// boundary and stamps security_id back onto the rows for display. It is not a
// DB column and gorm ignores it on read/write.
type StandardBar struct {
	SecurityID uint64  `gorm:"-" json:"security_id,omitempty"`
	Symbol     string  `gorm:"primaryKey;column:symbol;type:varchar(32)" json:"symbol"`
	TradeDate  string  `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	Open       float64 `gorm:"column:open;type:decimal(20,4)" json:"open"`
	High       float64 `gorm:"column:high;type:decimal(20,4)" json:"high"`
	Low        float64 `gorm:"column:low;type:decimal(20,4)" json:"low"`
	Close      float64 `gorm:"column:close;type:decimal(20,4)" json:"close"`
	Volume     int64   `gorm:"column:volume" json:"volume"`
	Amount     int64   `gorm:"column:amount;type:bigint" json:"amount"`
	Preclose   float64 `gorm:"column:preclose;type:decimal(20,4)" json:"preclose,omitempty"`
	PctChg     float64 `gorm:"column:pct_chg;type:decimal(10,4)" json:"pct_chg,omitempty"`
}

// BarsQuery is the unified query parameter for bars data. Identity is the
// resolved physical symbol; the controller resolves security_id → symbol before
// building a BarsQuery, so there is no SecurityID field here (the bars DAO
// filters by symbol, the §3.2 physical key).
type BarsQuery struct {
	AssetType string   `json:"asset_type"`
	Market    string   `json:"market"`
	Period    string   `json:"period"` // daily, weekly, min5, ...
	Adjust    string   `json:"adjust"` // nf, qfq, hfq
	Symbol    string   `json:"symbol,omitempty"`
	Symbols   []string `json:"symbols,omitempty"`
	StartDate string   `json:"start_date"`
	EndDate   string   `json:"end_date"`
	Fields    []string `json:"fields,omitempty"`
	Source    string   `json:"source,omitempty"`
	Limit     int      `json:"limit,omitempty"`
	Offset    int      `json:"offset,omitempty"`
}

// BarsUpsertMeta carries metadata for a bars upsert request.
type BarsUpsertMeta struct {
	Source string `json:"source,omitempty"` // data source: baostock, akshare, ...
	Period string `json:"period"`           // daily, weekly, ...
	Adjust string `json:"adjust"`           // nf, qfq, hfq
	Symbol string `json:"symbol,omitempty"` // optional if each bar row includes symbol
}

// BarsUpsertRequest is the unified bars write request.
type BarsUpsertRequest struct {
	Meta BarsUpsertMeta  `json:"meta"`
	Bars json.RawMessage `json:"bars"`
	Ext  json.RawMessage `json:"ext,omitempty"`
}

// BarsExtBaostock holds extension columns from baostock.
type BarsExtBaostock struct {
	Symbol    string  `gorm:"primaryKey;column:symbol;type:varchar(32)" json:"symbol"`
	TradeDate string  `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	Turn      float64 `gorm:"column:turn;type:decimal(10,4)" json:"turn,omitempty"`
	PeTTM     float64 `gorm:"column:pe_ttm;type:decimal(20,4)" json:"pe_ttm,omitempty"`
	PsTTM     float64 `gorm:"column:ps_ttm;type:decimal(20,4)" json:"ps_ttm,omitempty"`
	PbMRQ     float64 `gorm:"column:pb_mrq;type:decimal(20,4)" json:"pb_mrq,omitempty"`
	PcfNcfTTM float64 `gorm:"column:pcf_ncf_ttm;type:decimal(20,4)" json:"pcf_ncf_ttm,omitempty"`
}
