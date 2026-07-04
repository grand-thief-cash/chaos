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
	"taxonomy_category_derived_flags": {
		Domain:      "taxonomy",
		Description: "分类语义派生标记（PhoenixA 维护）",
		Lineage: &model.DataLineage{
			SourceSystem:    "phoenixA",
			IngestionMethod: "DAO derive + upsert",
			RefreshSchedule: "随 taxonomy 更新增量刷新",
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
	"adjust_factor": {
		Domain:      "bars",
		Description: "复权因子（用于复权行情重建）",
		TimeColumn:  "divid_operate_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/adjust-factors/{source}/upsert",
		},
	},
	"long_hu_bang": {
		Domain:      "regime",
		Description: "龙虎榜营业部明细",
		TimeColumn:  "trade_date",
		Lineage: &model.DataLineage{
			SourceSystem:    "artemis",
			IngestionMethod: "REST API batch upsert",
			RefreshSchedule: "每日增量",
			APIEndpoint:     "POST /api/v2/long-hu-bang/{source}/upsert",
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
	"*.id":                 "自增主键",
	"*.symbol":             "证券代码",
	"*.market":             "市场（如 zh_a, hk, us）",
	"*.source":             "数据来源",
	"*.created_at":         "创建时间",
	"*.updated_at":         "更新时间",
	"*.trade_date":         "交易日期",
	"*.open":               "开盘价",
	"*.high":               "最高价",
	"*.low":                "最低价",
	"*.close":              "收盘价",
	"*.volume":             "成交量",
	"*.amount":             "成交额",
	"*.preclose":           "昨收价",
	"*.pct_chg":            "涨跌幅(%)",
	"*.data_json":          "业务数据（JSONB 灵活字段）",
	"*.derived_flags":      "PhoenixA 派生语义标记（JSONB）",
	"*.statement_type":     "报表类型（balance_sheet/income/cashflow/profit_express/profit_notice）",
	"*.reporting_period":   "报告期（YYYYMMDD）",
	"*.action_type":        "公司行为类型（dividend/right_issue）",
	"*.ann_date":           "公告日期",
	"*.divid_operate_date": "除权除息日期",
	"*.fore_adjust_factor": "向前复权因子",
	"*.back_adjust_factor": "向后复权因子",
	"*.adjust_factor":      "本次复权因子",
	"*.security_name":      "证券名称",
	"*.reason_type":        "上榜原因类型代码",
	"*.reason_type_name":   "上榜原因名称",
	"*.trader_name":        "营业部名称",
	"*.flow_mark":          "买卖方向（1买入/2卖出）",
	"*.change_range":       "涨跌幅（%）",
	"*.buy_amount":         "买入金额（元）",
	"*.sell_amount":        "卖出金额（元）",
	"*.total_amount":       "实际交易金额（元）",
	"*.total_volume":       "实际交易量（万股）",
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

// ─── Data Capability Registry ───
// Describes what each table/domain can PROVIDE, for LLM function-calling discovery.
// When a new download task is onboarded, add its capability here.

var tableCapabilityRegistry = map[string]*model.DataCapability{
	"financial_statement": {
		Provider:            "财务报表",
		ProviderDescription: "上市公司财务报表数据，包含资产负债表、利润表、现金流量表、业绩快报、业绩预告、以及偿债能力指标。数据按 (source, statement_type) 分区存储，支持 PIT（时间点）查询。",
		DataTypes: []model.DataTypeInfo{
			{TypeValue: "balance_sheet", Label: "资产负债表", Description: "季度/年度资产负债表，含总资产、总负债、股东权益等", Source: "amazing_data"},
			{TypeValue: "income", Label: "利润表", Description: "季度/年度利润表，含营收、净利润、EPS等", Source: "amazing_data"},
			{TypeValue: "cashflow", Label: "现金流量表", Description: "季度/年度现金流量表，含经营/投资/筹资活动现金流", Source: "amazing_data"},
			{TypeValue: "profit_express", Label: "业绩快报", Description: "上市公司业绩快报数据", Source: "amazing_data"},
			{TypeValue: "profit_notice", Label: "业绩预告", Description: "上市公司业绩预告，含预告类型和预计利润范围", Source: "amazing_data"},
			{TypeValue: "bs_balance", Label: "偿债能力指标(baostock)", Description: "季频偿债能力数据：流动比率、速动比率、现金比率、资产负债率、权益乘数等", Source: "baostock"},
		},
		OutputFields: []model.FieldDesc{
			{Name: "security_id", Type: "bigint", Description: "证券ID（逻辑外键 → security_registry.id，Phase 3 替代 symbol/market）"},
			{Name: "source", Type: "varchar(32)", Description: "数据来源（amazing_data/baostock）"},
			{Name: "statement_type", Type: "varchar(32)", Description: "报表类型"},
			{Name: "reporting_period", Type: "varchar(10)", Description: "报告期（YYYY-MM-DD）"},
			{Name: "report_type", Type: "varchar(32)", Description: "报告期名称"},
			{Name: "ann_date", Type: "varchar(10)", Description: "公告日期（YYYY-MM-DD）"},
			{Name: "comp_type_code", Type: "int", Description: "公司类型代码（1:非金融 2:银行 3:保险 4:证券）"},
			{Name: "data_json", Type: "jsonb", Description: "业务数据字段（JSONB），内容因 statement_type 而异", InJSONB: true},
		},
		QueryParams: []model.ParamDesc{
			{Name: "source", Type: "string", Required: true, Description: "数据来源", Enum: []string{"amazing_data", "baostock"}},
			{Name: "statement_type", Type: "string", Required: true, Description: "报表类型", Enum: []string{"balance_sheet", "income", "cashflow", "profit_express", "profit_notice", "bs_balance"}},
			{Name: "security_id", Type: "integer", Required: false, Description: "单个证券ID（security_registry.id）"},
			{Name: "security_ids", Type: "string", Required: false, Description: "证券ID列表（逗号分隔）"},
			{Name: "period_start", Type: "string", Required: false, Description: "报告期起始（YYYY-MM-DD）"},
			{Name: "period_end", Type: "string", Required: false, Description: "报告期截止（YYYY-MM-DD）"},
			{Name: "reporting_period", Type: "string", Required: false, Description: "单个报告期（YYYY-MM-DD）"},
			{Name: "reporting_periods", Type: "string", Required: false, Description: "报告期列表（逗号分隔）"},
			{Name: "ann_date_before", Type: "string", Required: false, Description: "PIT查询：仅返回公告日<=此日期的记录"},
			{Name: "report_type", Type: "string", Required: false, Description: "按报告期名称过滤"},
			{Name: "comp_type_code", Type: "int", Required: false, Description: "公司类型代码（1:非金融 2:银行 3:保险 4:证券）"},
			{Name: "fields", Type: "string", Required: false, Description: "返回字段列表（逗号分隔）"},
			{Name: "page", Type: "int", Required: false, Description: "页码"},
			{Name: "page_size", Type: "int", Required: false, Description: "每页条数"},
		},
		RefreshSchedule:     "每日增量",
		CoverageDescription: "A股全量上市公司，2007至今（baostock偿债能力）/ 历史全量（AmazingData三表）",
	},
	"corporate_action": {
		Provider:            "公司行为",
		ProviderDescription: "上市公司分红、配股、除权除息等公司行为数据。支持多数据来源（AmazingData/baostock），按 (source, action_type) 分区存储。",
		DataTypes: []model.DataTypeInfo{
			{TypeValue: "dividend", Label: "分红(AmazingData)", Description: "现金分红数据，含每股派息、分红进度等", Source: "amazing_data"},
			{TypeValue: "right_issue", Label: "配股(AmazingData)", Description: "配股数据，含配股比例、配股价格等", Source: "amazing_data"},
			{TypeValue: "bs_dividend", Label: "除权除息(baostock)", Description: "除权除息详细数据：税前/税后每股股利、每股红股、每股转增资本、各关键日期", Source: "baostock"},
		},
		OutputFields: []model.FieldDesc{
			{Name: "security_id", Type: "bigint", Description: "证券ID（逻辑外键 → security_registry.id，Phase 3 替代 symbol/market）"},
			{Name: "source", Type: "varchar(32)", Description: "数据来源（amazing_data/baostock）"},
			{Name: "action_type", Type: "varchar(32)", Description: "行为类型"},
			{Name: "ann_date", Type: "varchar(10)", Description: "公告日期（YYYY-MM-DD）"},
			{Name: "report_period", Type: "varchar(10)", Description: "报告年度"},
			{Name: "data_json", Type: "jsonb", Description: "详细数据字段（JSONB）", InJSONB: true},
		},
		QueryParams: []model.ParamDesc{
			{Name: "source", Type: "string", Required: true, Description: "数据来源", Enum: []string{"amazing_data", "baostock"}},
			{Name: "action_type", Type: "string", Required: true, Description: "行为类型", Enum: []string{"dividend", "right_issue", "bs_dividend"}},
			{Name: "security_id", Type: "integer", Required: false, Description: "单个证券ID（security_registry.id）"},
			{Name: "security_ids", Type: "string", Required: false, Description: "证券ID列表（逗号分隔）"},
		},
		RefreshSchedule:     "每日增量",
		CoverageDescription: "A股全量，2015至今（baostock除权除息）/ 历史全量（AmazingData分红配股）",
	},
	"adjust_factor": {
		Provider:            "复权因子",
		ProviderDescription: "A股复权因子数据，记录每次除权除息事件对应的前复权因子、后复权因子和本次复权因子，可用于基于本地不复权日线重建前复权/后复权价格序列。",
		DataTypes: []model.DataTypeInfo{
			{TypeValue: "adjust_factor", Label: "复权因子", Description: "Baostock query_adjust_factor 输出的事件级复权因子", Source: "baostock"},
		},
		OutputFields: []model.FieldDesc{
			{Name: "security_id", Type: "bigint", Description: "证券ID（逻辑外键 → security_registry.id，Phase 3 替代 symbol/market）"},
			{Name: "source", Type: "varchar(32)", Description: "数据来源（baostock）"},
			{Name: "divid_operate_date", Type: "varchar(10)", Description: "除权除息日期（YYYY-MM-DD）"},
			{Name: "fore_adjust_factor", Type: "numeric(20,8)", Description: "向前复权因子"},
			{Name: "back_adjust_factor", Type: "numeric(20,8)", Description: "向后复权因子"},
			{Name: "adjust_factor", Type: "numeric(20,8)", Description: "本次复权因子"},
		},
		QueryParams: []model.ParamDesc{
			{Name: "source", Type: "string", Required: true, Description: "数据来源", Enum: []string{"baostock"}},
			{Name: "security_id", Type: "integer", Required: false, Description: "单个证券ID（security_registry.id）"},
			{Name: "security_ids", Type: "string", Required: false, Description: "证券ID列表（逗号分隔）"},
			{Name: "start_date", Type: "string", Required: false, Description: "起始除权除息日期（YYYY-MM-DD）"},
			{Name: "end_date", Type: "string", Required: false, Description: "截止除权除息日期（YYYY-MM-DD）"},
			{Name: "fields", Type: "string", Required: false, Description: "返回字段列表（逗号分隔）"},
			{Name: "page", Type: "int", Required: false, Description: "页码"},
			{Name: "page_size", Type: "int", Required: false, Description: "每页条数"},
		},
		RefreshSchedule:     "每日增量",
		CoverageDescription: "A股全量，2015至今（baostock query_adjust_factor）",
	},
	"long_hu_bang": {
		Provider:            "龙虎榜",
		ProviderDescription: "A股龙虎榜营业部明细数据，字段数量少且结构稳定，直接以显式列存储证券、原因类型、席位名称以及金额/交易量指标，可用于异常交易和市场情绪分析。",
		DataTypes: []model.DataTypeInfo{
			{TypeValue: "long_hu_bang", Label: "龙虎榜明细", Description: "AmazingData get_long_hu_bang 输出的营业部级龙虎榜数据", Source: "amazing_data"},
		},
		OutputFields: []model.FieldDesc{
			{Name: "security_id", Type: "bigint", Description: "证券ID（逻辑外键 → security_registry.id，Phase 3 替代 symbol/market）"},
			{Name: "source", Type: "varchar(32)", Description: "数据来源（amazing_data）"},
			{Name: "trade_date", Type: "varchar(10)", Description: "交易日期（YYYY-MM-DD）"},
			{Name: "security_name", Type: "varchar(128)", Description: "证券名称"},
			{Name: "reason_type", Type: "varchar(32)", Description: "上榜原因类型代码"},
			{Name: "reason_type_name", Type: "varchar(256)", Description: "上榜原因名称"},
			{Name: "trader_name", Type: "varchar(256)", Description: "营业部名称"},
			{Name: "flow_mark", Type: "smallint", Description: "买卖方向：1买入，2卖出"},
			{Name: "change_range", Type: "numeric(20,6)", Description: "涨跌幅（%）"},
			{Name: "buy_amount", Type: "numeric(24,4)", Description: "买入金额（元）"},
			{Name: "sell_amount", Type: "numeric(24,4)", Description: "卖出金额（元）"},
			{Name: "total_amount", Type: "numeric(24,4)", Description: "实际交易金额（元）"},
			{Name: "total_volume", Type: "numeric(24,4)", Description: "实际交易量（万股）"},
		},
		QueryParams: []model.ParamDesc{
			{Name: "source", Type: "string", Required: true, Description: "数据来源", Enum: []string{"amazing_data"}},
			{Name: "security_id", Type: "integer", Required: false, Description: "单个证券ID（security_registry.id）"},
			{Name: "security_ids", Type: "string", Required: false, Description: "证券ID列表（逗号分隔）"},
			{Name: "trade_date", Type: "string", Required: false, Description: "精确交易日期（YYYY-MM-DD）"},
			{Name: "start_date", Type: "string", Required: false, Description: "起始交易日期（YYYY-MM-DD）"},
			{Name: "end_date", Type: "string", Required: false, Description: "截止交易日期（YYYY-MM-DD）"},
			{Name: "reason_type", Type: "string", Required: false, Description: "上榜原因类型代码"},
			{Name: "trader_name", Type: "string", Required: false, Description: "营业部名称"},
			{Name: "flow_mark", Type: "int", Required: false, Description: "买卖方向（1买入，2卖出）"},
			{Name: "fields", Type: "string", Required: false, Description: "返回字段列表（逗号分隔）"},
			{Name: "page", Type: "int", Required: false, Description: "页码"},
			{Name: "page_size", Type: "int", Required: false, Description: "每页条数"},
		},
		RefreshSchedule:     "每日增量",
		CoverageDescription: "A股全量，历史可回溯至 AmazingData 提供的交易异动覆盖范围",
	},
	"bars_": {
		Provider:            "K线行情",
		ProviderDescription: "股票/指数/ETF的OHLCV行情数据，支持日/周/月/分钟级别，前复权/后复权/不复权。附带估值指标扩展数据（PE/PB/PS/PCF/换手率）。",
		DataTypes: []model.DataTypeInfo{
			{TypeValue: "daily_nf", Label: "日K线（不复权）", Description: "日频OHLCV + 估值指标"},
			{TypeValue: "daily_hfq", Label: "日K线（后复权）", Description: "日频OHLCV后复权 + 估值指标"},
		},
		OutputFields: []model.FieldDesc{
			{Name: "trade_date", Type: "varchar(10)", Description: "交易日期（YYYY-MM-DD）"},
			{Name: "symbol", Type: "varchar(32)", Description: "证券代码"},
			{Name: "open/high/low/close", Type: "numeric", Description: "OHLC价格"},
			{Name: "volume", Type: "bigint", Description: "成交量"},
			{Name: "amount", Type: "bigint", Description: "成交额"},
			{Name: "pct_chg", Type: "numeric", Description: "涨跌幅(%)"},
			{Name: "pe_ttm/pb_mrq/ps_ttm", Type: "numeric", Description: "估值指标（扩展表）", InJSONB: false},
		},
		QueryParams: []model.ParamDesc{
			{Name: "symbol", Type: "string", Required: true, Description: "证券代码"},
			{Name: "start_date", Type: "string", Required: false, Description: "起始日期"},
			{Name: "end_date", Type: "string", Required: false, Description: "截止日期"},
		},
		RefreshSchedule:     "每日增量（交易日18:00后）",
		CoverageDescription: "A股全量（SH/SZ/BJ），2009至今（后复权）/ 2016至今（不复权）",
	},
	"security_registry": {
		Provider:            "证券注册表",
		ProviderDescription: "统一的证券基础信息注册表，代理主键 security_id 是 (exchange, asset_type, symbol) 自然键的代理，作为其他表逻辑外键的引用目标。包含代码、名称、市场、上市日期、资产类型等。",
		OutputFields: []model.FieldDesc{
			{Name: "security_id", Type: "bigint", Description: "代理主键 (BIGSERIAL)，被其他表 security_id 逻辑引用"},
			{Name: "symbol", Type: "varchar(32)", Description: "证券代码"},
			{Name: "name", Type: "varchar(128)", Description: "证券名称"},
			{Name: "exchange", Type: "varchar(16)", Description: "交易所（SH/SZ/BJ）"},
			{Name: "asset_type", Type: "varchar(16)", Description: "资产类型（stock/index/etf）"},
			{Name: "market", Type: "varchar(16)", Description: "市场（zh_a/hk/us）"},
			{Name: "list_date", Type: "varchar(10)", Description: "上市日期"},
		},
		RefreshSchedule:     "每日全量",
		CoverageDescription: "A股全量（SH+SZ+BJ），含退市标记",
	},
}

// ─── Business API Registry ───

// tableApiMap maps table names/prefixes to their API endpoints.
var tableApiMap = map[string][]model.ApiEndpointRef{
	"security_registry": {
		{Method: "GET", Path: "/api/v2/securities", Description: "查询证券列表"},
		{Method: "GET", Path: "/api/v2/securities/{security_id}", Description: "按 security_id 查询单个证券"},
		{Method: "POST", Path: "/api/v2/securities/upsert", Description: "批量写入证券"},
	},
	"financial_statement": {
		{Method: "GET", Path: "/api/v2/financial/{source}/{statement_type}", Description: "查询财务报表"},
		{Method: "POST", Path: "/api/v2/financial/{source}/{statement_type}/upsert", Description: "写入财务报表"},
	},
	"corporate_action": {
		{Method: "GET", Path: "/api/v2/corporate-action/{source}/{action_type}", Description: "查询公司行为"},
		{Method: "POST", Path: "/api/v2/corporate-action/{source}/{action_type}/upsert", Description: "写入公司行为"},
	},
	"adjust_factor": {
		{Method: "GET", Path: "/api/v2/adjust-factors/{source}", Description: "查询复权因子"},
		{Method: "POST", Path: "/api/v2/adjust-factors/{source}/upsert", Description: "写入复权因子"},
	},
	"long_hu_bang": {
		{Method: "GET", Path: "/api/v2/long-hu-bang/{source}", Description: "查询龙虎榜明细"},
		{Method: "POST", Path: "/api/v2/long-hu-bang/{source}/upsert", Description: "写入龙虎榜明细"},
	},
	"taxonomy_category": {
		{Method: "GET", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories", Description: "查询分类节点"},
		{Method: "POST", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/upsert", Description: "写入分类节点"},
	},
	"taxonomy_security_map": {
		{Method: "GET", Path: "/api/v2/taxonomy/{source}/{taxonomy}/mapping/by_category/{category_id}", Description: "按分类查映射"},
		{Method: "POST", Path: "/api/v2/taxonomy/{source}/{taxonomy}/mapping/upsert", Description: "写入映射"},
	},
	"industry_constituent": {
		{Method: "GET", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_category/{category_id}", Description: "查询行业成分"},
		{Method: "POST", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/upsert", Description: "写入行业成分"},
	},
	"industry_weight": {
		{Method: "GET", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/{category_id}", Description: "查询行业权重"},
	},
	"industry_daily": {
		{Method: "GET", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily?category_id=", Description: "查询行业日线"},
		{Method: "POST", Path: "/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily/upsert", Description: "写入行业日线"},
	},
	"strategy_run_summary": {
		{Method: "GET", Path: "/api/v1/strategy/run/list", Description: "查询策略列表"},
		{Method: "GET", Path: "/api/v1/strategy/run/{run_id}", Description: "查询策略详情"},
	},
	"strategy_run_artifact": {
		{Method: "GET", Path: "/api/v1/strategy/run/{run_id}/artifacts", Description: "查询策略产物"},
	},
	"bars_": {
		{Method: "GET", Path: "/api/v2/bars/{asset_type}/{market}", Description: "查询K线行情"},
		{Method: "POST", Path: "/api/v2/bars/{asset_type}/{market}/upsert", Description: "写入K线行情"},
		{Method: "GET", Path: "/api/v2/bars/{asset_type}/{market}/last_update", Description: "最近更新时间"},
	},
	"factor_": {
		{Method: "GET", Path: "/api/v2/catalog/tables", Description: "因子数据（规划中）"},
	},
}

// domainApiRegistry maps business domains to example queries and cross-refs.
var domainApiRegistry = map[string]struct {
	Description  string
	ExampleCalls []model.ExampleCall
	CrossRefs    []model.CrossRef
}{
	"bars": {
		Description: "K线行情数据与复权支撑数据，按资产类型(stock/index/etf)和市场(zh_a/hk/us)组织",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询A股日线行情", URL: "GET /api/v2/bars/stock/zh_a?symbol=000001&start_date=2026-01-01"},
			{Title: "查询指数行情", URL: "GET /api/v2/bars/index/zh_a?symbol=000001&start_date=2026-01-01"},
			{Title: "查询复权因子", URL: "GET /api/v2/adjust-factors/baostock?security_id=1&start_date=2024-01-01"},
		},
		CrossRefs: []model.CrossRef{
			{ToTable: "security_registry", JoinKey: "security_id", Description: "证券基础信息（adjust_factor 经 security_id 关联；bars_* 物理表仍存 symbol，API 将在 Phase 4 迁 security_id）"},
		},
	},
	"security": {
		Description: "证券基础信息注册表，统一的证券代码、名称、市场、上市日期等",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询A股证券列表", URL: "GET /api/v2/securities?market=zh_a"},
			{Title: "按 security_id 查询单个证券", URL: "GET /api/v2/securities/{security_id}"},
		},
	},
	"taxonomy": {
		Description: "行业分类数据，包含行业节点、证券映射、行业成分、权重、日线行情",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询申万行业分类", URL: "GET /api/v2/taxonomy/sw/industry/zh_a/categories"},
			{Title: "按 security_id 查所属行业", URL: "GET /api/v2/taxonomy/by_security/{security_id}"},
		},
		CrossRefs: []model.CrossRef{
			{ToTable: "security_registry", JoinKey: "security_id", Description: "证券基础信息（Phase 2 surrogate-key 重构后映射表经 security_id 关联）"},
			{ToTable: "taxonomy_category", JoinKey: "category_id", Description: "行业分类节点"},
		},
	},
	"financial": {
		Description: "财务报表和公司行为数据，资产负债表/利润表/现金流量表/业绩预告/分红配股",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询资产负债表", URL: "GET /api/v2/financial/amazing_data/balance_sheet?security_id=1&page=1"},
			{Title: "查询分红信息", URL: "GET /api/v2/corporate-action/amazing_data/dividend?security_id=1"},
		},
		CrossRefs: []model.CrossRef{
			{ToTable: "security_registry", JoinKey: "security_id", Description: "证券基础信息（Phase 3 surrogate-key 重构后经 security_id 关联）"},
		},
	},
	"strategy": {
		Description: "策略回测运行结果和产物数据",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询策略列表", URL: "GET /api/v1/strategy/run/list?strategy_code=momentum"},
		},
	},
	"kg": {
		Description: "知识图谱数据，文档/抽取/事件/影响日志/图谱写入",
		ExampleCalls: []model.ExampleCall{
			{Title: "查询事件", URL: "GET /api/v1/kg/events?event_type=risk"},
		},
	},
	"factor": {Description: "因子数据（规划中）"},
	"regime": {Description: "市场状态引擎数据（规划中）"},
}

func (s *CatalogService) resolveAPIs(table string) []model.ApiEndpointRef {
	if apis, ok := tableApiMap[table]; ok {
		return apis
	}
	for prefix, apis := range tableApiMap {
		if strings.HasSuffix(prefix, "_") && strings.HasPrefix(table, prefix) {
			return apis
		}
	}
	return nil
}

func (s *CatalogService) resolveDomainMeta(domain string) (examples []model.ExampleCall, xrefs []model.CrossRef, desc string) {
	if info, ok := domainApiRegistry[domain]; ok {
		return info.ExampleCalls, info.CrossRefs, info.Description
	}
	return nil, nil, ""
}

// resolveCapability finds the capability description for a table using exact/prefix matching.
func (s *CatalogService) resolveCapability(table string) *model.DataCapability {
	if capability, ok := tableCapabilityRegistry[table]; ok {
		return capability
	}
	for prefix, capability := range tableCapabilityRegistry {
		if strings.HasSuffix(prefix, "_") && strings.HasPrefix(table, prefix) {
			return capability
		}
	}
	return nil
}

// queryDataSources returns per-source statistics for a table.
// Only works for tables that have a "source" column.
func (s *CatalogService) queryDataSources(ctx context.Context, schema, table, timeColumn string) []model.DataSourceSummary {
	fullTable := table
	if schema != "" && schema != "public" {
		fullTable = schema + "." + table
	}
	// Validate identifiers
	for _, id := range []string{schema, table} {
		if id != "" && !dao.SafeIdentifierRe.MatchString(id) {
			return nil
		}
	}

	// Check which identity column the table exposes: Phase 3 data tables
	// (financial_statement / corporate_action / equity_structure / adjust_factor /
	// long_hu_bang) use security_id; bars_* physical tables still use symbol
	// (storage exception, §3.2; bars API migrates to security_id in Phase 4).
	type colCheck struct {
		ColName string
	}
	var foundCols []colCheck
	checkQ := fmt.Sprintf(
		`SELECT column_name AS col_name FROM information_schema.columns WHERE table_schema = '%s' AND table_name = '%s' AND column_name IN ('source', 'security_id', 'symbol')`,
		schema, table,
	)
	if err := s.Dao.DB().WithContext(ctx).Raw(checkQ).Scan(&foundCols).Error; err != nil {
		return nil
	}
	hasSource, hasSecurityID, hasSymbol := false, false, false
	for _, c := range foundCols {
		switch c.ColName {
		case "source":
			hasSource = true
		case "security_id":
			hasSecurityID = true
		case "symbol":
			hasSymbol = true
		}
	}
	if !hasSource {
		return nil
	}

	type sourceRow struct {
		Source        string
		RowCount      int64
		DistinctCodes int
		MinDate       string
		MaxDate       string
	}

	var rows []sourceRow
	var query string

	distinctExpr := "0"
	if hasSecurityID {
		distinctExpr = "COUNT(DISTINCT security_id)"
	} else if hasSymbol {
		distinctExpr = "COUNT(DISTINCT symbol)"
	}

	if timeColumn != "" && dao.SafeIdentifierRe.MatchString(timeColumn) {
		query = fmt.Sprintf(
			`SELECT source,
			        COUNT(*) AS row_count,
			        %s AS distinct_codes,
			        MIN(%s)::text AS min_date,
			        MAX(%s)::text AS max_date
			 FROM %s
			 GROUP BY source
			 ORDER BY row_count DESC`,
			distinctExpr, timeColumn, timeColumn, fullTable,
		)
	} else {
		query = fmt.Sprintf(
			`SELECT source,
			        COUNT(*) AS row_count,
			        %s AS distinct_codes,
			        '' AS min_date,
			        '' AS max_date
			 FROM %s
			 GROUP BY source
			 ORDER BY row_count DESC`,
			distinctExpr, fullTable,
		)
	}

	if err := s.Dao.DB().WithContext(ctx).Raw(query).Scan(&rows).Error; err != nil {
		logging.Warnf(ctx, "catalog: query data sources for %s failed: %v", fullTable, err)
		return nil
	}

	result := make([]model.DataSourceSummary, 0, len(rows))
	for _, r := range rows {
		result = append(result, model.DataSourceSummary{
			Source:        r.Source,
			RowCount:      r.RowCount,
			DistinctCodes: r.DistinctCodes,
			MinDate:       r.MinDate,
			MaxDate:       r.MaxDate,
		})
	}
	return result
}

func (s *CatalogService) listTablesInDomain(tables []model.TableCatalogEntry, domain string) []string {
	var names []string
	for _, t := range tables {
		if t.Domain == domain {
			names = append(names, t.TableName)
		}
	}
	return names
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
	Dao          *dao.CatalogDao         `infra:"dep:dao_catalog"`
	SchemaDao    *dao.SchemaDao          `infra:"dep:dao_schema"`
	GraphDao     *dao.GraphDao           `infra:"dep_optional:dao_graph"`
	FieldDictDao *dao.FieldDictionaryDao `infra:"dep:dao_field_dictionary"`

	cacheMu      sync.RWMutex
	cachedTables []model.TableCatalogEntry
	cacheTime    time.Time
	cacheTTL     time.Duration

	dictMu     sync.RWMutex
	cachedDict *model.DataDictionary
	dictTime   time.Time
	dictTTL    time.Duration

	// fieldDictCache caches the per-storage-table field dictionary view used
	// to aggregate dictionary + observed stats in GetDataDictionary. Keyed by
	// storage_table name (e.g. "financial_statement").
	fieldDictMu    sync.RWMutex
	fieldDictCache map[string]*tableFieldDict
	fieldDictTime  time.Time
	fieldDictTTL   time.Duration
}

func NewCatalogService() *CatalogService {
	return &CatalogService{
		BaseComponent: core.NewBaseComponent(bizConsts.COMP_SVC_CATALOG),
		cacheTTL:      5 * time.Minute,
		dictTTL:       10 * time.Minute,
		fieldDictTTL:  10 * time.Minute,
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
	filtered := make([]model.TableCatalogEntry, 0)
	for _, t := range tables {
		if t.Domain == domain {
			filtered = append(filtered, t)
		}
	}
	return filtered, nil
}

// GetTableDetail returns detailed metadata for a specific table.
func (s *CatalogService) GetTableDetail(ctx context.Context, schema, table string, refresh bool) (*model.TableDetail, error) {
	schemaCtx := ctx
	if refresh {
		schemaCtx = dao.WithSchemaCacheBypass(ctx)
	}
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

	// Get JSONB keys for JSONB columns (check column type, not HasJSONB flag)
	for i, col := range cols {
		if strings.Contains(col.Type, "jsonb") {
			jsonbKeys := s.discoverJSONBKeys(schemaCtx, schema, table, col.Name)
			if jsonbKeys != nil {
				cols[i].JSONBKeys = jsonbKeys
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

	// Attach business metadata
	detail.ApiEndpoints = s.resolveAPIs(table)
	exCalls, xRefs, domainDesc := s.resolveDomainMeta(detail.Domain)
	detail.ExampleCalls = exCalls
	detail.RelatedTables = xRefs
	if domainDesc != "" {
		detail.BusinessDomain = &model.BusinessDomainSummary{
			Domain:         detail.Domain,
			Label:          domainDescriptions[detail.Domain],
			Description:    domainDesc,
			TablesInDomain: s.listTablesInDomain(tables, detail.Domain),
		}
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

	// Rebuild cache (ANALYZE first on refresh to get accurate pg statistics)
	if refresh {
		s.Dao.AnalyzeSchemas(ctx, []string{"public", "kg", "ods", "dwd", "govern"})
	}
	rows, err := s.Dao.ListTables(ctx, []string{"public", "kg", "ods", "dwd", "govern"})
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
	s.cacheTime = time.Now()
	s.cachedTables = tables
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
// Works for any table — first tries type-based discovery (for financial/corporate tables),
// then falls back to generic key discovery.
func (s *CatalogService) discoverJSONBKeys(ctx context.Context, schema, table, column string) any {
	if s.SchemaDao == nil {
		return nil
	}

	// Try type-based discovery first (for financial_statement / corporate_action)
	spec, ok := map[string]struct {
		Domain     string
		TypeColumn string
	}{
		"financial_statement": {"financial_statement", "statement_type"},
		"corporate_action":    {"corporate_action", "action_type"},
	}[table]
	if ok {
		types, err := s.SchemaDao.ListTypes(ctx, spec.Domain)
		if err == nil {
			result := map[string][]string{}
			for _, t := range types {
				fr, err := s.SchemaDao.DiscoverFields(ctx, spec.Domain, t, 100)
				if err != nil {
					logging.Warnf(ctx, "catalog: type-based discovery for %s/%s failed: %v", table, t, err)
					continue
				}
				if fr == nil || len(fr.Fields) == 0 {
					continue
				}
				result[t] = fr.Fields
			}
			if len(result) > 0 {
				return result
			}
		}
	}

	// Generic JSONB key discovery for any table
	keys, err := s.SchemaDao.DiscoverJSONBKeysGeneric(ctx, schema, table, column, 200)
	if err != nil || len(keys) == 0 {
		return nil
	}
	return keys
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

// GetDataDictionary returns a comprehensive machine-readable description of all available data.
// Suitable for UI display and LLM function calling.
// Results are cached for dictTTL duration (default 10 minutes).
func (s *CatalogService) GetDataDictionary(ctx context.Context, refresh bool) (*model.DataDictionary, error) {
	schemaCtx := ctx
	if refresh {
		schemaCtx = dao.WithSchemaCacheBypass(ctx)
	}
	// Check dict cache first
	if !refresh {
		s.dictMu.RLock()
		if s.cachedDict != nil && time.Since(s.dictTime) < s.dictTTL {
			result := s.cachedDict
			s.dictMu.RUnlock()
			return result, nil
		}
		s.dictMu.RUnlock()
	}

	tables, _, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}

	// Load the field dictionary view (storage_table -> dict) once. Used to
	// attach the aggregated dictionary + ungoverned-key diff to governed
	// tables. When FieldDictDao is not registered, this returns nil and the
	// data-dictionary falls back to observed-only behavior.
	fieldDictMap, dictErr := s.loadFieldDictionary(ctx, refresh)
	if dictErr != nil {
		logging.Warnf(ctx, "data-dict: load field dictionary failed: %v", dictErr)
		fieldDictMap = nil
	}

	entries := make([]model.TableDictionaryEntry, 0, len(tables))
	for _, t := range tables {
		entry := model.TableDictionaryEntry{
			Schema:      t.Schema,
			TableName:   t.TableName,
			Domain:      t.Domain,
			Description: t.Description,
			RowCount:    t.RowCount,
			StorageTier: t.StorageTier,
			Tablespace:  t.Tablespace,
			TimeRange:   t.TimeRange,
		}

		// Get column metadata
		cols, err := s.Dao.GetTableColumns(ctx, t.Schema, t.TableName)
		if err != nil {
			logging.Errorf(ctx, "data-dict: get columns for %s.%s failed: %v", t.Schema, t.TableName, err)
		}
		colDicts := make([]model.ColumnDictionary, 0, len(cols))
		// observedDataJSONKeys captures the JSONB keys discovered for the
		// data_json column so we can diff against the dictionary below.
		var observedDataJSONKeys []model.JSONBKeyRef
		for _, col := range cols {
			cd := model.ColumnDictionary{
				Name:         col.Name,
				Type:         col.Type,
				Nullable:     col.Nullable,
				IsPrimaryKey: col.IsPrimaryKey,
				Description:  s.getColumnDescription(t.TableName, col.Name),
			}
			// JSONB key discovery
			if t.HasJSONB && strings.Contains(col.Type, "jsonb") && s.SchemaDao != nil {
				keys, err := s.SchemaDao.DiscoverJSONBKeysGeneric(schemaCtx, t.Schema, t.TableName, col.Name, 100)
				if err == nil && len(keys) > 0 {
					cd.JSONBKeys = make([]model.JSONBKeyRef, 0, len(keys))
					for _, k := range keys {
						cd.JSONBKeys = append(cd.JSONBKeys, model.JSONBKeyRef{
							Name:       k.Name,
							ValueType:  k.ValueType,
							SampleVals: k.SampleVals,
						})
					}
					// The field dictionary applies to the data_json column.
					// Remember observed keys for ungoverned-key diffing.
					if col.Name == "data_json" {
						observedDataJSONKeys = cd.JSONBKeys
					}
				}
			}
			// Enum value discovery for known low-cardinality text columns
			if strings.Contains(col.Type, "character") || strings.Contains(col.Type, "text") {
				cd.EnumValues = s.discoverEnumValues(ctx, t.Schema, t.TableName, col.Name)
			}
			colDicts = append(colDicts, cd)
		}
		entry.Columns = colDicts

		// Get indexes
		indexes, err := s.Dao.GetTableIndexes(ctx, t.Schema, t.TableName)
		if err != nil {
			logging.Errorf(ctx, "data-dict: get indexes for %s.%s failed: %v", t.Schema, t.TableName, err)
		}
		entry.Indexes = indexes

		// Get lineage from meta registry
		meta := s.findMeta(t.Schema, t.TableName)
		entry.Lineage = meta.Lineage

		// Attach business metadata
		entry.ApiEndpoints = s.resolveAPIs(t.TableName)
		exCalls, xRefs, _ := s.resolveDomainMeta(t.Domain)
		entry.ExampleCalls = exCalls
		entry.RelatedTables = xRefs

		// Enhanced: attach capability metadata
		entry.Capability = s.resolveCapability(t.TableName)

		// Enhanced: attach per-source statistics
		entry.DataSources = s.queryDataSources(ctx, t.Schema, t.TableName, meta.TimeColumn)

		if meta.TimeColumn != "" && entry.TimeRange == nil {
			tr, trErr := s.Dao.GetTimeRange(ctx, t.Schema, t.TableName, meta.TimeColumn)
			if trErr == nil && tr != nil {
				entry.TimeRange = tr
			}
		}

		// Phase 2: attach aggregated field dictionary view for governed tables.
		// Combines the authoritative dictionary contract with observed JSONB
		// key stats and flags ungoverned keys (observed but not registered).
		if fieldDictMap != nil {
			if fd, ok := fieldDictMap[t.TableName]; ok {
				entry.FieldDictionary = &model.TableFieldDictionary{
					Dataset:         fd.Dataset,
					Source:          fd.Source,
					ContractVersion: fd.ContractVersion,
					Groups:          fd.Groups,
					UngovernedKeys:  computeUngovernedKeys(observedDataJSONKeys, fd.DataJSONRawField),
				}
			}
		}

		entries = append(entries, entry)
	}

	dict := &model.DataDictionary{
		GeneratedAt: time.Now(),
		Tables:      entries,
	}

	// Cache the result
	s.dictMu.Lock()
	s.dictTime = time.Now()
	s.cachedDict = dict
	s.dictMu.Unlock()

	return dict, nil
}

// GetBusinessOverview returns domain-grouped business data with APIs, examples, cross-refs.
func (s *CatalogService) GetBusinessOverview(ctx context.Context, refresh bool) (*model.BusinessOverview, error) {
	tables, _, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}

	domainTables := map[string][]model.TableCatalogEntry{}
	for _, t := range tables {
		domainTables[t.Domain] = append(domainTables[t.Domain], t)
	}

	domainOrder := []string{"bars", "security", "taxonomy", "financial", "strategy", "kg", "factor", "regime", "other"}
	seen := map[string]bool{}
	var domains []model.BusinessDomain

	for _, d := range domainOrder {
		ts, ok := domainTables[d]
		if !ok || len(ts) == 0 {
			continue
		}
		seen[d] = true

		var totalRows int64
		names := make([]string, 0, len(ts))
		for _, t := range ts {
			totalRows += t.RowCount
			names = append(names, t.TableName)
		}

		info, _ := domainApiRegistry[d]
		var allAPIs []model.ApiEndpointRef
		for _, t := range ts {
			if apis := s.resolveAPIs(t.TableName); len(apis) > 0 {
				allAPIs = append(allAPIs, apis...)
				break
			}
		}

		domains = append(domains, model.BusinessDomain{
			Domain:       d,
			Label:        domainDescriptions[d],
			Description:  info.Description,
			TableCount:   len(ts),
			TotalRows:    totalRows,
			Tables:       names,
			ApiEndpoints: allAPIs,
			ExampleCalls: info.ExampleCalls,
			CrossRefs:    info.CrossRefs,
		})
	}

	for d, ts := range domainTables {
		if seen[d] {
			continue
		}
		var totalRows int64
		names := make([]string, 0, len(ts))
		for _, t := range ts {
			totalRows += t.RowCount
			names = append(names, t.TableName)
		}
		domains = append(domains, model.BusinessDomain{
			Domain:     d,
			Label:      domainDescriptions[d],
			TableCount: len(ts),
			TotalRows:  totalRows,
			Tables:     names,
		})
	}

	return &model.BusinessOverview{Domains: domains}, nil
}

// Columns to skip for enum discovery — known to be high-cardinality or uninteresting.
var enumDiscoverySkipColumns = map[string]bool{
	"name": true, "symbol": true, "code": true, "title": true,
	"description": true, "source": true, "url": true, "path": true,
	"exchange": true, "market": true, "tablespace": true, "tier": true,
	"created_at": true, "updated_at": true, "deleted_at": true,
	"security_name": true, "company": true, "full_name": true,
	"index_code": true, "parent_code": true, "category_code": true,
	"status": true, "type": true,
}

// discoverEnumValues finds distinct values for a text column (up to 20 values).
// Only returns values if there are <= 20 distinct values (indicating enum-like behavior).
// Skips known high-cardinality columns to avoid unnecessary queries.
func (s *CatalogService) discoverEnumValues(ctx context.Context, schema, table, column string) []string {
	// Skip known high-cardinality / uninteresting columns
	if enumDiscoverySkipColumns[column] {
		return nil
	}
	for _, id := range []string{schema, table, column} {
		if !dao.SafeIdentifierRe.MatchString(id) {
			return nil
		}
	}
	fullTable := table
	if schema != "" && schema != "public" {
		fullTable = schema + "." + table
	}

	// Only discover if cardinality is low (enum-like)
	query := fmt.Sprintf(
		`SELECT val FROM (
		    SELECT %s AS val, COUNT(*) AS cnt
		    FROM %s
		    WHERE %s IS NOT NULL AND %s != ''
		    GROUP BY %s
		    ORDER BY cnt DESC
		    LIMIT 21
		) sub`,
		column, fullTable, column, column, column,
	)
	var vals []string
	if err := s.Dao.DB().WithContext(ctx).Raw(query).Scan(&vals).Error; err != nil {
		return nil
	}
	// If more than 20 distinct values, it's not enum-like
	if len(vals) > 20 {
		return nil
	}
	return vals
}

// GetCapabilities returns a lightweight LLM-optimized view of data availability.
// Unlike the full data-dictionary, this only includes capability/availability info —
// designed for LLM function-call tool registration (smaller payload).
func (s *CatalogService) GetCapabilities(ctx context.Context, refresh bool) (*model.DataCapabilities, error) {
	tables, _, err := s.getTables(ctx, refresh)
	if err != nil {
		return nil, err
	}

	// Group tables by domain
	domainTables := map[string][]model.TableCatalogEntry{}
	for _, t := range tables {
		domainTables[t.Domain] = append(domainTables[t.Domain], t)
	}

	domainOrder := []string{"bars", "security", "taxonomy", "financial", "strategy", "kg", "factor", "regime", "other"}
	var capabilities []model.DomainCapability

	for _, d := range domainOrder {
		ts, ok := domainTables[d]
		if !ok || len(ts) == 0 {
			continue
		}

		var tableCaps []model.TableCapability
		for _, t := range ts {
			meta := s.findMeta(t.Schema, t.TableName)
			capability := s.resolveCapability(t.TableName)
			sources := s.queryDataSources(ctx, t.Schema, t.TableName, meta.TimeColumn)

			tc := model.TableCapability{
				Schema:      t.Schema,
				TableName:   t.TableName,
				Description: t.Description,
				RowCount:    t.RowCount,
				TimeRange:   t.TimeRange,
				DataSources: sources,
				Capability:  capability,
			}

			// Get time range if not already set
			if meta.TimeColumn != "" && tc.TimeRange == nil {
				tr, trErr := s.Dao.GetTimeRange(ctx, t.Schema, t.TableName, meta.TimeColumn)
				if trErr == nil && tr != nil {
					tc.TimeRange = tr
				}
			}

			tableCaps = append(tableCaps, tc)
		}

		info, _ := domainApiRegistry[d]
		capabilities = append(capabilities, model.DomainCapability{
			Domain:      d,
			Label:       domainDescriptions[d],
			Description: info.Description,
			Tables:      tableCaps,
		})
	}

	return &model.DataCapabilities{
		GeneratedAt:  time.Now(),
		Capabilities: capabilities,
	}, nil
}

// ─── Phase 2: field dictionary aggregation ───

// tableFieldDict is the cached per-table field-dictionary view used by
// GetDataDictionary to aggregate the authoritative field contract with
// observed JSONB key stats.
type tableFieldDict struct {
	Dataset          string
	Source           string
	ContractVersion  string
	Groups           []model.DictionaryFieldGroup
	DataJSONRawField map[string]bool // raw_field names with storage_location=data_json
}

// loadFieldDictionary returns a map keyed by storage_table name. It reads
// data_dataset_dictionary (for the storage_table -> dataset mapping) and
// data_field_dictionary (for the full field list per dataset). Results are
// cached for fieldDictTTL.
//
// When FieldDictDao is nil (component not registered), returns nil without
// error so the catalog falls back to observed-only behavior.
func (s *CatalogService) loadFieldDictionary(ctx context.Context, refresh bool) (map[string]*tableFieldDict, error) {
	if s.FieldDictDao == nil {
		return nil, nil
	}
	s.fieldDictMu.RLock()
	if !refresh && s.fieldDictCache != nil && time.Since(s.fieldDictTime) < s.fieldDictTTL {
		result := s.fieldDictCache
		s.fieldDictMu.RUnlock()
		return result, nil
	}
	s.fieldDictMu.RUnlock()

	datasets, err := s.FieldDictDao.ListDatasets(ctx, "")
	if err != nil {
		return nil, fmt.Errorf("list dataset dictionary: %w", err)
	}

	cache := make(map[string]*tableFieldDict, len(datasets))
	for _, d := range datasets {
		if d.StorageTable == "" {
			continue
		}
		rows, err := s.FieldDictDao.DiscoverFields(ctx, dao.FieldQueryParams{
			Dataset:           d.Dataset,
			Source:            d.Source,
			Include:           "all",
			IncludeDeprecated: false,
		})
		if err != nil {
			logging.Warnf(ctx, "catalog: load field dictionary for %s failed: %v", d.Dataset, err)
			continue
		}

		// Group fields by data_type, preserving alphabetical order for stable
		// output. Within a group, DiscoverFields already orders rows.
		groupsMap := make(map[string][]model.FieldDiscoveryEntry)
		groupLabel := make(map[string]string)
		rawFieldSet := make(map[string]bool)
		var contractVersion string
		for _, r := range rows {
			if contractVersion == "" {
				contractVersion = r.ContractVersion
			}
			entry := model.FieldDiscoveryEntry{
				RawField:        r.RawField,
				CanonicalField:  r.CanonicalField,
				LabelZh:         r.LabelZh,
				Description:     r.Description,
				ValueType:       r.ValueType,
				Unit:            r.Unit,
				Scale:           r.Scale,
				EnumRef:         r.EnumRef,
				StorageLocation: r.StorageLocation,
				QueryName:       queryNameFor(r),
				IsMetadata:      r.IsMetadata,
				IsCore:          r.IsCore,
				CompTypeScope:   r.CompTypeScope,
				Aliases:         r.Aliases,
				SourceDoc:       r.SourceDoc,
				Deprecated:      r.Deprecated,
			}
			groupsMap[r.DataType] = append(groupsMap[r.DataType], entry)
			if r.DataTypeLabelZh != "" {
				groupLabel[r.DataType] = r.DataTypeLabelZh
			}
			if r.StorageLocation == "data_json" {
				rawFieldSet[r.RawField] = true
			}
		}

		dataTypeOrder := make([]string, 0, len(groupsMap))
		for dt := range groupsMap {
			dataTypeOrder = append(dataTypeOrder, dt)
		}
		sort.Strings(dataTypeOrder)

		groups := make([]model.DictionaryFieldGroup, 0, len(dataTypeOrder))
		for _, dt := range dataTypeOrder {
			groups = append(groups, model.DictionaryFieldGroup{
				DataType: dt,
				LabelZh:  groupLabel[dt],
				Fields:   groupsMap[dt],
			})
		}

		cache[d.StorageTable] = &tableFieldDict{
			Dataset:          d.Dataset,
			Source:           d.Source,
			ContractVersion:  contractVersion,
			Groups:           groups,
			DataJSONRawField: rawFieldSet,
		}
	}

	s.fieldDictMu.Lock()
	s.fieldDictCache = cache
	s.fieldDictTime = time.Now()
	s.fieldDictMu.Unlock()
	return cache, nil
}

// computeUngovernedKeys returns observed JSONB keys that are not registered in
// the field dictionary. These are SDK-added fields the dictionary has not
// caught up with — candidates for backfill.
func computeUngovernedKeys(observed []model.JSONBKeyRef, governed map[string]bool) []string {
	if len(governed) == 0 {
		return nil
	}
	var out []string
	for _, k := range observed {
		if !governed[k.Name] {
			out = append(out, k.Name)
		}
	}
	return out
}

// GetSecurityCoverage returns per-dataset/data_type row counts and time ranges
// for a given security_id. This is a generic discovery API — callers (e.g.,
// artemis BI layer) use it to show what data exists for a company.
func (s *CatalogService) GetSecurityCoverage(ctx context.Context, securityID uint64) (*model.CatalogSecurityCoverage, error) {
	rows, err := s.Dao.GetSecurityCoverage(ctx, securityID)
	if err != nil {
		return nil, err
	}
	coverage := dao.AggregateCoverage(rows, securityID)
	coverage.GeneratedAt = time.Now().UTC()
	return coverage, nil
}
