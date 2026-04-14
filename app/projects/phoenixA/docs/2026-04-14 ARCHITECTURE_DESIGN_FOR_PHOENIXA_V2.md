# PhoenixA 数据中台架构重设计

> **文档状态**：Draft v1.0 · 2026-04-14
> **目标读者**：PhoenixA & Artemis 开发者
> **核心命题**：从金融量化业务视角重新梳理数据中台的数据模型、领域划分和扩展策略

---

## 0. 执行摘要

PhoenixA 当前面临三个结构性痛点：

| # | 痛点 | 表现 |
|---|------|------|
| 1 | **资产类型绑死** | 表名/Model/DAO/Controller 全部硬编码 `stock_zh_a_*`，无法自然扩展到 Index、ETF、期货、基金 |
| 2 | **数据源列不统一** | baostock 带 PE/PB/Turn 等滚动指标，akshare/mairui 仅有 OHLCV；当前 `StockZhAHistDaily` 结构体只适配 baostock 的 15 列 |
| 3 | **分类体系与数据源强耦合** | `CategoryMairui`、`CategorySWHY` 各自独立表和独立 DAO/Service/Controller 逻辑，每新增一个分类数据源就要全栈复制 |

本文档从**金融业务本质**出发，提出一套 **"资产类型 × 行情频率 × 数据域"** 的三维领域模型，并给出从当前代码到目标架构的**渐进式迁移路径**，不做一刀切重写。

---

## 1. 金融业务领域建模

### 1.1 金融数据的三个核心维度

在量化系统中，所有数据可以沿三个正交维度进行组织：

```
                    ┌─────────────────────────────────────────┐
                    │           金融数据三维空间               │
                    │                                         │
                    │   维度 1: Asset Class (资产类别)         │
                    │     stock · index · etf · fund ·        │
                    │     futures · bond · crypto · ...       │
                    │                                         │
                    │   维度 2: Data Domain (数据域)           │
                    │     bars (行情) · reference (基础)  ·    │
                    │     category (分类) · fundamental (财务)│
                    │     analytics (回测结果) · ...           │
                    │                                         │
                    │   维度 3: Frequency / Granularity        │
                    │     tick · 1min · 5min · daily ·        │
                    │     weekly · monthly · snapshot ·        │
                    │     quarterly · annual                   │
                    │                                         │
                    └─────────────────────────────────────────┘
```

**关键洞察**：当前代码把三个维度混杂到命名和结构里（`stock_zh_a_hist_daily_nf`），导致每新增一个资产或频率，都要复制 Model/DAO/Service/Controller 全栈。

### 1.2 六大数据域 (Data Domains)

从量化系统的全生命周期来看，PhoenixA 最终需要覆盖以下数据域：

| 数据域 | 英文代号 | 典型数据 | 当前状态 |
|--------|----------|----------|----------|
| **行情数据** | `bars` | OHLCV K 线、Tick、分笔 | ✅ 已有，但列定义与资产类型耦合 |
| **基础信息** | `reference` | 证券列表、代码映射、上市/退市 | ✅ 已有 `stock_zh_a_list` |
| **分类体系** | `taxonomy` | 行业分类（申万/中信/GICS）、概念板块、地区 | ✅ 已有，但每个来源一套 |
| **财务数据** | `fundamental` | 财报、PE/PB/ROE、分红、增减持 | ❌ 未实现 |
| **策略产出** | `analytics` | 回测结果、交易记录、权益曲线 | ✅ 已有 `strategy_run_*` |
| **元数据** | `meta` | 数据源注册表、数据新鲜度、质量报告 | ❌ 部分有 (last_update) |

### 1.3 资产类别全景

| 资产类别 | 代号 | 市场 | 代码格式 | 特殊列需求 |
|----------|------|------|---------|-----------|
| A 股 | `stock` | `zh_a` | 6 位纯数字 | PE/PB/Turn/换手率 |
| 指数 | `index` | `zh_a` | 6 位 (如 000001/399001) | 无复权概念 |
| ETF | `etf` | `zh_a` | 6 位 (如 510050) | 净值、折溢价率 |
| 可转债 | `cb` | `zh_a` | 6 位 | 转股价、到期收益率 |
| 期货 | `futures` | `zh` | 不定长 (如 IF2403) | 持仓量、结算价 |
| 基金 | `fund` | `zh` | 6 位 | 净值、累计净值 |
| 港股 | `stock` | `hk` | 5 位 (如 00700) | 与 A 股列相似 |
| 美股 | `stock` | `us` | 不定长 (如 AAPL) | 与 A 股列相似 |
| 数字货币 | `crypto` | `global` | 不定长 (如 BTC-USDT) | 特有字段 |

---

## 2. 当前架构问题深度剖析

### 2.1 问题一：行情表 "一列定义走天下"

**现状**：`StockZhAHistDaily` 包含 15 列（date, code, open, high, low, close, preclose, volume, amount, turn, pct_chg, pe_ttm, ps_ttm, pcf_ncf_ttm, pb_mrq），这些列来自 baostock。

**问题**：
- 来自 akshare 或 mairui 的日线数据只有 OHLCV，写入时 PE/PB 等字段全为 0，语义含糊（0 是"没有"还是"真的为零"？）
- 如果未来要接入 tushare（带 adj_factor、total_mv、circ_mv），又要加列，表结构不断膨胀
- Index 根本不需要 turn/pe_ttm 等字段，但被迫使用同一结构
- Artemis 的 `DataProviderSpec.required_fields` 只声明了 8 列，但 PhoenixA 强制绑定 15 列的结构

**根因**：把 "核心行情列" 和 "数据源专属列" 混在了同一张宽表。

### 2.2 问题二：分类数据源每来一个全栈复制

**现状**：
- `CategoryMairui` → `MarketCategoryMairui` DAO → `MarketCategoryMairui` Service → `MarketCategoryController` 里的 if-else 分支
- `CategorySWHY` → `MarketCategorySWHY` DAO → `MarketCategorySWHY` Service → 同上 controller

**问题**：
- 如果接入中信行业分类、概念板块、地区板块，每个来源都要新建 Model + DAO + Service + 在 Controller 加 if-else
- 路由 `/{source}` 的设计合理，但底层实现是硬编码分发
- `category_stock_map` 只有 `category_code + stock_code` 两列，但 code 来自不同 source 的 namespace，会冲突

### 2.3 问题三：命名绑定地域和资产

**现状**：
- 表名 `stock_zh_a_hist_daily_nf`、Model 名 `StockZhAHistDaily`、DAO 名 `StockZhAHistDaily`
- 路由 `/api/v1/stock/hist/...`、`/api/v1/stock/list/...`

**问题**：
- 当需要支持 Index 时，是否要创建 `index_zh_a_hist_daily_nf`？然后 ETF 再来一套？
- Artemis 的 `PhoenixAClient` 也被迫为每个资产类型写独立方法 (`get_stock_zh_a_hist_bars` / `get_index_zh_a_hist_bars`)

---

## 3. 目标架构设计

### 3.1 设计原则

| 原则 | 说明 |
|------|------|
| **核心列标准化** | OHLCV 是跨资产类型、跨数据源的最大公约数，必须在所有行情表中保持一致 |
| **扩展列外置** | 数据源特有的列（PE/PB/Turn/adj_factor 等）通过扩展机制附加，而非堆入主表 |
| **资产类型路由化** | API 层统一为 `/api/v1/market/{asset_type}/...`，内部按 asset_type 路由到对应处理逻辑 |
| **分类体系统一** | 所有分类数据源共享统一的 `taxonomy_category` + `taxonomy_mapping` 表，通过 `source` 字段区分 |
| **数据源自描述** | 引入 `data_source_registry` 表，记录每个数据源能提供哪些资产类型、哪些列、哪些频率 |
| **渐进式迁移** | 不做大爆炸重写，通过新旧路由并存 + 数据双写过渡 |

### 3.2 行情数据 (Bars) 重设计

#### 3.2.1 核心思路："标准列 + 扩展列" 分层

```
┌─────────────────────────────────────────────────────────────┐
│                    行情数据分层模型                          │
│                                                             │
│  Layer 1: Standard Bars (标准行情)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ asset_type | market | symbol | date | freq | adjust │    │
│  │ open | high | low | close | volume | amount         │    │
│  │ [preclose | pct_chg]  ← 可选标准列                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                         ↕ 1:1 关联                          │
│  Layer 2: Extended Attributes (扩展属性)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ symbol | date | source | attr_key | attr_value      │    │
│  │ 或: 每个数据源一张附属宽表                           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2.2 方案对比

| 方案 | 核心行情表 | 扩展列处理 | 优点 | 缺点 |
|------|-----------|-----------|------|------|
| **A: 宽表 + NULL** | 一张大宽表包含所有可能列 | 无数据时 NULL | 简单直接 | 列无限膨胀，NULL 语义含糊 |
| **B: EAV 扩展** | 标准 OHLCV 表 | `attr_key/attr_value` 长表 | 极度灵活 | 查询性能差，类型丢失 |
| **C: 标准表 + 源附属表** (推荐) | 标准 OHLCV 主表 | 每个数据源一张附属表 | 类型安全，JOIN 可选 | 表数略多 |
| **D: JSON 扩展列** | 标准 OHLCV + extras JSON | `extras` 列存 JSON | 折中灵活 | MySQL JSON 查询效率一般 |

**推荐方案 C**：标准表 + 源附属表

理由：
1. Artemis 回测引擎 95% 场景只需要 OHLCV，标准表直接满足
2. PE/PB/Turn 等指标只在"因子计算"或"特定策略"时需要，通过 LEFT JOIN 按需获取
3. 类型安全（decimal/bigint），不丢失精度
4. 后续迁移到 ClickHouse 时，宽表 + 附属表模式同样适用

#### 3.2.3 推荐表结构

**标准行情表** — 按 `{asset_type}_{market}` 分组建表，每个频率+复权类型仍独立物理表（保持分区策略）：

```sql
-- 命名规则: bars_{asset_type}_{market}_{freq}_{adjust}
-- 例: bars_stock_zh_a_daily_nf, bars_index_zh_a_daily_nf, bars_etf_zh_a_daily_nf

CREATE TABLE IF NOT EXISTS bars_stock_zh_a_daily_nf (
    symbol      VARCHAR(32)    NOT NULL COMMENT '证券代码',
    trade_date  DATE           NOT NULL COMMENT '交易日',
    open        DECIMAL(20,4)  NULL     COMMENT '开盘价',
    high        DECIMAL(20,4)  NULL     COMMENT '最高价',
    low         DECIMAL(20,4)  NULL     COMMENT '最低价',
    close       DECIMAL(20,4)  NULL     COMMENT '收盘价',
    volume      BIGINT         NULL     COMMENT '成交量',
    amount      BIGINT         NULL     COMMENT '成交额',
    preclose    DECIMAL(20,4)  NULL     COMMENT '昨收价',
    pct_chg     DECIMAL(10,4)  NULL     COMMENT '涨跌幅(%)',
    PRIMARY KEY (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  PARTITION BY RANGE (YEAR(trade_date)) ( ... );
```

> **对比现有表名**：`stock_zh_a_hist_daily_nf` → `bars_stock_zh_a_daily_nf`
> - `hist` 去掉：语义冗余（行情数据本身就是历史数据）
> - `code` → `symbol`：统一术语，适配不同资产类型（股票代码、指数代码、期货合约代码）
> - `date` → `trade_date`：更精确的语义

**数据源附属表** — 存储特定数据源提供的额外指标：

```sql
-- 命名规则: bars_ext_{source}_{asset_type}_{market}_{freq}
-- 例: bars_ext_baostock_stock_zh_a_daily

CREATE TABLE IF NOT EXISTS bars_ext_baostock_stock_zh_a_daily (
    symbol      VARCHAR(32)    NOT NULL,
    trade_date  DATE           NOT NULL,
    turn        DECIMAL(10,4)  NULL     COMMENT '换手率(%)',
    pe_ttm      DECIMAL(20,4)  NULL     COMMENT '滚动市盈率',
    ps_ttm      DECIMAL(20,4)  NULL     COMMENT '滚动市销率',
    pb_mrq      DECIMAL(20,4)  NULL     COMMENT '市净率(MRQ)',
    pcf_ncf_ttm DECIMAL(20,4)  NULL     COMMENT '滚动市现率',
    PRIMARY KEY (symbol, trade_date),
    CONSTRAINT fk_ext_baostock_daily
        FOREIGN KEY (symbol, trade_date)
        REFERENCES bars_stock_zh_a_daily_nf (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 3.2.4 表名路由规则 (Table Name Resolution)

DAO 层不再硬编码表名，而是通过统一的解析函数生成：

```go
// 标准行情表名
func BarsTableName(assetType, market, freq, adjust string) string {
    return fmt.Sprintf("bars_%s_%s_%s_%s", assetType, market, freq, adjust)
}
// → "bars_stock_zh_a_daily_nf"

// 数据源附属表名
func BarsExtTableName(source, assetType, market, freq string) string {
    return fmt.Sprintf("bars_ext_%s_%s_%s_%s", source, assetType, market, freq)
}
// → "bars_ext_baostock_stock_zh_a_daily"
```

### 3.3 证券基础信息 (Reference) 重设计

#### 3.3.1 统一证券注册表

当前 `stock_zh_a_list` 只服务于 A 股。扩展后的设计：

```sql
-- 统一证券注册表: 所有可交易品种的基础信息
CREATE TABLE IF NOT EXISTS security_registry (
    symbol       VARCHAR(32)   NOT NULL COMMENT '证券代码',
    asset_type   VARCHAR(16)   NOT NULL COMMENT 'stock/index/etf/futures/fund/cb',
    market       VARCHAR(16)   NOT NULL COMMENT 'zh_a/hk/us/global',
    exchange     VARCHAR(8)    NOT NULL COMMENT 'SH/SZ/BJ/HKEX/NYSE/...',
    name         VARCHAR(128)  NOT NULL DEFAULT '' COMMENT '证券简称',
    full_name    VARCHAR(256)  NULL     COMMENT '证券全称',
    status       VARCHAR(16)   NOT NULL DEFAULT 'active' COMMENT 'active/delisted/suspended',
    list_date    DATE          NULL     COMMENT '上市日期',
    delist_date  DATE          NULL     COMMENT '退市日期',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, asset_type, market),
    KEY idx_asset_market (asset_type, market),
    KEY idx_exchange (exchange),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

> **向后兼容**：现有 `stock_zh_a_list` 可作为视图或别名保留，数据迁移脚本将 `code` → `symbol`, `company` → `name`, 并补充 `asset_type='stock'`, `market='zh_a'`。

### 3.4 分类体系 (Taxonomy) 重设计

#### 3.4.1 核心问题

当前每个分类来源一张表（`mkt_category_mairui`、`mkt_category_swhy`），列完全不同，导致：
- Controller 里大量 if-else 按 source 分发
- `category_stock_map` 里的 `category_code` 跨 source 可能冲突

#### 3.4.2 统一分类模型

```sql
-- 统一分类节点表
CREATE TABLE IF NOT EXISTS taxonomy_category (
    id           BIGINT UNSIGNED AUTO_INCREMENT,
    source       VARCHAR(32)   NOT NULL COMMENT '分类来源: mairui/swhy/citic/gics/concept/region',
    code         VARCHAR(64)   NOT NULL COMMENT '分类代码（source 内唯一）',
    name         VARCHAR(255)  NOT NULL COMMENT '分类名称',
    parent_code  VARCHAR(64)   NULL     COMMENT '父分类代码',
    level        TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '层级',
    is_leaf      TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否叶子节点',
    attrs_json   JSON          NULL     COMMENT '来源特有属性 (如 mairui 的 type1/type2)',
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_source_code (source, code),
    KEY idx_parent (source, parent_code),
    KEY idx_level (source, level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 统一分类-证券关系表
CREATE TABLE IF NOT EXISTS taxonomy_security_map (
    source        VARCHAR(32) NOT NULL COMMENT '分类来源',
    category_code VARCHAR(64) NOT NULL COMMENT '分类代码',
    symbol        VARCHAR(32) NOT NULL COMMENT '证券代码',
    asset_type    VARCHAR(16) NOT NULL DEFAULT 'stock' COMMENT '资产类型',
    market        VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场',
    UNIQUE KEY uk_source_cat_sec (source, category_code, symbol, asset_type, market),
    KEY idx_symbol (symbol, asset_type, market),
    KEY idx_category (source, category_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**好处**：
- 新增分类来源只需写入不同 `source` 值，无需新建表
- `attrs_json` 存放 source 独有属性（如 mairui 的 type1/type2, swhy 的 index_code）
- `taxonomy_security_map` 通过 `source` 隔离不同来源的 namespace，不会冲突
- Controller 无需 if-else，统一逻辑按 source 过滤即可

### 3.5 财务数据 (Fundamental) 设计预留

当前阶段不实现，但预定义好位置：

```
数据域: fundamental
表命名: fundamental_{data_type}_{market}
例:
  fundamental_income_zh_a        -- A 股利润表
  fundamental_balance_zh_a       -- A 股资产负债表
  fundamental_cashflow_zh_a      -- A 股现金流量表
  fundamental_valuation_zh_a     -- A 股估值指标 (PE/PB/PS/PCF)
  fundamental_dividend_zh_a      -- A 股分红送配
```

> 注：将行情表中的 PE/PB 等列抽出到这里是合理的 —— 它们本质上是"估值指标"，属于 fundamental 域。但因为 baostock 在日线数据中包含了这些列，所以在 PhoenixA 中也可以选择同时存放在 `bars_ext_baostock_*` 附属表中（数据冗余但查询便捷）。长期来看，独立的 `fundamental_valuation` 表是更合理的归宿。

### 3.6 策略产出 (Analytics) — 保持现有设计

`strategy_run_summary` 和 `strategy_run_artifact` 的设计已经很好，表名和字段都具有业务通用性，**不需要重构**。但建议：

1. `symbol` 列宽度从 `VARCHAR(32)` 保持不变（已足够适配各类资产代码）
2. 未来可在 `strategy_run_summary` 中增加 `asset_type` 和 `market` 列，标识回测的资产类型
3. 路由 `/api/v1/strategy/run/...` 保持不变

### 3.7 数据源注册表 (Meta)

```sql
-- 数据源注册表: 自描述每个数据源能提供什么
CREATE TABLE IF NOT EXISTS data_source_registry (
    source_code   VARCHAR(32)  NOT NULL COMMENT '数据源代码: baostock/akshare/tushare/mairui/csv_import',
    display_name  VARCHAR(128) NOT NULL COMMENT '数据源显示名',
    asset_types   JSON         NOT NULL COMMENT '支持的资产类型 ["stock","index"]',
    markets       JSON         NOT NULL COMMENT '支持的市场 ["zh_a"]',
    frequencies   JSON         NOT NULL COMMENT '支持的频率 ["daily","weekly","5min"]',
    bar_fields    JSON         NOT NULL COMMENT '提供的行情列 ["open","high","low","close","volume","amount","turn","pe_ttm"]',
    category_support TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否提供分类数据',
    status        VARCHAR(16)  NOT NULL DEFAULT 'active',
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**用途**：
- Artemis 在下载任务启动前可查询此表，了解当前数据源支持哪些列
- PhoenixA 在写入时可校验传入的字段是否在该数据源的 `bar_fields` 声明范围内
- 前端 Cthulhu 可用此表动态渲染可用的数据源/频率/资产类型选项

---

## 4. API 路由重设计

### 4.1 路由设计原则

- **资源导向**：URL 反映数据域和资产类型
- **维度参数化**：`asset_type`, `market`, `freq`, `adjust` 通过 URL 路径或查询参数传递
- **保持向后兼容**：旧路由与新路由并存过渡

### 4.2 新路由清单

```
# ====== 证券基础信息 (Reference) ======
GET    /api/v2/securities                           # 统一证券列表查询
POST   /api/v2/securities/upsert                    # 批量写入/更新证券信息
GET    /api/v2/securities/{symbol}                   # 单个证券详情
  查询参数: asset_type, market, exchange, status, limit, offset

# ====== 行情数据 (Bars) ======
GET    /api/v2/bars/{asset_type}/{market}            # 查询行情数据
POST   /api/v2/bars/{asset_type}/{market}/upsert     # 写入行情数据
GET    /api/v2/bars/{asset_type}/{market}/last_update # 查询最新更新日期
  路径参数: asset_type (stock/index/etf/...), market (zh_a/hk/us/...)
  查询参数: symbol, start_date, end_date, freq, adjust, fields, limit, offset, source

# ====== 行情扩展数据 ======
GET    /api/v2/bars/{asset_type}/{market}/ext/{source}  # 查询特定数据源的扩展列
POST   /api/v2/bars/{asset_type}/{market}/ext/{source}/upsert

# ====== 分类体系 (Taxonomy) ======
GET    /api/v2/taxonomy/{source}/categories          # 按来源查分类树
POST   /api/v2/taxonomy/{source}/categories/upsert   # 批量写入分类
GET    /api/v2/taxonomy/{source}/mapping              # 分类-证券映射
POST   /api/v2/taxonomy/{source}/mapping/upsert       # 批量写入映射
POST   /api/v2/taxonomy/{source}/mapping/replace      # 替换映射
GET    /api/v2/taxonomy/by_security/{symbol}          # 查询某证券所属分类

# ====== 策略结果 (Analytics) — 保持现有 ======
GET    /api/v1/strategy/run/list
POST   /api/v1/strategy/run/summary/upsert
POST   /api/v1/strategy/run/artifact/upsert
GET    /api/v1/strategy/run/{run_id}
GET    /api/v1/strategy/run/{run_id}/artifacts

# ====== 数据源元信息 ======
GET    /api/v2/meta/sources                          # 查询所有数据源及其能力
GET    /api/v2/meta/sources/{source_code}             # 查询单个数据源

# ====== 旧路由兼容 (标记 deprecated, 内部代理到新逻辑) ======
GET    /api/v1/stock/list/...        → 代理到 /api/v2/securities
GET    /api/v1/stock/hist/...        → 代理到 /api/v2/bars/stock/zh_a
POST   /api/v1/stock/hist/upsert     → 代理到 /api/v2/bars/stock/zh_a/upsert
GET    /api/v1/market_category/...   → 代理到 /api/v2/taxonomy/...
```

### 4.3 行情 API 统一请求/响应格式

**写入请求** (POST `/api/v2/bars/{asset_type}/{market}/upsert`)：

```json
{
  "meta": {
    "source": "baostock",
    "freq": "daily",
    "adjust": "nf",
    "symbol": "000001"
  },
  "bars": [
    {
      "trade_date": "2026-04-11",
      "open": 10.50,
      "high": 10.80,
      "low": 10.30,
      "close": 10.65,
      "volume": 12345678,
      "amount": 130000000
    }
  ],
  "ext": [
    {
      "trade_date": "2026-04-11",
      "turn": 1.23,
      "pe_ttm": 15.67,
      "pb_mrq": 2.34
    }
  ]
}
```

- `bars` 只包含标准列，写入 `bars_stock_zh_a_daily_nf`
- `ext` 可选，包含该数据源的扩展列，写入 `bars_ext_baostock_stock_zh_a_daily`
- 向后兼容：如果 `ext` 为空或不传，只写标准表

**读取响应** (GET `/api/v2/bars/stock/zh_a?symbol=000001&start_date=2026-01-01&end_date=2026-04-11&freq=daily&adjust=nf`)：

```json
{
  "symbol": "000001",
  "asset_type": "stock",
  "market": "zh_a",
  "freq": "daily",
  "adjust": "nf",
  "total": 67,
  "data": [
    {
      "trade_date": "2026-01-02",
      "open": 10.50,
      "high": 10.80,
      "low": 10.30,
      "close": 10.65,
      "volume": 12345678,
      "amount": 130000000,
      "preclose": 10.45,
      "pct_chg": 1.91
    }
  ]
}
```

- 默认只返回标准列
- 如果请求带 `fields=open,high,low,close,volume,pe_ttm,pb_mrq`，则 JOIN 扩展表返回额外列
- 如果请求带 `source=baostock`，限定从该数据源的扩展表获取

---

## 5. Go 代码架构重设计

### 5.1 包结构调整

```
internal/
├── consts/
│   ├── asset_type.go       # stock, index, etf, ...
│   ├── market.go           # zh_a, hk, us, ...
│   ├── frequency.go        # daily, weekly, min5, ...
│   ├── data_source.go      # baostock, akshare, mairui, ...
│   ├── data_domain.go      # bars, reference, taxonomy, analytics, meta
│   └── components.go       # 组件注册名
│
├── model/
│   ├── bars.go             # StandardBar 通用结构 + BarsExtRow
│   ├── security.go         # SecurityRegistry
│   ├── taxonomy.go         # TaxonomyCategory, TaxonomySecurityMap
│   ├── strategy_run.go     # 保持不变
│   └── query.go            # BarsQuery, TaxonomyQuery 等通用查询参数
│
├── dao/
│   ├── bars_dao.go         # 通用行情 DAO（基于 asset_type/market/freq/adjust 动态表名）
│   ├── bars_ext_dao.go     # 扩展列 DAO
│   ├── security_dao.go     # 证券注册 DAO
│   ├── taxonomy_dao.go     # 统一分类 DAO（取代 mairui/swhy 两个 DAO）
│   ├── strategy_run.go     # 保持不变
│   └── table_resolver.go   # 表名解析工具
│
├── service/
│   ├── bars_service.go     # 统一行情服务
│   ├── security_service.go # 证券服务
│   ├── taxonomy_service.go # 统一分类服务
│   ├── strategy_run.go     # 保持不变
│   └── meta_service.go     # 数据源元信息服务
│
├── controller/
│   ├── bars_controller.go  # 统一行情 Controller
│   ├── security_controller.go
│   ├── taxonomy_controller.go
│   ├── strategy_run_controller.go  # 保持不变
│   ├── meta_controller.go
│   └── legacy_compat.go    # 旧路由兼容适配
│
├── api/
│   ├── router_v2.go        # v2 路由注册
│   └── router_all.go       # 旧路由 (标记 deprecated，内部 proxy)
│
└── registry_ext/
    ├── dao.go
    ├── service.go
    └── controller.go
```

### 5.2 通用行情 Model

```go
// model/bars.go

// StandardBar 是所有资产类型、所有数据源的行情最大公约数
type StandardBar struct {
    Symbol    string  `gorm:"primaryKey;type:varchar(32)" json:"symbol"`
    TradeDate string  `gorm:"primaryKey;type:date"        json:"trade_date"`
    Open      float64 `gorm:"type:decimal(20,4)"          json:"open"`
    High      float64 `gorm:"type:decimal(20,4)"          json:"high"`
    Low       float64 `gorm:"type:decimal(20,4)"          json:"low"`
    Close     float64 `gorm:"type:decimal(20,4)"          json:"close"`
    Volume    int64   `                                    json:"volume"`
    Amount    int64   `gorm:"type:bigint"                  json:"amount"`
    Preclose  float64 `gorm:"type:decimal(20,4)"          json:"preclose,omitempty"`
    PctChg    float64 `gorm:"column:pct_chg;type:decimal(10,4)" json:"pct_chg,omitempty"`
}

// BarsQuery 统一的行情查询参数
type BarsQuery struct {
    AssetType string   `json:"asset_type"` // stock, index, etf, ...
    Market    string   `json:"market"`     // zh_a, hk, us, ...
    Freq      string   `json:"freq"`       // daily, weekly, min5, ...
    Adjust    string   `json:"adjust"`     // nf, qfq, hfq
    Symbol    string   `json:"symbol"`
    Symbols   []string `json:"symbols,omitempty"`
    StartDate string   `json:"start_date"`
    EndDate   string   `json:"end_date"`
    Fields    []string `json:"fields,omitempty"`
    Source    string   `json:"source,omitempty"` // 指定扩展列数据源
    Limit     int      `json:"limit,omitempty"`
    Offset    int      `json:"offset,omitempty"`
}

// BarsUpsertRequest 统一的行情写入请求
type BarsUpsertRequest struct {
    Meta BarsUpsertMeta         `json:"meta"`
    Bars []map[string]any       `json:"bars"` // 标准列
    Ext  []map[string]any       `json:"ext,omitempty"` // 扩展列
}

type BarsUpsertMeta struct {
    Source    string `json:"source"`
    Freq      string `json:"freq"`
    Adjust    string `json:"adjust"`
    Symbol    string `json:"symbol,omitempty"` // 可选: 如果 bars 中已包含 symbol
}
```

### 5.3 通用行情 DAO

```go
// dao/bars_dao.go

type BarsDao struct {
    *core.BaseComponent
    GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
    db       *gorm.DB
    dsName   string
}

// 动态表名解析
func (d *BarsDao) tableName(assetType, market, freq, adjust string) string {
    return fmt.Sprintf("bars_%s_%s_%s_%s", assetType, market, freq, adjust)
}

func (d *BarsDao) extTableName(source, assetType, market, freq string) string {
    return fmt.Sprintf("bars_ext_%s_%s_%s_%s", source, assetType, market, freq)
}

// 通用 BatchUpsert: 写入标准列
func (d *BarsDao) BatchUpsert(ctx context.Context, q *model.BarsQuery, bars []*model.StandardBar) error {
    table := d.tableName(q.AssetType, q.Market, q.Freq, q.Adjust)
    return d.db.Table(table).WithContext(ctx).
        Clauses(clause.OnConflict{
            Columns:   []clause.Column{{Name: "symbol"}, {Name: "trade_date"}},
            DoUpdates: clause.AssignmentColumns([]string{
                "open", "high", "low", "close", "volume", "amount", "preclose", "pct_chg",
            }),
        }).CreateInBatches(bars, 1000).Error
}

// 通用 Query: 支持 fields 选择
func (d *BarsDao) Query(ctx context.Context, q *model.BarsQuery) ([]map[string]any, error) {
    table := d.tableName(q.AssetType, q.Market, q.Freq, q.Adjust)
    db := d.db.Table(table).WithContext(ctx).
        Where("symbol = ? AND trade_date >= ? AND trade_date <= ?", q.Symbol, q.StartDate, q.EndDate).
        Order("trade_date ASC")
    // ... fields selection, limit, offset, optional JOIN with ext table
}
```

### 5.4 通用分类 DAO

```go
// dao/taxonomy_dao.go

type TaxonomyDao struct {
    *core.BaseComponent
    GormComp *mg.GormComponent `infra:"dep:mysql_gorm"`
    db       *gorm.DB
}

// 通用 BatchUpsert: 按 source + code upsert
func (d *TaxonomyDao) BatchUpsertCategories(ctx context.Context, source string, categories []*model.TaxonomyCategory) error {
    return d.db.Table("taxonomy_category").WithContext(ctx).
        Clauses(clause.OnConflict{
            Columns:   []clause.Column{{Name: "source"}, {Name: "code"}},
            DoUpdates: clause.AssignmentColumns([]string{
                "name", "parent_code", "level", "is_leaf", "attrs_json", "updated_at",
            }),
        }).CreateInBatches(categories, 500).Error
}

// 无需 if-else 按 source 分发！
```

---

## 6. Artemis 侧的适配变更

### 6.1 PhoenixAClient 简化

重构后 Artemis 不再需要为每个资产类型写独立方法：

```python
# 当前: get_stock_zh_a_hist_bars() / get_index_zh_a_hist_bars() / ...
# 目标: 统一方法

class PhoenixAClient:
    def get_bars(
        self, *,
        asset_type: str,   # "stock", "index", "etf"
        market: str,       # "zh_a", "hk", "us"
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = "daily",
        adjust: str = "nf",
        fields: list[str] | None = None,
        source: str | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        path = f"/api/v2/bars/{asset_type}/{market}"
        params = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "freq": freq,
            "adjust": adjust,
            "limit": limit,
        }
        if fields:
            params["fields"] = ",".join(fields)
        if source:
            params["source"] = source
        # ... paging logic
```

### 6.2 DataProviderSpec 自然对齐

Artemis 的 `DataProviderSpec` 和 PhoenixA 的 `data_source_registry` 可以互相印证：

```python
# Artemis 侧注册
_phoenixa_hist_daily = DataProviderSpec(
    code="phoenixa_bars",      # 不再绑定 hist_daily
    supported_modes=("historical",),
    supported_timeframes=("daily", "weekly", "5min", "15min", "30min", "60min"),
    default_adjust="nf",
    required_fields=("trade_date", "symbol", "open", "high", "low", "close", "volume", "amount"),
)
```

### 6.3 Workbench Provider 简化

```python
# 当前: PhoenixStockZhAProvider, PhoenixIndexZhAProvider, ... (每个资产类型一个)
# 目标: 一个通用 Provider

class PhoenixBarsProvider(MarketDataProvider):
    name = "phoenix_bars"

    def supports(self, *, asset_type: str, market: str) -> bool:
        # 未来可查询 PhoenixA 的 data_source_registry 来动态判断
        return True

    def fetch_bars(self, *, client, query: MarketDataQuery) -> list[dict]:
        return client.get_bars(
            asset_type=query.asset_type,
            market=query.market,
            symbol=query.symbol,
            start_date=query.start_date,
            end_date=query.end_date,
            freq=query.period,
            adjust=query.adjust,
        )
```

---

## 7. 数据迁移策略

### 7.1 原则

- **不停服迁移**：新旧路由并存
- **数据双写**：过渡期旧路由内部 proxy 到新逻辑
- **回滚能力**：旧表保留至少一个 release cycle

### 7.2 迁移步骤

```
Phase M1: 基础设施准备
├── 创建新表 (bars_stock_zh_a_daily_nf, security_registry, taxonomy_category, ...)
├── 写数据迁移脚本: stock_zh_a_hist_daily_nf → bars_stock_zh_a_daily_nf
├── 写数据迁移脚本: stock_zh_a_list → security_registry
├── 写数据迁移脚本: mkt_category_mairui + mkt_category_swhy → taxonomy_category
└── 写数据迁移脚本: category_stock_map → taxonomy_security_map

Phase M2: 新代码上线（双写）
├── v2 路由上线，新 DAO/Service/Controller 投产
├── v1 路由内部 proxy 到 v2 逻辑 (旧接口行为不变)
├── Artemis 暂不改动，仍调 v1 路由
└── 验证新表数据正确性

Phase M3: Artemis 切换
├── Artemis PhoenixAClient 切换到 v2 接口
├── CacheEngine 适配新字段名 (date→trade_date, code→symbol)
├── DataProviderSpec required_fields 更新
└── 全链路联调验证

Phase M4: 清理
├── 标记 v1 路由为 deprecated (日志 warning)
├── 待确认无调用后移除 v1 路由代码
└── 归档旧表 (rename 为 _archive 后缀)
```

### 7.3 字段映射表

| 旧字段 | 新字段 | 说明 |
|--------|--------|------|
| `code` (CHAR 6) | `symbol` (VARCHAR 32) | 适配更多资产类型 |
| `date` | `trade_date` | 更精确语义 |
| `company` | `name` | 统一 |
| `turn/pe_ttm/ps_ttm/pcf_ncf_ttm/pb_mrq` | → `bars_ext_baostock_*` | 移入扩展表 |
| `CategoryMairui.type1/type2` | → `taxonomy_category.attrs_json` | 移入 JSON |
| `CategorySWHY.index_code/industry_code` | → `taxonomy_category.code + attrs_json` | 统一 |

---

## 8. 实施路线图

```
┌────────────────────────────────────────────────────────────────────────┐
│                          实施路线图                                    │
├──────────┬─────────────────────────────────────────────────────────────┤
│ Phase 1  │ 当前已完成                                                 │
│ (Done)   │ ✅ stock OHLCV CRUD (baostock 日线)                       │
│          │ ✅ 分类数据 (mairui + swhy)                                │
│          │ ✅ 回测结果持久化 (strategy_run_*)                          │
├──────────┼─────────────────────────────────────────────────────────────┤
│ Phase 2  │ 核心重构: 行情 + 证券注册                                  │
│ (Next)   │ 🔲 新建 security_registry 表 + DAO/Service/Controller     │
│          │ 🔲 新建 bars_stock_zh_a_daily_nf 标准行情表                │
│          │ 🔲 新建 bars_ext_baostock_stock_zh_a_daily 扩展表          │
│          │ 🔲 实现通用 BarsDao + BarsService + BarsController        │
│          │ 🔲 v2 路由上线, v1 路由 proxy                             │
│          │ 🔲 数据迁移脚本                                           │
├──────────┼─────────────────────────────────────────────────────────────┤
│ Phase 3  │ 分类体系统一                                              │
│          │ 🔲 新建 taxonomy_category + taxonomy_security_map         │
│          │ 🔲 统一 TaxonomyDao/Service/Controller                    │
│          │ 🔲 迁移 mairui/swhy 数据                                  │
│          │ 🔲 Artemis 分类相关任务适配                                │
├──────────┼─────────────────────────────────────────────────────────────┤
│ Phase 4  │ 多资产扩展                                                │
│          │ 🔲 Index 行情接入 (bars_index_zh_a_daily_nf)              │
│          │ 🔲 ETF 行情接入 (bars_etf_zh_a_daily_nf)                  │
│          │ 🔲 Artemis Provider 简化为统一 PhoenixBarsProvider        │
│          │ 🔲 data_source_registry 元数据服务                         │
├──────────┼─────────────────────────────────────────────────────────────┤
│ Phase 5  │ 财务数据 + 高级特性                                       │
│          │ 🔲 fundamental 域表设计与实现                               │
│          │ 🔲 Redis 缓存层 (行情热点数据)                             │
│          │ 🔲 ClickHouse 双写 (大规模历史查询场景)                    │
│          │ 🔲 数据质量监控 (完整性/新鲜度报表)                        │
└──────────┴─────────────────────────────────────────────────────────────┘
```

---

## 9. 全局术语统一

为避免团队沟通歧义，制定以下术语标准：

| 术语 | 定义 | 旧用法（废弃） |
|------|------|---------------|
| `symbol` | 证券代码（通用） | `code` |
| `trade_date` | 交易日 / K 线日期 | `date` |
| `asset_type` | 资产类别 (stock/index/etf/...) | 隐含在表名中 |
| `market` | 市场 (zh_a/hk/us/...) | 隐含在表名中 |
| `period` | K 线周期 (daily/weekly/min5/...) | `freq` / `timeframe` (已废弃) |
| `adjust` | 复权类型 (nf/qfq/hfq) | `adjustflag` (baostock 参数) |
| `source` | 数据来源 (baostock/akshare/mairui/...) | `data_source` (可互用) |
| `bars` | K 线行情数据 | `hist` / `history` |
| `taxonomy` | 分类体系 | `market_category` / `category` |

---

## 10. 决策记录 (ADR)

### ADR-001: 行情扩展列使用附属表而非 JSON

**决策**：每个数据源一张附属表（方案 C），而非 JSON 扩展列（方案 D）。

**理由**：
1. MySQL JSON 列的索引和查询性能远不如原生列
2. PE/PB 等指标在因子策略中可能需要 WHERE/ORDER BY，JSON 列不友好
3. 迁移到 ClickHouse 时，JSON 列的兼容性差
4. 附属表的维护成本可控（每个数据源最多 2-3 张表）

**后果**：接入新数据源时需要建新的附属表，但这是一次性操作。

### ADR-002: 分类体系统一为单表 + attrs_json

**决策**：所有分类来源共用 `taxonomy_category` 表，来源特有属性存 `attrs_json`。

**理由**：
1. 分类数据的核心结构高度一致（code/name/parent/level/is_leaf）
2. 来源特有属性（type1/type2、index_code）访问频率低，适合 JSON
3. 避免每新增一个分类来源就全栈复制的模式

**后果**：查询 source 特有属性时需要 JSON 函数，但这些场景很少。

### ADR-003: 表名按 asset_type/market 而非 data_source 分组

**决策**：标准行情表按 `bars_{asset_type}_{market}_{freq}_{adjust}` 命名。

**理由**：
1. 同一个 symbol 的数据可能来自多个数据源，但应该合并存储
2. 查询时用户关心的是"000001 的日线"，而非"baostock 的 000001 日线"
3. 数据源只影响扩展列，不影响标准行情

**后果**：多数据源写入同一张标准表时需要 upsert 合并策略。

---

## 11. 附录

### A. 各数据源列对比

| 列名 | baostock | akshare | tushare | mairui | 标准表 | 归属 |
|-------|----------|---------|---------|--------|--------|------|
| date/trade_date | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| code/symbol | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| open | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| high | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| low | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| close | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| volume | ✅ | ✅ | ✅ | ✅ | ✅ | 标准 |
| amount | ✅ | ✅ | ✅ | ❌ | ✅ | 标准 |
| preclose | ✅ | ❌ | ✅ | ❌ | ✅ | 标准(可选) |
| pct_chg | ✅ | ✅ | ✅ | ❌ | ✅ | 标准(可选) |
| turn (换手率) | ✅ | ❌ | ✅ | ❌ | ❌ | 扩展 |
| pe_ttm | ✅ | ❌ | ✅ | ❌ | ❌ | 扩展 |
| ps_ttm | ✅ | ❌ | ❌ | ❌ | ❌ | 扩展 |
| pb_mrq | ✅ | ❌ | ✅ | ❌ | ❌ | 扩展 |
| pcf_ncf_ttm | ✅ | ❌ | ❌ | ❌ | ❌ | 扩展 |
| adj_factor | ❌ | ❌ | ✅ | ❌ | ❌ | 扩展 |
| total_mv | ❌ | ❌ | ✅ | ❌ | ❌ | 扩展 |
| circ_mv | ❌ | ❌ | ✅ | ❌ | ❌ | 扩展 |

### B. 各资产类型行情列对比

| 列名 | Stock | Index | ETF | Futures | Fund |
|-------|-------|-------|-----|---------|------|
| symbol | ✅ | ✅ | ✅ | ✅ | ✅ |
| trade_date | ✅ | ✅ | ✅ | ✅ | ✅ |
| open/high/low/close | ✅ | ✅ | ✅ | ✅ | ❌(用 nav) |
| volume | ✅ | ✅ | ✅ | ✅ | ❌ |
| amount | ✅ | ✅ | ✅ | ✅ | ❌ |
| preclose | ✅ | ✅ | ✅ | ✅ | ❌ |
| open_interest | ❌ | ❌ | ❌ | ✅ | ❌ |
| settle | ❌ | ❌ | ❌ | ✅ | ❌ |
| nav | ❌ | ❌ | ✅ | ❌ | ✅ |
| discount_rate | ❌ | ❌ | ✅ | ❌ | ❌ |
| acc_nav | ❌ | ❌ | ❌ | ❌ | ✅ |

> 基金 (Fund) 的行情结构与其他资产差异较大，可考虑使用独立的 `fund_nav` 表而非 `bars_fund_*`。

### C. 与 Artemis CacheEngine 的字段对齐

Artemis CacheEngine 使用 `date` 列做分区和去重。迁移后需注意：

| CacheEngine 逻辑 | 旧字段 | 新字段 | 影响 |
|------------------|--------|--------|------|
| `df["date"]` 分区分组 | `date` | `trade_date` | 需在 CacheEngine 增加 alias 或归一化 |
| `drop_duplicates(subset=["date"])` | `date` | `trade_date` | 同上 |
| `mask = (df["date"] >= start) & ...` | `date` | `trade_date` | 同上 |

**建议**：在 Artemis `MarketDataService` 中，从 PhoenixA 拿到数据后，统一 rename `trade_date` → `date` 以保持 CacheEngine 内部不变。

