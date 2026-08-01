package dao

import (
	"fmt"

	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
)

// BarsTableName returns the standard bars table name.
// Pattern: ods.bars_{assetType}_{market}_{period}_{adjust}
func BarsTableName(assetType, market, period, adjust string) string {
	if normalized, ok := bizConsts.NormalizePeriod(period); ok {
		period = normalized
	}
	return fmt.Sprintf("ods.bars_%s_%s_%s_%s", assetType, market, period, adjust)
}

// BarsExtTableName returns an optional extension-schema table name.
// Pattern: ods.bars_ext_{extensionKind}_{assetType}_{market}_{period}
func BarsExtTableName(extensionKind, assetType, market, period string) string {
	return fmt.Sprintf("ods.bars_ext_%s_%s_%s_%s", extensionKind, assetType, market, period)
}
