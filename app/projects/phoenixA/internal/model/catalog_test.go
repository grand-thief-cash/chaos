package model

import (
	"encoding/json"
	"testing"
	"time"
)

func TestCatalogOverviewJSON(t *testing.T) {
	now := time.Now()
	ov := CatalogOverview{
		GeneratedAt:     now,
		Cached:          true,
		CacheTTLSeconds: 300,
		Summary: CatalogSummary{
			TotalTables:         25,
			TotalRows:           150000000,
			TotalDiskSize:       "186 GB",
			TotalDiskSizeBytes:  199715979264,
			TotalIndexSize:      "45 GB",
			TotalIndexSizeBytes: 48318382080,
		},
		StorageTiers: map[string]TierSummary{
			"hot":  {Tablespace: "pg_default", DiskSize: "136 GB", DiskSizeBytes: 146028888064, TableCount: 20},
			"warm": {Tablespace: "warm_storage", DiskSize: "50 GB", DiskSizeBytes: 53687091200, TableCount: 5},
		},
		Domains: []DomainCatalogSummary{
			{Domain: "bars", Description: "行情数据", TableCount: 10, TotalRows: 120000000, TotalDiskSize: "80 GB", TotalDiskSizeBytes: 85899345920},
		},
	}

	data, err := json.Marshal(ov)
	if err != nil {
		t.Fatalf("marshal CatalogOverview: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	requiredFields := []string{
		"generated_at", "cached", "cache_ttl_seconds",
		"summary", "storage_tiers", "domains",
	}
	for _, f := range requiredFields {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}

	// Verify summary sub-fields
	summary, ok := m["summary"].(map[string]any)
	if !ok {
		t.Fatal("summary is not an object")
	}
	summaryFields := []string{
		"total_tables", "total_rows", "total_disk_size",
		"total_disk_size_bytes", "total_index_size", "total_index_size_bytes",
	}
	for _, f := range summaryFields {
		if _, ok := summary[f]; !ok {
			t.Errorf("missing summary field: %s", f)
		}
	}
}

func TestTableCatalogEntryJSON(t *testing.T) {
	entry := TableCatalogEntry{
		Schema:         "public",
		TableName:      "bars_stock_zh_a_daily_nf",
		Domain:         "bars",
		Description:    "K线: bars_stock_zh_a_daily_nf",
		RowCount:       25000000,
		DiskSize:       "3.2 GB",
		DiskSizeBytes:  3435973837,
		IndexSize:      "1.1 GB",
		IndexSizeBytes: 1181116006,
		Tablespace:     "warm_storage",
		StorageTier:    "warm",
		IsHypertable:   true,
		TimeRange:      &TimeRange{Column: "trade_date", Min: "2000-01-04", Max: "2026-05-08"},
		ColumnCount:    12,
		HasJSONB:       false,
	}

	data, err := json.Marshal(entry)
	if err != nil {
		t.Fatalf("marshal TableCatalogEntry: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	requiredFields := []string{
		"schema", "table_name", "domain", "description",
		"row_count", "disk_size", "disk_size_bytes",
		"index_size", "index_size_bytes", "tablespace",
		"storage_tier", "is_hypertable", "time_range",
		"column_count", "has_jsonb",
	}
	for _, f := range requiredFields {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}

	// Verify time_range structure
	tr, ok := m["time_range"].(map[string]any)
	if !ok {
		t.Fatal("time_range is not an object")
	}
	for _, f := range []string{"column", "min", "max"} {
		if _, ok := tr[f]; !ok {
			t.Errorf("missing time_range field: %s", f)
		}
	}
}

func TestTableDetailJSON(t *testing.T) {
	detail := TableDetail{
		TableCatalogEntry: TableCatalogEntry{
			Schema:    "public",
			TableName: "financial_statement",
			Domain:    "financial",
		},
		Columns: []ColumnMeta{
			{Name: "id", Type: "bigint", Nullable: false, IsPrimaryKey: true, Description: "PK"},
			{Name: "data_json", Type: "jsonb", Nullable: false, JSONBKeys: map[string][]string{
				"balance_sheet": {"TOTAL_ASSETS", "TOTAL_LIAB"},
			}},
		},
		Indexes: []IndexMeta{
			{Name: "uk_fin_stmt", Columns: []string{"source", "symbol"}, IsUnique: true, Type: "btree"},
		},
		DataLineage: &DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/financial/{source}/{type}/upsert",
		},
	}

	data, err := json.Marshal(detail)
	if err != nil {
		t.Fatalf("marshal TableDetail: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	for _, f := range []string{"columns", "indexes", "data_lineage"} {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}

	// Verify column with jsonb_keys
	cols, ok := m["columns"].([]any)
	if !ok || len(cols) != 2 {
		t.Fatal("expected 2 columns")
	}
	col1, ok := cols[1].(map[string]any)
	if !ok {
		t.Fatal("column[1] is not an object")
	}
	if _, ok := col1["jsonb_keys"]; !ok {
		t.Error("column data_json should have jsonb_keys")
	}
}

func TestTableCatalogEntryNoTimeRange(t *testing.T) {
	entry := TableCatalogEntry{
		Schema:    "public",
		TableName: "security_registry",
	}

	data, err := json.Marshal(entry)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// time_range should be omitted (omitempty)
	if _, ok := m["time_range"]; ok {
		t.Error("time_range should be omitted when nil")
	}
}

func TestStorageInfoJSON(t *testing.T) {
	info := StorageInfo{
		Tablespaces: []TablespaceInfo{
			{
				Name:           "pg_default",
				Location:       "",
				Tier:           "hot",
				Hardware:       "2TB M.2 NVMe",
				TotalSize:      "136 GB",
				TotalSizeBytes: 146028888064,
				TableCount:     20,
				Tables:         []string{"public.security_registry"},
			},
		},
	}

	data, err := json.Marshal(info)
	if err != nil {
		t.Fatalf("marshal StorageInfo: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	tsList, ok := m["tablespaces"].([]any)
	if !ok || len(tsList) != 1 {
		t.Fatal("expected 1 tablespace")
	}

	ts := tsList[0].(map[string]any)
	for _, f := range []string{"name", "location", "tier", "hardware", "total_size", "total_size_bytes", "table_count", "tables"} {
		if _, ok := ts[f]; !ok {
			t.Errorf("missing tablespace field: %s", f)
		}
	}
}

func TestGraphCatalogOverviewJSON(t *testing.T) {
	gco := GraphCatalogOverview{
		Available:  true,
		NodeCounts: map[string]int{"Company": 100, "Product": 200},
		TotalNodes: 300,
		TotalEdges: 500,
		Labels: []GraphLabelInfo{
			{Label: "Product", Count: 200, Description: "产品/服务"},
			{Label: "Company", Count: 100, Description: "公司/企业实体"},
		},
		RelTypes: []GraphRelTypeInfo{
			{Type: "SUPPLIES", Count: 150, Description: "供应关系"},
		},
	}

	data, err := json.Marshal(gco)
	if err != nil {
		t.Fatalf("marshal GraphCatalogOverview: %v", err)
	}

	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	for _, f := range []string{"available", "node_counts", "total_nodes", "total_edges", "labels", "rel_types"} {
		if _, ok := m[f]; !ok {
			t.Errorf("missing JSON field: %s", f)
		}
	}

	if m["available"] != true {
		t.Error("available should be true")
	}
}

func TestGraphCatalogOverviewUnavailable(t *testing.T) {
	gco := GraphCatalogOverview{Available: false}

	data, err := json.Marshal(gco)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var m map[string]any
	json.Unmarshal(data, &m)

	// node_counts should be omitted when nil
	if _, ok := m["node_counts"]; ok {
		t.Error("node_counts should be omitted when nil")
	}
	// labels should be omitted when nil
	if _, ok := m["labels"]; ok {
		t.Error("labels should be omitted when nil")
	}
}
