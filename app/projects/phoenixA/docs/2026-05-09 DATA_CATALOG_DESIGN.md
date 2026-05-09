# PhoenixA 数据目录（Data Catalog）设计

> PhoenixA 作为数据中台，需要对外提供完整的数据资产目录能力：精确描述存储了什么数据、多少条、占多大空间、时间范围、字段含义、JSONB 字段内容、数据来源和质量状态。
>
> 数据目录不仅供人阅读（通过 Cthulhu Dashboard），也通过 API 对外提供，让上游（Artemis/Atlas）和下游（回测/因子引擎）能够程序化发现可用数据。
>
> 当前范围分为两部分：
> - **PostgreSQL Catalog**：表/列/索引/JSONB/时间范围/存储层级
> - **Neo4j Graph Catalog**：节点标签、关系类型、节点/边数量、图谱可用性
>
> **创建日期**：2026-05-09

---

## 一、设计目标

1. **自动发现**：基于 PostgreSQL 系统表自动发现所有表/列，无需手动维护
2. **数据描述**：静态注册每张表、每个字段的中文/英文描述和业务含义
3. **实时统计**：行数、磁盘占用、时间范围、最近更新时间
4. **JSONB 内省**：自动扫描 JSONB 列中的 key 列表（复用已有 SchemaDao）
5. **存储层级**：展示数据在 NVMe/SATA 的分布
6. **数据系列枚举**：bars 表的 asset_type × market × period × adjust 组合
7. **Neo4j 图谱感知**：展示 Neo4j 知识图谱的节点标签、关系类型、数量统计
8. **图谱可用性观测**：当 Neo4j 关闭或不可达时，API 要优雅返回 `available=false`
9. **API 友好**：RESTful JSON 接口，支持缓存和刷新
10. **可扩展**：后续可以增加数据质量指标、数据血缘等

---

## 二、API 设计

### 2.1 接口总览

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v2/catalog/overview` | 总览：总表数、总行数、总磁盘、按域分组统计 |
| GET | `/api/v2/catalog/tables` | 所有表列表（含行数、大小、时间范围） |
| GET | `/api/v2/catalog/tables/{schema}/{table}` | 单表详情（列信息、JSONB key、数据范围） |
| GET | `/api/v2/catalog/storage` | 存储层级汇总（NVMe vs SATA 用量） |
| GET | `/api/v2/catalog/graph` | Neo4j 知识图谱目录（节点标签/关系类型/数量） |

### 2.2 接口详细定义

#### GET /api/v2/catalog/overview

```json
{
  "generated_at": "2026-05-09T10:30:00Z",
  "cached": true,
  "cache_ttl_seconds": 300,
  "summary": {
    "total_tables": 25,
    "total_rows": 150000000,
    "total_disk_size": "186 GB",
    "total_disk_size_bytes": 199715979264,
    "total_index_size": "45 GB",
    "total_index_size_bytes": 48318382080
  },
  "storage_tiers": {
    "hot": {
      "tablespace": "pg_default",
      "disk_size": "136 GB",
      "table_count": 20
    },
    "warm": {
      "tablespace": "warm_storage",
      "disk_size": "50 GB",
      "table_count": 5
    }
  },
  "domains": [
    {
      "domain": "bars",
      "description": "行情数据（K线）",
      "table_count": 10,
      "total_rows": 120000000,
      "total_disk_size": "80 GB"
    },
    {
      "domain": "taxonomy",
      "description": "分类/行业数据",
      "table_count": 5,
      "total_rows": 5000000,
      "total_disk_size": "51 GB"
    }
  ]
}
```

#### GET /api/v2/catalog/tables

支持查询参数：`?domain=bars&schema=public`

```json
{
  "tables": [
    {
      "schema": "public",
      "table_name": "bars_stock_zh_a_daily_nf",
      "domain": "bars",
      "description": "A股日线行情（不复权）",
      "row_count": 25000000,
      "disk_size": "3.2 GB",
      "disk_size_bytes": 3435973837,
      "index_size": "1.1 GB",
      "index_size_bytes": 1181116006,
      "tablespace": "pg_default",
      "storage_tier": "hot",
      "is_hypertable": true,
      "time_range": {
        "column": "trade_date",
        "min": "2000-01-04",
        "max": "2026-05-08"
      },
      "last_modified": "2026-05-08T22:30:00Z",
      "column_count": 12,
      "has_jsonb": false
    }
  ]
}
```

#### GET /api/v2/catalog/tables/{schema}/{table}

```json
{
  "schema": "public",
  "table_name": "financial_statement",
  "domain": "financial",
  "description": "财务报表（三表 + 快报 + 预告）",
  "row_count": 3700000,
  "disk_size": "7.5 GB",
  "disk_size_bytes": 8053063680,
  "index_size": "2.1 GB",
  "tablespace": "pg_default",
  "storage_tier": "hot",
  "is_hypertable": false,
  "time_range": {
    "column": "reporting_period",
    "min": "20050101",
    "max": "20260331"
  },
  "columns": [
    {
      "name": "id",
      "type": "bigint",
      "nullable": false,
      "description": "自增主键",
      "is_primary_key": true
    },
    {
      "name": "symbol",
      "type": "character varying(32)",
      "nullable": false,
      "description": "证券代码"
    },
    {
      "name": "data_json",
      "type": "jsonb",
      "nullable": false,
      "description": "财务报表数据（使用 JSONB 存储灵活字段）",
      "jsonb_keys": {
        "balance_sheet": ["TOTAL_ASSETS", "TOTAL_LIAB", "TOTAL_EQUITY", "..."],
        "income": ["REVENUE", "OPERATE_PROFIT", "NET_PROFIT", "..."],
        "cashflow": ["NET_OPER_CASHFLOW", "NET_INVEST_CASHFLOW", "..."]
      }
    }
  ],
  "indexes": [
    {
      "name": "uk_fin_stmt",
      "columns": ["source", "symbol", "market", "statement_type", "reporting_period", "report_type", "statement_code"],
      "is_unique": true
    },
    {
      "name": "idx_fs_data_gin",
      "columns": ["data_json"],
      "type": "GIN"
    }
  ],
  "data_lineage": {
    "source_system": "artemis",
    "ingestion_method": "REST API batch upsert",
    "refresh_schedule": "每日增量",
    "api_endpoint": "POST /api/v2/financial/{source}/{statement_type}/upsert"
  }
}
```

#### GET /api/v2/catalog/storage

```json
{
  "tablespaces": [
    {
      "name": "pg_default",
      "location": "/nvme/pgdata",
      "tier": "hot",
      "hardware": "2TB M.2 NVMe",
      "total_size": "136 GB",
      "table_count": 20,
      "tables": ["bars_stock_zh_a_daily_nf", "financial_statement", "..."]
    },
    {
      "name": "warm_storage",
      "location": "/sata8t/pgdata_warm",
      "tier": "warm",
      "hardware": "8TB SATA SSD",
      "total_size": "50 GB",
      "table_count": 5,
      "tables": ["bars_stock_zh_a_1min_nf", "strategy_run_artifact_archive", "..."]
    }
  ]
}
```

#### GET /api/v2/catalog/graph

```json
{
  "available": true,
  "node_counts": {
    "Company": 5200,
    "Product": 12000,
    "Event": 3500,
    "Industry": 500
  },
  "total_nodes": 24900,
  "total_edges": 125000,
  "labels": [
    { "label": "Product", "count": 12000, "description": "产品/服务" },
    { "label": "Company", "count": 5200, "description": "公司/企业实体" }
  ],
  "rel_types": [
    { "type": "HAS_PRODUCT", "count": 15000, "description": "拥有产品" },
    { "type": "SUPPLIES", "count": 8000, "description": "供应关系" },
    { "type": "IMPACT_ON", "count": 5000, "description": "事件影响" }
  ]
}
```

> 当 Neo4j 未启用或不可达时返回 `{ "available": false, "total_nodes": 0, "total_edges": 0 }`

---

## 三、数据模型

### 3.1 核心结构体

```go
// TableCatalogEntry — 表级目录信息
type TableCatalogEntry struct {
    Schema        string         `json:"schema"`
    TableName     string         `json:"table_name"`
    Domain        string         `json:"domain"`
    Description   string         `json:"description"`
    RowCount      int64          `json:"row_count"`
    DiskSize      string         `json:"disk_size"`
    DiskSizeBytes int64          `json:"disk_size_bytes"`
    IndexSize     string         `json:"index_size"`
    IndexSizeBytes int64         `json:"index_size_bytes"`
    Tablespace    string         `json:"tablespace"`
    StorageTier   string         `json:"storage_tier"`
    IsHypertable  bool           `json:"is_hypertable"`
    TimeRange     *TimeRange     `json:"time_range,omitempty"`
    LastModified  *time.Time     `json:"last_modified,omitempty"`
    ColumnCount   int            `json:"column_count"`
    HasJSONB      bool           `json:"has_jsonb"`
}

// TimeRange — 数据时间范围
type TimeRange struct {
    Column string `json:"column"`
    Min    string `json:"min"`
    Max    string `json:"max"`
}

// ColumnMeta — 列元数据
type ColumnMeta struct {
    Name         string   `json:"name"`
    Type         string   `json:"type"`
    Nullable     bool     `json:"nullable"`
    Description  string   `json:"description"`
    IsPrimaryKey bool     `json:"is_primary_key,omitempty"`
    JSONBKeys    any      `json:"jsonb_keys,omitempty"`
}

// IndexMeta — 索引信息
type IndexMeta struct {
    Name     string   `json:"name"`
    Columns  []string `json:"columns"`
    IsUnique bool     `json:"is_unique"`
    Type     string   `json:"type,omitempty"`
}

// DataLineage — 数据血缘
type DataLineage struct {
    SourceSystem    string `json:"source_system"`
    IngestionMethod string `json:"ingestion_method"`
    RefreshSchedule string `json:"refresh_schedule"`
    APIEndpoint     string `json:"api_endpoint,omitempty"`
}

// StorageTierSummary — 存储层汇总
type StorageTierSummary struct {
    Name       string   `json:"name"`
    Location   string   `json:"location"`
    Tier       string   `json:"tier"`
    Hardware   string   `json:"hardware"`
    TotalSize  string   `json:"total_size"`
    TableCount int      `json:"table_count"`
    Tables     []string `json:"tables"`
}

// GraphCatalogOverview — Neo4j 图谱目录信息
type GraphCatalogOverview struct {
    Available  bool               `json:"available"`
    NodeCounts map[string]int     `json:"node_counts,omitempty"`
    TotalNodes int                `json:"total_nodes"`
    TotalEdges int                `json:"total_edges"`
    Labels     []GraphLabelInfo   `json:"labels,omitempty"`
    RelTypes   []GraphRelTypeInfo `json:"rel_types,omitempty"`
}
```

### 3.2 静态元数据注册表

为每张表和每个字段提供描述，以 Go map 硬编码（初期不需要数据库存储）：

```go
// 表域分类映射
var tableDomainMap = map[string]TableMeta{
    "bars_*":                {Domain: "bars", Description: "行情数据（K线）", TimeColumn: "trade_date"},
    "bars_ext_*":            {Domain: "bars", Description: "行情扩展指标", TimeColumn: "trade_date"},
    "security_registry":     {Domain: "security", Description: "证券注册表（股票/ETF/指数基础信息）"},
    "taxonomy_category":     {Domain: "taxonomy", Description: "分类节点（行业/概念/地域）"},
    "taxonomy_security_map": {Domain: "taxonomy", Description: "证券-分类映射关系"},
    "industry_constituent":  {Domain: "taxonomy", Description: "行业成分股"},
    "industry_weight":       {Domain: "taxonomy", Description: "行业成分权重（日度）", TimeColumn: "trade_date"},
    "industry_daily":        {Domain: "taxonomy", Description: "行业日行情", TimeColumn: "trade_date"},
    "financial_statement":   {Domain: "financial", Description: "财务报表（三表+快报+预告）", TimeColumn: "reporting_period"},
    "corporate_action":      {Domain: "financial", Description: "公司行为（分红/配股）", TimeColumn: "ann_date"},
    "strategy_run_summary":  {Domain: "strategy", Description: "策略回测汇总"},
    "strategy_run_artifact": {Domain: "strategy", Description: "策略回测制品"},
    "kg.documents":          {Domain: "kg", Description: "知识图谱文档元数据"},
    "kg.extractions":        {Domain: "kg", Description: "LLM 抽取结果（JSONB）"},
    "kg.events":             {Domain: "kg", Description: "规范化事件（去重后）"},
    "kg.impact_logs":        {Domain: "kg", Description: "事件影响日志"},
    "kg.daily_runs":         {Domain: "kg", Description: "每日 KG 流水线运行记录"},
    "kg.graph_ingestions":   {Domain: "kg", Description: "图谱写入记录"},
}
```

---

## 四、架构设计

### 4.1 组件层级

```
CatalogController (HTTP endpoints)
       ↓
CatalogService (business logic + caching + static metadata merge)
       ├── CatalogDao (PostgreSQL system catalog queries)
       ├── SchemaDao  (existing — JSONB key discovery)
       └── GraphDao   (optional — Neo4j node/edge statistics)
```

### 4.2 缓存策略

- 表列表 + 统计信息缓存 **5 分钟**（`pg_total_relation_size` 在大量表时较慢）
- 支持 `?refresh=true` 参数强制刷新
- 缓存使用 in-memory sync.Map，无需 Redis

### 4.3 文件结构

```
internal/
├── model/
│   └── catalog.go           # CatalogOverview, TableCatalogEntry, ColumnMeta 等结构体
├── dao/
│   └── catalog_dao.go       # PostgreSQL 系统表查询
├── service/
│   └── catalog_service.go   # 静态注册合并 + 缓存
├── controller/
│   └── catalog_controller.go  # HTTP endpoints
├── consts/
│   └── components_v2.go     # 新增 COMP_DAO_CATALOG, COMP_SVC_CATALOG, COMP_CTRL_CATALOG
├── registry_ext/
│   ├── dao_v2.go            # 注册 CatalogDao
│   ├── service_v2.go        # 注册 CatalogService
│   └── controller_v2.go     # 注册 CatalogController
└── api/
    └── router_v2.go         # 新增 /api/v2/catalog/* 路由
```

---

## 五、Cthulhu 数据看板

### 5.1 页面规划

在 Cthulhu `features/phoenixa` 下新增数据目录页面：

| 路由 | 组件 | 内容 |
|------|------|------|
| `/phoenixa/catalog` | `DataCatalogComponent` | 数据总览 + 表列表 + 存储分布 |
| `/phoenixa/catalog/:schema/:table` | `TableDetailComponent` | 单表详情（列/JSONB/索引） |

### 5.2 总览页布局

```
┌─────────────────────────────────────────────────────────────────────┐
│  数据目录总览                                      [刷新] [自动刷新 60s] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ 25 张表   │ │ 1.5 亿行  │ │ 186 GB   │ │ 45 GB    │               │
│  │ Total     │ │ Total    │ │ Data     │ │ Index    │               │
│  │ Tables    │ │ Rows     │ │ Size     │ │ Size     │               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
│                                                                     │
│  ┌──────────────────────┐  ┌────────────────────────────────┐      │
│  │ 存储分布 (Pie)        │  │ 按域统计 (Bar)                  │      │
│  │                       │  │                                │      │
│  │   NVMe ■ 136 GB      │  │  bars     ████████████ 80 GB   │      │
│  │   SATA ■  50 GB      │  │  taxonomy ██████      51 GB   │      │
│  │                       │  │  kg       ████        30 GB   │      │
│  │                       │  │  financial ██         8 GB    │      │
│  └──────────────────────┘  └────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 表详情列表                              [搜索] [域筛选 ▼]      │   │
│  ├──────┬──────────────────┬────────┬──────┬──────┬─────┬──────┤   │
│  │ 域    │ 表名              │ 行数    │ 数据  │ 索引  │ 层级 │ 时间  │   │
│  ├──────┼──────────────────┼────────┼──────┼──────┼─────┼──────┤   │
│  │ bars │ bars_..daily_nf  │ 25M    │ 3.2G │ 1.1G │ Hot │ 2000↔│   │
│  │ bars │ bars_..1min_nf   │ 80M    │ 40G  │ 8G   │Warm │ 2020↔│   │
│  └──────┴──────────────────┴────────┴──────┴──────┴─────┴──────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 表详情页布局

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← 返回  │  public.financial_statement                              │
├─────────────────────────────────────────────────────────────────────┤
│  域: financial  │  描述: 财务报表（三表+快报+预告）                    │
│  行数: 3.7M     │  数据: 7.5 GB  │  索引: 2.1 GB  │  层级: Hot      │
│  时间范围: 2005-01-01 ~ 2026-03-31  │  来源: artemis                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  列信息                                                              │
│  ┌──────────────────┬─────────────────┬──────┬───────────────────┐   │
│  │ 列名              │ 类型             │ 可空  │ 描述               │   │
│  ├──────────────────┼─────────────────┼──────┼───────────────────┤   │
│  │ id               │ bigint          │  ✗   │ 自增主键           │   │
│  │ symbol           │ varchar(32)     │  ✗   │ 证券代码           │   │
│  │ data_json        │ jsonb           │  ✗   │ 财务报表数据        │   │
│  └──────────────────┴─────────────────┴──────┴───────────────────┘   │
│                                                                     │
│  JSONB 字段详情 (data_json)                                          │
│  ┌─────────────────┬──────────────────────────────────────────┐     │
│  │ statement_type   │ 发现的 Keys                              │     │
│  ├─────────────────┼──────────────────────────────────────────┤     │
│  │ balance_sheet   │ TOTAL_ASSETS, TOTAL_LIAB, TOTAL_EQUITY… │     │
│  │ income          │ REVENUE, OPERATE_PROFIT, NET_PROFIT…    │     │
│  │ cashflow        │ NET_OPER_CASHFLOW, NET_INVEST_CASHFLOW… │     │
│  └─────────────────┴──────────────────────────────────────────┘     │
│                                                                     │
│  索引信息                                                            │
│  ┌──────────────────┬────────────────────────────┬──────┬──────┐   │
│  │ 索引名            │ 列                          │ 唯一  │ 类型  │   │
│  ├──────────────────┼────────────────────────────┼──────┼──────┤   │
│  │ uk_fin_stmt      │ source, symbol, mkt, ...   │  ✓   │ btree│   │
│  │ idx_fs_data_gin  │ data_json                  │  ✗   │ GIN  │   │
│  └──────────────────┴────────────────────────────┴──────┴──────┘   │
│                                                                     │
│  数据血缘                                                            │
│  来源: artemis → REST API batch upsert                              │
│  刷新频率: 每日增量                                                   │
│  API: POST /api/v2/financial/{source}/{statement_type}/upsert       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 六、实施计划

| 阶段 | 内容 | 预估工时 |
|------|------|---------|
| Phase 1 | CatalogDao + CatalogService + CatalogController（基础 API） | 1 天 |
| Phase 2 | 静态元数据注册（表描述、列描述、血缘） | 0.5 天 |
| Phase 3 | Cthulhu 数据目录总览页 | 1 天 |
| Phase 4 | Cthulhu 表详情页 + JSONB 内省展示 | 0.5 天 |
| **总计** | | **~3 天** |

---

## 七、后续扩展（非当前范围）

1. **数据质量指标**：NULL 比例、重复率、异常值检测
2. **数据新鲜度监控**：表最后更新距今时间，超时告警
3. **全文搜索**：支持搜索表名/描述/列名
4. **数据血缘可视化**：DAG 展示 artemis → phoenixA → cthulhu 数据流
5. **因子目录整合**：因子引擎投产后，将因子元数据纳入数据目录
6. **变更追踪**：记录表结构变更历史

