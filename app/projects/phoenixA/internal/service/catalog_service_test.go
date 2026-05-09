package service

import (
	"context"
	"testing"
)

func TestFindMeta_ExactMatch(t *testing.T) {
	svc := &CatalogService{}

	cases := []struct {
		schema string
		table  string
		domain string
		desc   string
	}{
		{"public", "security_registry", "security", "证券注册表（股票/ETF/指数基础信息）"},
		{"public", "financial_statement", "financial", "财务报表（三表+快报+预告）"},
		{"public", "corporate_action", "financial", "公司行为（分红/配股）"},
		{"public", "taxonomy_category", "taxonomy", "分类节点（行业/概念/地域）"},
		{"public", "taxonomy_security_map", "taxonomy", "证券-分类映射关系"},
		{"public", "industry_weight", "taxonomy", "行业成分权重（日度）"},
		{"public", "industry_daily", "taxonomy", "行业日行情"},
		{"public", "strategy_run_summary", "strategy", "策略回测汇总"},
		{"public", "strategy_run_artifact", "strategy", "策略回测制品"},
		{"public", "factor_metadata", "factor", "因子元数据（描述/参数/状态）"},
		{"kg", "documents", "kg", "知识图谱文档元数据"},
		{"kg", "extractions", "kg", "LLM 抽取结果（JSONB）"},
		{"kg", "events", "kg", "规范化事件（去重后）"},
		{"kg", "impact_logs", "kg", "事件影响日志"},
		{"kg", "daily_runs", "kg", "每日 KG 流水线运行记录"},
		{"kg", "graph_ingestions", "kg", "图谱写入记录"},
	}

	for _, c := range cases {
		meta := svc.findMeta(c.schema, c.table)
		if meta.Domain != c.domain {
			t.Errorf("findMeta(%s, %s): domain got %q, want %q", c.schema, c.table, meta.Domain, c.domain)
		}
		if meta.Description != c.desc {
			t.Errorf("findMeta(%s, %s): description got %q, want %q", c.schema, c.table, meta.Description, c.desc)
		}
	}
}

func TestFindMeta_PrefixMatch(t *testing.T) {
	svc := &CatalogService{}

	cases := []struct {
		table  string
		domain string
	}{
		{"bars_stock_zh_a_daily_nf", "bars"},
		{"bars_stock_zh_a_1min_nf", "bars"},
		{"bars_stock_us_daily_adj", "bars"},
		{"bars_ext_baostock_stock_zh_a_daily", "bars"},
		{"factor_daily", "factor"},
		{"regime_state", "regime"},
		{"regime_indicator", "regime"},
	}

	for _, c := range cases {
		meta := svc.findMeta("public", c.table)
		if meta.Domain != c.domain {
			t.Errorf("findMeta(public, %s): domain got %q, want %q", c.table, meta.Domain, c.domain)
		}
	}
}

func TestFindMeta_PrefixPriority(t *testing.T) {
	svc := &CatalogService{}

	// bars_ext_ should match the bars_ext_ prefix (longer), not bars_ (shorter)
	meta := svc.findMeta("public", "bars_ext_baostock_stock_zh_a_daily")
	if meta.Domain != "bars" {
		t.Errorf("expected domain 'bars', got %q", meta.Domain)
	}
	// Description should be the ext-specific one
	if meta.Description != "扩展指标: bars_ext_baostock_stock_zh_a_daily" {
		t.Errorf("unexpected description: %q", meta.Description)
	}
}

func TestFindMeta_UnknownTable(t *testing.T) {
	svc := &CatalogService{}

	meta := svc.findMeta("public", "some_unknown_table")
	if meta.Domain != "other" {
		t.Errorf("unknown table domain: got %q, want 'other'", meta.Domain)
	}
}

func TestFindMeta_KGSchemaFallback(t *testing.T) {
	svc := &CatalogService{}

	meta := svc.findMeta("kg", "some_future_kg_table")
	if meta.Domain != "kg" {
		t.Errorf("unknown kg table domain: got %q, want 'kg'", meta.Domain)
	}
}

func TestGetColumnDescription_Wildcard(t *testing.T) {
	svc := &CatalogService{}

	cases := []struct {
		table, column, expected string
	}{
		{"bars_stock_zh_a_daily_nf", "symbol", "证券代码"},
		{"financial_statement", "trade_date", "交易日期"},
		{"any_table", "open", "开盘价"},
		{"any_table", "data_json", "业务数据（JSONB 灵活字段）"},
		{"any_table", "unknown_col", ""},
	}

	for _, c := range cases {
		got := svc.getColumnDescription(c.table, c.column)
		if got != c.expected {
			t.Errorf("getColumnDescription(%s, %s): got %q, want %q", c.table, c.column, got, c.expected)
		}
	}
}

func TestFindMeta_HasLineage(t *testing.T) {
	svc := &CatalogService{}

	// All registered tables should have lineage info
	tablesWithLineage := []struct {
		schema string
		table  string
		source string
	}{
		{"public", "security_registry", "artemis"},
		{"public", "financial_statement", "artemis"},
		{"public", "bars_stock_zh_a_daily_nf", "artemis"},
		{"kg", "documents", "atlas"},
		{"kg", "events", "atlas"},
	}

	for _, c := range tablesWithLineage {
		meta := svc.findMeta(c.schema, c.table)
		if meta.Lineage == nil {
			t.Errorf("findMeta(%s, %s): lineage is nil", c.schema, c.table)
			continue
		}
		if meta.Lineage.SourceSystem != c.source {
			t.Errorf("findMeta(%s, %s): source got %q, want %q", c.schema, c.table, meta.Lineage.SourceSystem, c.source)
		}
	}
}

func TestFindMeta_HasTimeColumn(t *testing.T) {
	svc := &CatalogService{}

	cases := []struct {
		schema     string
		table      string
		timeColumn string
	}{
		{"public", "bars_stock_zh_a_daily_nf", "trade_date"},
		{"public", "financial_statement", "reporting_period"},
		{"public", "corporate_action", "ann_date"},
		{"public", "industry_weight", "trade_date"},
		{"kg", "events", "first_seen_at"},
		{"kg", "daily_runs", "run_date"},
		// No time column
		{"public", "security_registry", ""},
		{"public", "taxonomy_category", ""},
	}

	for _, c := range cases {
		meta := svc.findMeta(c.schema, c.table)
		if meta.TimeColumn != c.timeColumn {
			t.Errorf("findMeta(%s, %s): timeColumn got %q, want %q", c.schema, c.table, meta.TimeColumn, c.timeColumn)
		}
	}
}

func TestDomainDescriptions_Complete(t *testing.T) {
	// All domains used in tableMetaRegistry should have a description
	usedDomains := map[string]bool{}
	for _, meta := range tableMetaRegistry {
		usedDomains[meta.Domain] = true
	}

	for domain := range usedDomains {
		if _, ok := domainDescriptions[domain]; !ok {
			t.Errorf("domain %q used in registry but missing from domainDescriptions", domain)
		}
	}
}

func TestGetGraphCatalog_NoNeo4j(t *testing.T) {
	svc := &CatalogService{}

	info, err := svc.GetGraphCatalog(context.Background())
	if err != nil {
		t.Fatalf("GetGraphCatalog error: %v", err)
	}
	if info == nil {
		t.Fatal("GetGraphCatalog returned nil")
	}
	if info.Available {
		t.Error("expected Available=false when GraphDao is nil")
	}
	if info.TotalNodes != 0 || info.TotalEdges != 0 {
		t.Errorf("expected zero counts when unavailable, got nodes=%d edges=%d", info.TotalNodes, info.TotalEdges)
	}
}

func TestGraphLabelDescriptions_CompleteForKnownStatsLabels(t *testing.T) {
	labels := []string{"Company", "Product", "Resource", "Industry", "Technology", "Event", "Policy", "Asset", "Market"}
	for _, label := range labels {
		if _, ok := graphLabelDescriptions[label]; !ok {
			t.Errorf("missing graph label description for %q", label)
		}
	}
}

func TestGraphRelTypeDescriptions_NotEmptyForCoreRelations(t *testing.T) {
	rels := []string{"SUPPLIES", "COMPETITOR_OF", "IMPACT_ON", "HAS_PRODUCT", "BELONGS_TO"}
	for _, rel := range rels {
		desc, ok := graphRelTypeDescriptions[rel]
		if !ok || desc == "" {
			t.Errorf("missing graph relationship description for %q", rel)
		}
	}
}
