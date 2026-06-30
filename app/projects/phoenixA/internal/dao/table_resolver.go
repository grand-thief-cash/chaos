package dao

import "fmt"

// BarsTableName returns the standard bars table name.
// Pattern: ods.bars_{assetType}_{market}_{period}_{adjust}
func BarsTableName(assetType, market, period, adjust string) string {
	return fmt.Sprintf("ods.bars_%s_%s_%s_%s", assetType, market, period, adjust)
}

// BarsExtTableName returns the extension table name for a specific source.
// Pattern: ods.bars_ext_{source}_{assetType}_{market}_{period}
func BarsExtTableName(source, assetType, market, period string) string {
	return fmt.Sprintf("ods.bars_ext_%s_%s_%s_%s", source, assetType, market, period)
}
