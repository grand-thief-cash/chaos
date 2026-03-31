package model

// CategoryStockMap represents the mapping between categories and stocks.
type CategoryStockMap struct {
	CategoryCode string `gorm:"type:varchar(64);not null;uniqueIndex:uk_cat_stock" json:"category_code"`
	StockCode    string `gorm:"type:varchar(6);not null;uniqueIndex:uk_cat_stock" json:"stock_code"`
}

func (CategoryStockMap) TableName() string { return "category_stock_map" }
