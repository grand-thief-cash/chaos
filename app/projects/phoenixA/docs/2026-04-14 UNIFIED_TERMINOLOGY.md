# PhoenixA 全局术语统一规范

> **生效日期**: 2026-04-14
> **适用范围**: PhoenixA, Artemis, CronJob, Cthulhu 以及所有相关项目

## 统一字段命名

以下为跨项目统一的字段命名规范。所有项目在 API、数据库、代码中必须使用统一名称。

| 统一名称 | 定义 | 旧名称（已废弃） |
|----------|------|------------------|
| `symbol` | 证券代码（通用，适配股票/指数/ETF/期货等） | `code` |
| `trade_date` | 交易日 / K 线日期 | `date` |
| `name` | 证券简称 | `company` |
| `period` | K 线周期 (daily/weekly/min5/min15/min30/min60) | `freq`, `timeframe`, `frequency` |
| `adjust` | 复权类型 (nf/qfq/hfq) | `adjustflag` |
| `asset_type` | 资产类别 (stock/index/etf/futures/fund/cb) | 隐含在表名中 |
| `market` | 市场 (zh_a/hk/us/global) | 隐含在表名中 |
| `source` | 数据来源 (baostock/akshare/mairui/tushare/csv_import) | `data_source` |
| `bars` | K 线行情数据 | `hist`, `history` |
| `taxonomy` | 分类体系 | `market_category`, `category` |
| `open/high/low/close` | OHLC 价格 | 无变化 |
| `volume` | 成交量 | 无变化 |
| `amount` | 成交额 | 无变化 |
| `preclose` | 昨收价 | 无变化 |
| `pct_chg` | 涨跌幅 (%) | `pctChg` (JSON 驼峰已统一为下划线) |

## 表命名规范

| 域 | 命名规则 | 示例 |
|----|----------|------|
| 行情标准表 | `bars_{asset_type}_{market}_{period}_{adjust}` | `bars_stock_zh_a_daily_nf` |
| 行情扩展表 | `bars_ext_{source}_{asset_type}_{market}_{period}` | `bars_ext_baostock_stock_zh_a_daily` |
| 证券注册 | `security_registry` | - |
| 分类节点 | `taxonomy_category` | - |
| 分类映射 | `taxonomy_security_map` | - |
| 策略结果 | `strategy_run_summary` / `strategy_run_artifact` | 保持不变 |

## API 路由规范

| 域 | v2 路由 | 旧 v1 路由（兼容） |
|----|---------|-------------------|
| 证券 | `/api/v2/securities` | `/api/v1/stock/list` |
| 行情 | `/api/v2/bars/{asset_type}/{market}` | `/api/v1/stock/hist` |
| 分类 | `/api/v2/taxonomy/{source}` | `/api/v1/market_category/{source}` |
| 策略 | `/api/v1/strategy/run/...` | 不变 |

## JSON 字段风格

- 所有 JSON 字段统一使用 **snake_case**（下划线命名）
- 示例: `trade_date`, `asset_type`, `pct_chg`, `pe_ttm`
- 废弃: `pctChg`, `peTTM`, `pcfNcfTTM` 等驼峰命名

## Artemis CacheEngine 适配说明

Artemis CacheEngine 内部使用 `date` 列做分区和去重。
从 PhoenixA v2 API 获取数据后，在 Artemis MarketDataService 层统一 rename:
- `trade_date` → `date` (仅 CacheEngine 内部)
- `symbol` → `code` (仅需要时兼容)

CacheEngine 内部逻辑不变，只在数据进出时做字段名映射。

