package service

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/grand-thief-cash/chaos/app/infra/go/application/components/logging"
	"github.com/grand-thief-cash/chaos/app/infra/go/application/core"
	bizConsts "github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/consts"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/dao"
	"github.com/grand-thief-cash/chaos/app/projects/phoenixA/internal/model"
)

// ─── Static metadata registry ───

type tableMeta struct {
	Domain      string
	Description string
	TimeColumn  string
	Lineage     *model.DataLineage
}

// tableMetaRegistry maps table names (or patterns) to static metadata.
// Entries with "*" are matched using hasPrefix logic.
var tableMetaRegistry = map[string]tableMeta{
	// Bars
	"bars_": {
		Domain:      "bars",
		Description: "行情数据（K线）",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/bars/{asset_type}/{market}/upsert",
		},
	},
	"bars_ext_": {
		Domain:      "bars",
		Description: "行情扩展指标",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert (extension)",
			RefreshSchedule: "每日增量",
		},
	},
	// Security
	"security_registry": {
		Domain:      "security",
		Description: "证券注册表（股票/ETF/指数基础信息）",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日全量",
			APIEndpoint:     "POST /api/v2/securities/upsert",
		},
	},
	// Taxonomy
	"taxonomy_category": {
		Domain:      "taxonomy",
		Description: "分类节点（行业/概念/地域）",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
		},
	},
	"taxonomy_security_map": {
		Domain:      "taxonomy",
		Description: "证券-分类映射关系",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API replace",
			RefreshSchedule: "每日全量替换",
		},
	},
	"industry_constituent": {
		Domain:      "taxonomy",
		Description: "行业成分股",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			RefreshSchedule: "每日增量",
		},
	},
	"industry_weight": {
		Domain:      "taxonomy",
		Description: "行业成分权重（日度）",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			RefreshSchedule: "每日增量",
		},
	},
	"industry_daily": {
		Domain:      "taxonomy",
		Description: "行业日行情",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			RefreshSchedule: "每日增量",
		},
	},
	// Financial
	"financial_statement": {
		Domain:      "financial",
		Description: "财务报表（三表+快报+预告）",
		TimeColumn:  "reporting_period",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/financial/{source}/{statement_type}/upsert",
		},
	},
	"corporate_action": {
		Domain:      "financial",
		Description: "公司行为（分红/配股）",
		TimeColumn:  "ann_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/corporate-action/{source}/{action_type}/upsert",
		},
	},
	// Strategy
	"strategy_run_summary": {
		Domain:      "strategy",
		Description: "策略回测汇总",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API upsert",
		},
	},
	"strategy_run_artifact": {
		Domain:      "strategy",
		Description: "策略回测制品",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API upsert",
		},
	},
	// KG
	"documents": {
		Domain:      "kg",
		Description: "知识图谱文档元数据",
		Lineage: &model.DataLineage{
			SourceSystem:    "atlas",
			IngestionMethod: "REST API",
			RefreshSchedule: "每日增量",
		},
	},
	"extractions": {
		Domain:      "kg",
		Description: "LLM 抽取结果（JSONB）",
		Lineage: &model.DataLineage{
			SourceSystem: "atlas",
		},
	},
	"events": {
		Domain:      "kg",
		Description: "规范化事件（去重后）",
		TimeColumn:  "first_seen_at",
		Lineage: &model.DataLineage{
			SourceSystem: "atlas",
		},
	},
	"impact_logs": {
		Domain:      "kg",
		Description: "事件影响日志",
		Lineage: &model.DataLineage{
			SourceSystem: "atlas",
		},
	},
	"daily_runs": {
		Domain:      "kg",
		Description: "每日 KG 流水线运行记录",
		TimeColumn:  "run_date",
		Lineage: &model.DataLineage{
			SourceSystem: "atlas",
		},
	},
	"graph_ingestions": {
		Domain:      "kg",
		Description: "图谱写入记录",
		Lineage: &model.DataLineage{
			SourceSystem: "atlas",
		},
	},
	// Factor
	"factor_": {
		Domain:      "factor",
		Description: "因子数据",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
		},
	},
	"factor_metadata": {
		Domain:      "factor",
		Description: "因子元数据（描述/参数/状态）",
		Lineage: &model.DataLineage{
			SourceSystem: "artemis",
		},
	},
	// Regime
	"regime_": {
		Domain:      "regime",
		Description: "市场状态引擎数据",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API",
			RefreshSchedule: "每日计算",
		},
	},
}

// column description registry (table.column → description)
var columnDescRegistry = map[string]string{
	"*.id":               "自增主键",
	"*.symbol":           "证券代码",
	"*.market":           "市场（如 zh_a, hk, us）",
	"*.source":           "数据来源",
	"*.created_at":       "创建时间",
	"*.updated_at":       "更新时间",
	"*.trade_date":       "交易日期",
	"*.open":             "开盘价",
	"*.high":             "最高价",
	"*.low":              "最低价",
	"*.close":            "收盘价",
	"*.volume":           "成交量",
	"*.amount":           "成交额",
	"*.preclose":         "昨收价",
	"*.pct_chg":          "涨跌幅(%)",
	"*.data_json":        "业务数据（JSONB 灵活字段）",
	"*.statement_type":   "报表类型（balance_sheet/income/cashflow/profit_express/profit_notice）",
	"*.reporting_period": "报告期（YYYYMMDD）",
	"*.action_type":      "公司行为类型（dividend/right_issue）",
	"*.ann_date":         "公告日期",
	"*.security_name":    "证券名称",
}

// ─── Domain label map ───

var domainDescriptions = map[string]string{
	"bars":      "行情数据（K线）",
	"security":  "证券基础信息",
	"taxonomy":  "分类/行业数据",
	"financial": "财务/公司行为数据",
	"strategy":  "策略回测数据",
	"kg":        "知识图谱数据",
	"factor":    "因子数据",
	"regime":    "市场状态引擎数据",
	"other":     "其他",
}

// tablespace tier mapping
var tablespaceTiers = map[string]struct {
	Tier     string
	Hardware string
}{
	"pg_default":   {Tier: "hot", Hardware: "2TB M.2 NVMe"},
	"warm_storage": {Tier: "warm", Hardware: "8TB SATA SSD"},
}

// ─── CatalogService ───

type CatalogService struct {
	*core.BaseComponent
	Dao       *dao.CatalogDao `infra:"dep:dao_catalog"`
	SchemaDao *dao.SchemaDao  `infra:"dep:dao_schema"`
	GraphDao  *dao.GraphDao   `infra:"dep_optional:dao_graph"`

	cacheMu      sync.RWMutex
	cachedTables []model.TableCatalogEntry
	cacheTime    time.Time
	cacheTTL     time.Duration
}

func NewCatalogService() *CatalogService {
	return &CatalogService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_CATALOG),
		cacheTTL:      5 * time.Minute,
	}
}

func (s *CatalogService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *CatalogService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

// GetOverview returns the full catalog overview.
func (s *CatalogService) GetOverview(ctx context.Context, refresh bool) (*model.CatalogOverview, error) {
	tables, cached, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}

	// Aggregate summary
	var totalRows, totalDisk, totalIdx int64
	for _, t := range tables {
		totalRows += t.RowCount
		totalDisk += t.DiskSizeBytes
		totalIdx += t.IndexSizeBytes
	}

	// Per-tier summary
	tierMap := map[string]*model.TierSummary{}
	for _, t := range tables {
		key := t.StorageTier
		if _, ok := tierMap[key]; !ok {
			tierMap[key] = &model.TierSummary{Tablespace: t.Tablespace}
		}
		tierMap[key].TableCount++
		tierMap[key].DiskSizeBytes += t.DiskSizeBytes
	}
	tiers := map[string]model.TierSummary{}
	for k, v := range tierMap {
		v.DiskSize = dao.HumanSize(v.DiskSizeBytes)
		tiers[k] = *v
	}

	// Per-domain summary
	domainMap := map[string]*model.DomainCatalogSummary{}
	for _, t := range tables {
		d := t.Domain
		if _, ok := domainMap[d]; !ok {
			domainMap[d] = &model.DomainCatalogSummary{
				Domain:      d,
				Description: domainDescriptions[d],
			}
		}
		domainMap[d].TableCount++
		domainMap[d].TotalRows += t.RowCount
		domainMap[d].TotalDiskSizeBytes += t.DiskSizeBytes
	}
	domains := make([]model.DomainCatalogSummary, 0, len(domainMap))
	for _, v := range domainMap {
		v.TotalDiskSize = dao.HumanSize(v.TotalDiskSizeBytes)
		domains = append(domains, *v)
	}
	sort.Slice(domains, func(i, j int) bool {
		return domains[i].TotalDiskSizeBytes > domains[j].TotalDiskSizeBytes
	})

	return &model.CatalogOverview{
		GeneratedAt:     time.Now(),
		Cached:          cached,
		CacheTTLSeconds: int(s.cacheTTL.Seconds()),
		Summary: model.CatalogSummary{
			TotalTables:         len(tables),
			TotalRows:           totalRows,
			TotalDiskSize:       dao.HumanSize(totalDisk),
			TotalDiskSizeBytes:  totalDisk,
			TotalIndexSize:      dao.HumanSize(totalIdx),
			TotalIndexSizeBytes: totalIdx,
		},
		StorageTiers: tiers,
		Domains:      domains,
	}, nil
}

// ListTables returns all table catalog entries, optionally filtered by domain.
func (s *CatalogService) ListTables(ctx context.Context, domain string, refresh bool) ([]model.TableCatalogEntry, error) {
	tables, _, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}
	if domain == "" {
		return tables, nil
	}
	var filtered []model.TableCatalogEntry
	for _, t := range tables {
		if t.Domain == domain {
			filtered = append(filtered, t)
		}
	}
	return filtered, nil
}

// GetTableDetail returns detailed metadata for a specific table.
func (s *CatalogService) GetTableDetail(ctx context.Context, schema, table string, refresh bool) (*model.TableDetail, error) {
	tables, _, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}

	// Find the table entry
	var entry *model.TableCatalogEntry
	for _, t := range tables {
		if t.Schema == schema && t.TableName == table {
			e := t
			entry = &e
			break
		}
	}
	if entry == nil {
		return nil, fmt.Errorf("table %s.%s not found", schema, table)
	}

	// Get columns
	cols, err := s.Dao.GetTableColumns(ctx, schema, table)
	if err != nil {
		logging.Errorf(ctx, "catalog: get columns for %s.%s failed: %v", schema, table, err)
		cols = nil
	}

	// Enrich column descriptions
	for i := range cols {
		cols[i].Description = s.getColumnDescription(table, cols[i].Name)
	}

	// Get JSONB keys for JSONB columns
	if entry.HasJSONB {
		for i, col := range cols {
			if strings.Contains(col.Type, "jsonb") {
				jsonbKeys := s.discoverJSONBKeys(ctx, schema, table, col.Name)
				if jsonbKeys != nil {
					cols[i].JSONBKeys = jsonbKeys
				}
			}
		}
	}

	// Get indexes
	indexes, err := s.Dao.GetTableIndexes(ctx, schema, table)
	if err != nil {
		logging.Errorf(ctx, "catalog: get indexes for %s.%s failed: %v", schema, table, err)
		indexes = nil
	}

	// Get time range
	meta := s.findMeta(schema, table)
	if meta.TimeColumn != "" && entry.TimeRange == nil {
		tr, trErr := s.Dao.GetTimeRange(ctx, schema, table, meta.TimeColumn)
		if trErr == nil && tr != nil {
			entry.TimeRange = tr
		}
	}

	detail := &model.TableDetail{
		TableCatalogEntry: *entry,
		Columns:           cols,
		Indexes:           indexes,
		DataLineage:       meta.Lineage,
	}

	return detail, nil
}

// GetStorageInfo returns tablespace-level storage info.
func (s *CatalogService) GetStorageInfo(ctx context.Context) (*model.StorageInfo, error) {
	tsList, err := s.Dao.GetTablespaces(ctx)
	if err != nil {
		return nil, err
	}

	// Get tables to group by tablespace
	tables, _, tblErr := s.getTables(ctx, false)
	if tblErr != nil {
		return nil, tblErr
	}

	tsTableMap := map[string][]string{}
	for _, t := range tables {
		ts := t.Tablespace
		if ts == "" {
			ts = "pg_default"
		}
		tsTableMap[ts] = append(tsTableMap[ts], t.Schema+"."+t.TableName)
	}

	for i := range tsList {
		ts := &tsList[i]
		name := ts.Name
		if info, ok := tablespaceTiers[name]; ok {
			ts.Tier = info.Tier
			ts.Hardware = info.Hardware
		} else {
			ts.Tier = "unknown"
		}
		ts.Tables = tsTableMap[name]
		ts.TableCount = len(ts.Tables)
	}

	return &model.StorageInfo{Tablespaces: tsList}, nil
}

// ─── internal helpers ───

func (s *CatalogService) getTables(ctx context.Context, refresh bool) ([]model.TableCatalogEntry, bool, error) {
	s.cacheMu.RLock()
	if !refresh && s.cachedTables != nil && time.Since(s.cacheTime) < s.cacheTTL {
		tables := s.cachedTables
		s.cacheMu.RUnlock()
		return tables, true, nil
	}
	s.cacheMu.RUnlock()

	// Rebuild cache
	rows, err := s.Dao.ListTables(ctx, []string{"public", "kg"})
	if err != nil {
		return nil, false, err
	}

	tables := make([]model.TableCatalogEntry, 0, len(rows))
	for _, r := range rows {
		meta := s.findMeta(r.SchemaName, r.TableName)
		tier := "hot"
		ts := r.Tablespace
		if ts == "" {
			ts = "pg_default"
		}
		if info, ok := tablespaceTiers[ts]; ok {
			tier = info.Tier
		}

		entry := model.TableCatalogEntry{
			Schema:         r.SchemaName,
			TableName:      r.TableName,
			Domain:         meta.Domain,
			Description:    meta.Description,
			RowCount:       r.RowEstimate,
			DiskSize:       dao.HumanSize(r.TotalBytes),
			DiskSizeBytes:  r.TotalBytes,
			IndexSize:      dao.HumanSize(r.IndexBytes),
			IndexSizeBytes: r.IndexBytes,
			Tablespace:     ts,
			StorageTier:    tier,
			IsHypertable:   r.IsHypertable,
			ColumnCount:    r.ColumnCount,
			HasJSONB:       r.HasJSONB,
		}

		// Try to get time range if we know the time column
		if meta.TimeColumn != "" {
			tr, trErr := s.Dao.GetTimeRange(ctx, r.SchemaName, r.TableName, meta.TimeColumn)
			if trErr == nil && tr != nil {
				entry.TimeRange = tr
			}
		}

		tables = append(tables, entry)
	}

	s.cacheMu.Lock()
	s.cachedTables = tables
	s.cacheTime = time.Now()
	s.cacheMu.Unlock()

	return tables, false, nil
}

// findMeta finds the static metadata for a table using prefix matching.
func (s *CatalogService) findMeta(schema, table string) tableMeta {
	// Exact match first
	key := table
	if schema == "kg" {
		key = table // kg tables are stored by their table name only
	}
	if m, ok := tableMetaRegistry[key]; ok {
		return m
	}

	// Prefix match (for bars_*, bars_ext_*)
	// Try longest prefix first
	bestKey := ""
	for k := range tableMetaRegistry {
		if strings.HasSuffix(k, "_") && strings.HasPrefix(table, k) {
			if len(k) > len(bestKey) {
				bestKey = k
			}
		}
	}
	if bestKey != "" {
		m := tableMetaRegistry[bestKey]
		// Generate more specific description for bars tables
		if m.Domain == "bars" && strings.HasPrefix(table, "bars_ext_") {
			m.Description = "扩展指标: " + table
		} else if m.Domain == "bars" {
			m.Description = "K线: " + table
		}
		return m
	}

	// Default for kg schema
	if schema == "kg" {
		return tableMeta{Domain: "kg", Description: table}
	}

	return tableMeta{Domain: "other", Description: table}
}

// getColumnDescription finds a description for a column from the registry.
func (s *CatalogService) getColumnDescription(table, column string) string {
	// Try table-specific key
	if desc, ok := columnDescRegistry[table+"."+column]; ok {
		return desc
	}
	// Try wildcard
	if desc, ok := columnDescRegistry["*."+column]; ok {
		return desc
	}
	return ""
}

// discoverJSONBKeys uses SchemaDao to discover keys in a JSONB column.
// This is a best-effort operation; may return nil if the table/column combo isn't supported.
// schema and column are reserved for future generic JSONB discovery.
func (s *CatalogService) discoverJSONBKeys(ctx context.Context, _ /*schema*/, table, _ /*column*/ string) any {
	if s.SchemaDao == nil {
		return nil
	}

	// Only supported for financial_statement and corporate_action currently
	spec, ok := map[string]struct {
		Domain     string
		TypeColumn string
	}{
		"financial_statement": {"financial_statement", "statement_type"},
		"corporate_action":    {"corporate_action", "action_type"},
	}[table]
	if !ok {
		return nil
	}

	// List types then get keys per type
	types, err := s.SchemaDao.ListTypes(ctx, spec.Domain)
	if err != nil {
		return nil
	}

	result := map[string][]string{}
	for _, t := range types {
		fr, err := s.SchemaDao.DiscoverFields(ctx, spec.Domain, t, 100)
		if err != nil || fr == nil {
			continue
		}
		result[t] = fr.Fields
	}
	if len(result) == 0 {
		return nil
	}
	return result
}

// ─── Neo4j graph catalog ───

// graphLabelDescriptions maps Neo4j node labels to descriptions.
var graphLabelDescriptions = map[string]string{
	"Company":    "公司/企业实体",
	"Product":    "产品/服务",
	"Resource":   "资源（大宗商品/能源/矿产/算力）",
	"Industry":   "行业分类",
	"Technology": "技术/专利",
	"Event":      "事件（新闻/政策/财报）",
	"Policy":     "政策/监管",
	"Asset":      "资产/证券",
	"Market":     "市场",
}

// graphRelTypeDescriptions maps Neo4j relationship types to descriptions.
var graphRelTypeDescriptions = map[string]string{
	"SUPPLIES":      "供应关系",
	"USES":          "使用/依赖",
	"PRODUCES":      "生产",
	"BELONGS_TO":    "属于（行业）",
	"COMPETITOR_OF": "竞争关系",
	"IMPACT_ON":     "事件影响",
	"DEPENDS_ON":    "依赖",
	"HAS_PRODUCT":   "拥有产品",
	"OPERATES_IN":   "经营于（市场）",
	"INVESTS_IN":    "投资",
	"CHILD_OF":      "子公司/控股关系",
}

// GetGraphCatalog returns Neo4j graph database catalog info.
func (s *CatalogService) GetGraphCatalog(ctx context.Context) (*model.GraphCatalogOverview, error) {
	if s.GraphDao == nil {
		return &model.GraphCatalogOverview{Available: false}, nil
	}

	stats, err := s.GraphDao.GetGraphStats(ctx)
	if err != nil {
		logging.Errorf(ctx, "catalog: get graph stats failed: %v", err)
		return &model.GraphCatalogOverview{Available: false}, nil
	}

	overview := &model.GraphCatalogOverview{
		Available: true,
	}

	// Parse node counts
	if nc, ok := stats["node_counts"].(map[string]any); ok {
		overview.NodeCounts = make(map[string]int, len(nc))
		for label, cnt := range nc {
			if v, ok := cnt.(int); ok {
				overview.NodeCounts[label] = v
			}
		}
	}
	if v, ok := stats["total_nodes"].(int); ok {
		overview.TotalNodes = v
	}
	if v, ok := stats["total_edges"].(int); ok {
		overview.TotalEdges = v
	}

	// Build label info with descriptions
	if overview.NodeCounts != nil {
		labels := make([]model.GraphLabelInfo, 0, len(overview.NodeCounts))
		for label, count := range overview.NodeCounts {
			labels = append(labels, model.GraphLabelInfo{
				Label:       label,
				Count:       count,
				Description: graphLabelDescriptions[label],
			})
		}
		sort.Slice(labels, func(i, j int) bool { return labels[i].Count > labels[j].Count })
		overview.Labels = labels
	}

	// Query relationship types with counts
	relTypes, relErr := s.GraphDao.GetRelTypeCounts(ctx)
	if relErr == nil && relTypes != nil {
		rts := make([]model.GraphRelTypeInfo, 0, len(relTypes))
		for relType, count := range relTypes {
			rts = append(rts, model.GraphRelTypeInfo{
				Type:        relType,
				Count:       count,
				Description: graphRelTypeDescriptions[relType],
			})
		}
		sort.Slice(rts, func(i, j int) bool { return rts[i].Count > rts[j].Count })
		overview.RelTypes = rts
	}

	return overview, nil
}
