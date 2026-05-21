package consts

import (
	"fmt"
	"strings"
)

const (
	RedisCacheKeyPrefixSecurityList                 = "phoenixa:cache:v1:security:list"
	RedisCacheKeyPrefixSecurityCount                = "phoenixa:cache:v1:security:count"
	RedisCacheKeyPrefixSchemaFields                 = "phoenixa:cache:v1:schema:fields"
	RedisCacheKeyPrefixJSONBKeys                    = "phoenixa:cache:v1:schema:jsonb_keys"
	RedisCacheKeyPrefixTaxonomyCategoryList         = "phoenixa:cache:v1:taxonomy:category:list"
	RedisCacheKeyPrefixTaxonomyCategoryGet          = "phoenixa:cache:v1:taxonomy:category:get"
	RedisCacheKeyPrefixTaxonomyMappingBySymbol      = "phoenixa:cache:v1:taxonomy:mapping:by_symbol"
	RedisCacheKeyPrefixTaxonomyMappingByCategory    = "phoenixa:cache:v1:taxonomy:mapping:by_category"
	RedisCacheKeyPrefixTaxonomyConstituentsByIndex  = "phoenixa:cache:v1:taxonomy:constituents:by_index"
	RedisCacheKeyPrefixTaxonomyConstituentsBySymbol = "phoenixa:cache:v1:taxonomy:constituents:by_symbol"

	RedisCacheTTLSecondsSecurityList                 = 6 * 60 * 60
	RedisCacheTTLSecondsSecurityCount                = 30 * 60
	RedisCacheTTLSecondsSchemaFields                 = 30 * 60
	RedisCacheTTLSecondsJSONBKeys                    = 30 * 60
	RedisCacheTTLSecondsTaxonomyCategoryList         = 30 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyCategoryGet          = 30 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyMappingBySymbol      = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyMappingByCategory    = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyConstituentsByIndex  = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyConstituentsBySymbol = 14 * 24 * 60 * 60
)

func BuildSecurityListCacheKey(assetType, market string) string {
	return fmt.Sprintf("%s:%s:%s", RedisCacheKeyPrefixSecurityList, normalizeCachePart(assetType), normalizeCachePart(market))
}

func BuildSecurityCountCacheKey(assetType, market string) string {
	return fmt.Sprintf("%s:%s:%s", RedisCacheKeyPrefixSecurityCount, normalizeCachePart(assetType), normalizeCachePart(market))
}

func BuildSecurityListCachePattern(assetType, market string) string {
	return fmt.Sprintf("%s:%s:%s", RedisCacheKeyPrefixSecurityList, normalizeCachePatternPart(assetType), normalizeCachePatternPart(market))
}

func BuildSecurityCountCachePattern(assetType, market string) string {
	return fmt.Sprintf("%s:%s:%s", RedisCacheKeyPrefixSecurityCount, normalizeCachePatternPart(assetType), normalizeCachePatternPart(market))
}

func BuildSchemaFieldsCacheKey(domain, dataType string, sampleSize int) string {
	return fmt.Sprintf("%s:%s:%s:%d", RedisCacheKeyPrefixSchemaFields, normalizeCachePart(domain), normalizeCachePart(dataType), sampleSize)
}

func BuildJSONBKeysCacheKey(schema, table, column string, sampleSize int) string {
	return fmt.Sprintf("%s:%s:%s:%s:%d", RedisCacheKeyPrefixJSONBKeys, normalizeCachePart(schema), normalizeCachePart(table), normalizeCachePart(column), sampleSize)
}

func BuildTaxonomyCategoryListCacheKey(source, taxonomy, market, filterToken string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyCategoryList, normalizeCachePart(source), normalizeCachePart(taxonomy), normalizeCachePart(market), normalizeCachePart(filterToken))
}

func BuildTaxonomyCategoryListCachePattern(source, taxonomy, market string) string {
	return fmt.Sprintf("%s:%s:%s:%s:*", RedisCacheKeyPrefixTaxonomyCategoryList, normalizeCachePatternPart(source), normalizeCachePatternPart(taxonomy), normalizeCachePatternPart(market))
}

func BuildTaxonomyCategoryGetCacheKey(source, taxonomy, market, code string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyCategoryGet, normalizeCachePart(source), normalizeCachePart(taxonomy), normalizeCachePart(market), normalizeCachePart(code))
}

func BuildTaxonomyCategoryGetCachePattern(source, taxonomy, market string) string {
	return fmt.Sprintf("%s:%s:%s:%s:*", RedisCacheKeyPrefixTaxonomyCategoryGet, normalizeCachePatternPart(source), normalizeCachePatternPart(taxonomy), normalizeCachePatternPart(market))
}

func BuildTaxonomyMappingBySymbolCacheKey(symbol string) string {
	return fmt.Sprintf("%s:%s", RedisCacheKeyPrefixTaxonomyMappingBySymbol, normalizeCachePart(symbol))
}

func BuildTaxonomyMappingBySymbolCachePattern() string {
	return RedisCacheKeyPrefixTaxonomyMappingBySymbol + ":*"
}

func BuildTaxonomyMappingByCategoryCacheKey(source, taxonomy, categoryCode string) string {
	return fmt.Sprintf("%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyMappingByCategory, normalizeCachePart(source), normalizeCachePart(taxonomy), normalizeCachePart(categoryCode))
}

func BuildTaxonomyMappingByCategoryCachePattern(source, taxonomy, categoryCode string) string {
	return fmt.Sprintf("%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyMappingByCategory, normalizeCachePatternPart(source), normalizeCachePatternPart(taxonomy), normalizeCachePatternPart(categoryCode))
}

func BuildTaxonomyConstituentsByIndexCacheKey(source, taxonomy, market, indexCode string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyConstituentsByIndex, normalizeCachePart(source), normalizeCachePart(taxonomy), normalizeCachePart(market), normalizeCachePart(indexCode))
}

func BuildTaxonomyConstituentsByIndexCachePattern(source, taxonomy, market, indexCode string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyConstituentsByIndex, normalizeCachePatternPart(source), normalizeCachePatternPart(taxonomy), normalizeCachePatternPart(market), normalizeCachePatternPart(indexCode))
}

func BuildTaxonomyConstituentsBySymbolCacheKey(source, taxonomy, market, symbol string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyConstituentsBySymbol, normalizeCachePart(source), normalizeCachePart(taxonomy), normalizeCachePart(market), normalizeCachePart(symbol))
}

func BuildTaxonomyConstituentsBySymbolCachePattern(source, taxonomy, market, symbol string) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s", RedisCacheKeyPrefixTaxonomyConstituentsBySymbol, normalizeCachePatternPart(source), normalizeCachePatternPart(taxonomy), normalizeCachePatternPart(market), normalizeCachePatternPart(symbol))
}

func normalizeCachePart(v string) string {
	v = strings.TrimSpace(strings.ToLower(v))
	if v == "" {
		return "_"
	}
	v = strings.ReplaceAll(v, " ", "_")
	v = strings.ReplaceAll(v, "/", "_")
	v = strings.ReplaceAll(v, ":", "_")
	return v
}

func normalizeCachePatternPart(v string) string {
	v = strings.TrimSpace(v)
	if v == "" {
		return "*"
	}
	return normalizeCachePart(v)
}
