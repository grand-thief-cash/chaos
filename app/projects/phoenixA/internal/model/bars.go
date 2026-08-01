package model

import "encoding/json"

// StandardBar is the universal OHLCV bar structure used across all asset types.
// Table naming: bars_{asset_type}_{market}_{period}_{adjust}
//
// security_id is the physical identity of every bars_* row and logically
// references ods.security_registry.id. Symbol is response-only display data;
// registry code/name changes do not rewrite historical facts.
//
// TradeDate is a legacy cross-period JSON/column name. Daily tables store DATE;
// intraday tables store TIMESTAMPTZ and the string carries the complete RFC3339
// bar timestamp. Do not truncate it without checking BarsQuery.Period.
type StandardBar struct {
	SecurityID uint64   `gorm:"primaryKey;column:security_id;not null" json:"security_id"`
	Symbol     string   `gorm:"-" json:"symbol,omitempty"`
	TradeDate  string   `gorm:"primaryKey;column:trade_date" json:"trade_date"`
	Open       float64  `gorm:"column:open;type:decimal(20,4)" json:"open"`
	High       float64  `gorm:"column:high;type:decimal(20,4)" json:"high"`
	Low        float64  `gorm:"column:low;type:decimal(20,4)" json:"low"`
	Close      float64  `gorm:"column:close;type:decimal(20,4)" json:"close"`
	Volume     *int64   `gorm:"column:volume" json:"volume"`
	Amount     *int64   `gorm:"column:amount;type:bigint" json:"amount"`
	Preclose   *float64 `gorm:"column:preclose;type:decimal(20,4)" json:"preclose,omitempty"`
	PctChg     *float64 `gorm:"column:pct_chg;type:decimal(10,4)" json:"pct_chg,omitempty"`
}

// BarsQuery is the unified security_id-native query parameter for bars data.
type BarsQuery struct {
	AssetType   string   `json:"asset_type"`
	Market      string   `json:"market"`
	Period      string   `json:"period"` // canonical: daily, weekly, min1, min5, ...
	Adjust      string   `json:"adjust"` // nf, qfq, hfq
	SecurityID  uint64   `json:"security_id,omitempty"`
	SecurityIDs []uint64 `json:"security_ids,omitempty"`
	StartDate   string   `json:"start_date"`
	EndDate     string   `json:"end_date"`
	Fields      []string `json:"fields,omitempty"`
	Limit       int      `json:"limit,omitempty"`
	Offset      int      `json:"offset,omitempty"`
}

// BarsUpsertMeta carries metadata for a bars upsert request.
type BarsUpsertMeta struct {
	ExtensionKind string `json:"extension_kind,omitempty"` // optional vendor-shaped extension schema
	Period        string `json:"period"`                   // daily, weekly, ...
	Adjust        string `json:"adjust"`                   // nf, qfq, hfq
}

// BarsUpsertRequest is the unified bars write request.
type BarsUpsertRequest struct {
	Meta BarsUpsertMeta  `json:"meta"`
	Bars json.RawMessage `json:"bars"`
	Ext  json.RawMessage `json:"ext,omitempty"`
}

// BarsExtBaostock holds extension columns from baostock.
type BarsExtBaostock struct {
	SecurityID  uint64   `gorm:"primaryKey;column:security_id;not null" json:"security_id"`
	TradeDate   string   `gorm:"primaryKey;column:trade_date;type:date" json:"trade_date"`
	Turn        *float64 `gorm:"column:turn;type:decimal(10,4)" json:"turn,omitempty"`
	PeTTM       *float64 `gorm:"column:pe_ttm;type:decimal(20,4)" json:"pe_ttm,omitempty"`
	PsTTM       *float64 `gorm:"column:ps_ttm;type:decimal(20,4)" json:"ps_ttm,omitempty"`
	PbMRQ       *float64 `gorm:"column:pb_mrq;type:decimal(20,4)" json:"pb_mrq,omitempty"`
	PcfNcfTTM   *float64 `gorm:"column:pcf_ncf_ttm;type:decimal(20,4)" json:"pcf_ncf_ttm,omitempty"`
	TradeStatus *int16   `gorm:"column:trade_status" json:"trade_status,omitempty"`
	IsST        *bool    `gorm:"column:is_st" json:"is_st,omitempty"`
}
