package consts

import (
	"fmt"
	"strings"
)

const (
	RedisCacheKeyPrefixSecurityList         = "phoenixa:v1:security:list"
	RedisCacheKeyPrefixSecurityCount        = "phoenixa:v1:security:count"
	RedisCacheKeyPrefixSchemaFields         = "phoenixa:v1:schema:fields"
	RedisCacheKeyPrefixJSONBKeys            = "phoenixa:v1:schema:jsonb_keys"
	RedisCacheKeyPrefixTaxonomyCategoryList = "phoenixa:v1:taxonomy:category:list"
	RedisCacheKeyPrefixTaxonomyCategoryGet  = "phoenixa:v1:taxonomy:category:get"
	// Phase 2 surrogate-key refactor: taxonomy mapping/constituent caches are keyed by
	// security_id / category_id (was symbol / index_code).
	RedisCacheKeyPrefixTaxonomyMappingBySecurity      = "phoenixa:v1:taxonomy:mapping:by_security"
	RedisCacheKeyPrefixTaxonomyMappingByCategory      = "phoenixa:v1:taxonomy:mapping:by_category"
	RedisCacheKeyPrefixTaxonomyConstituentsByCategory = "phoenixa:v1:taxonomy:constituents:by_category"
	RedisCacheKeyPrefixTaxonomyConstituentsBySecurity = "phoenixa:v1:taxonomy:constituents:by_security"

	RedisCacheTTLSecondsSecurityList                   = 6 * 60 * 60
	RedisCacheTTLSecondsSecurityCount                  = 30 * 60
	RedisCacheTTLSecondsSchemaFields                   = 30 * 60
	RedisCacheTTLSecondsJSONBKeys                      = 30 * 60
	RedisCacheTTLSecondsTaxonomyCategoryList           = 30 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyCategoryGet            = 30 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyMappingBySecurity      = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyMappingByCategory      = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyConstituentsByCategory = 14 * 24 * 60 * 60
	RedisCacheTTLSecondsTaxonomyConstituentsBySecurity = 14 * 24 * 60 * 60
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

// Phase 2: taxonomy mapping/constituent cache keys are keyed by surrogate id.
// normalizeCachePart on a uint64 just stringifies it.

func BuildTaxonomyMappingBySecurityCacheKey(securityID uint64) string {
	return fmt.Sprintf("%s:%d", RedisCacheKeyPrefixTaxonomyMappingBySecurity, securityID)
}

func BuildTaxonomyMappingBySecurityCachePattern() string {
	return RedisCacheKeyPrefixTaxonomyMappingBySecurity + ":*"
}

func BuildTaxonomyMappingByCategoryCacheKey(categoryID uint64) string {
	return fmt.Sprintf("%s:%d", RedisCacheKeyPrefixTaxonomyMappingByCategory, categoryID)
}

func BuildTaxonomyMappingByCategoryCachePattern() string {
	return RedisCacheKeyPrefixTaxonomyMappingByCategory + ":*"
}

func BuildTaxonomyConstituentsByCategoryCacheKey(categoryID uint64) string {
	return fmt.Sprintf("%s:%d", RedisCacheKeyPrefixTaxonomyConstituentsByCategory, categoryID)
}

func BuildTaxonomyConstituentsByCategoryCachePattern() string {
	return RedisCacheKeyPrefixTaxonomyConstituentsByCategory + ":*"
}

func BuildTaxonomyConstituentsBySecurityCacheKey(securityID uint64) string {
	return fmt.Sprintf("%s:%d", RedisCacheKeyPrefixTaxonomyConstituentsBySecurity, securityID)
}

func BuildTaxonomyConstituentsBySecurityCachePattern() string {
	return RedisCacheKeyPrefixTaxonomyConstituentsBySecurity + ":*"
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
