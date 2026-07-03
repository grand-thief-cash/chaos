# security_registry 代理主键化与 ODS 表外键引用改造 — 调研报告

> 状态: **调研阶段,未改动任何代码**
> 日期: 2026-07-02
> 作者: 调研产出 (基于 dev/alpha 分支 v0.38.3 / phoenixA v1.26.3)
> 范围: chaos 量化系统 — phoenixA (数据中台) + artemis (下载 agent) + 下游消费方 (cronjob / cthulhu / atlas)

---

## 0. TL;DR

- 本次改造的核心: 给 `ods.security_registry` 增加一个**代理主键 `id` (BIGSERIAL)**,并让其他携带冗余 `symbol`/`source`/`market` 列的 ODS 表通过**逻辑外键**引用 `security_registry.id` (以及 `taxonomy_category.id`),使数据之间能天然按字段 JOIN。
- 自然唯一键定为 **`(exchange, asset_type, symbol)`** 三元组 (见 §3.1) — 单靠 `(exchange,symbol)` 有形式歧义风险,三元组最稳妥;代理 `id` 是它的代理。
- `bars_*` 物理**存储表**不新增字段、不改主键(永久特例) — asset_type 已编码在物理表名里,数据量大,保持现状;但 **bars API / artemis 契约仍迁 `security_id`**(存储特例不外溢成 API 特例,见 §3.2)。
- `market`/`asset_type` 当前 hardcode (`zh_a`/`stock`),但**必须引用 consts 枚举,禁止 magic** (见 §3.3)。
- `asset_type`/`exchange`/`market`/`source` 建议 govern 化为 `govern.data_enum_dictionary` 枚举;`taxonomy` 保持开放命名空间 (见 §3.4)。
- **全量重建重导,不做增量迁移,不留 legacy 列/代码,不双轨过渡** — 有 bug 立刻修 (见 §5.1.1)。直接改 `0001_ods.sql`,重建后由 artemis 重新下载导入。
- **不建真实 FK 约束** — security_id/category_id 是逻辑外键,DDL 不写 `REFERENCES`,只加索引 (见 §6 R9)。
- **对外 `/api/v2/*` API 直接迁到 `security_id`**(不双轨,含 bars API),artemis (含 factor_engine/BI) + cthulhu 的 factor/BI 前端须同步改造;**workbench/strategy_run 本批 scope-out**;cronjob/atlas 不受影响 (见 §5 break 矩阵)。
- SDK 元数据: 当前 base 任务只用 `get_code_info`(§3.5.2.1, 字段稀疏),但 SDK 另有 `get_stock_basic`(§3.5.2.9) **能补齐** `full_name/list_date/delist_date/status` (含已退市) — 已修正上一版误判 (§4.1)。`exchange`/`asset_type` 仍需派生。
- **终态契约 artifact (§10)**: 终态 DDL 表格 (§10.a)、API 契约矩阵 (§10.b)、resolve 语义 (§10.c)、重建导入顺序 (§9.bis) — 可直接作为实施蓝图。
- **实施前须闭合的真实代码路径 (§10.d)**: field dictionary/0004 seed 的 MARKET_CODE→symbol (运行时 break)、bars ext+write buffer resolve 时机、industry buffer 旧维度签名、bars route 双来源、derived_flags scope decision、测试清单。
- 本文档不含代码改动,仅做影响范围/风险/成本分析与分阶段计划 (§7/§8/§9/§10)。

---

## 1. 背景与目标

### 1.1 用户提出的问题

review `ods` 层表设计后发现若干不合理之处:

1. `ods.security_registry` 缺少 `id`,但证明证券唯一性的应是 `exchange+asset_type+symbol` (或 `exchange+symbol`)。
2. 有了 1. 之后,`ods.taxonomy_security_map` 等表不必再维护冗余列,只需 ref `security_registry.id`。
3. `ods.taxonomy_category` 作为分类基表,`taxonomy+code` 定位唯一行,`taxonomy_security_map` 也可 ref `taxonomy_category.id`。
4. 其他类似表同理需分析。
5. Artemis 下载任务应先下基础元数据 (security registry) 作为 base,其他下载任务写入时 ref 该 base,使数据天然可按字段 JOIN。
6. 调整 5. 会引发 phoenixA + artemis 数据处理变更,以及业务层 API 大量接口问题,需同步调整查询。

### 1.2 本次产出

不改动代码,只产出本调研文档: 改动点清单、影响范围、潜在风险、改动成本、分阶段改造计划。

---

## 2. 现状盘点

### 2.1 security_registry 现状

- DDL: `migrations/postgresql/security/0001_ods.sql:575-588`
- Go model: `internal/model/security.go:7-21`
- **无 `id` 列**。主键是复合自然键 `pk_security_registry (symbol, asset_type, market)`。
- 无 `source` 列 (单源主数据,artemis 从 AmazingData `get_code_info` 下载,POST `/api/v2/securities/upsert`)。
- `exchange` 是**存储列** (varchar(8)),但实际由调用方在请求体里传入、`ToUpper(TrimSpace)` 后落库。
- `full_name` / `list_date` / `delist_date` 是**预留空列**,当前无数据源填充 (`0001_ods.sql:604-607`)。
- upsert 去重: `OnConflict` on `(symbol, asset_type, market)`,更新 `exchange/name/full_name/status/list_date/delist_date/updated_at` (`internal/dao/security_dao.go:76-80`)。
- **没有任何其他 DAO/JOIN 查询 `security_registry`** — 它目前是完全孤立的写入选表,无 FK 被引用 (grep `security_id`/`REFERENCES ods.security_registry` 零命中)。
- 唯一的单行查询是 `Get(ctx, symbol, assetType, market)`,需要三元组全传 (`security_dao.go:89`)。

### 2.2 携带冗余 symbol/source/market 的 ODS 表清单

| 表 (model file:line) | 携带冗余列 | 当前去重唯一键 | source 列 | 是否多源 | 备注 |
|---|---|---|---|---|---|
| `taxonomy_security_map` (`taxonomy.go:27`) | source,taxonomy,category_code,symbol,asset_type,market | `uk_src_tax_cat_sec` (全六列) | 是 | — | **无代理 id**,复合键即整行;非下载直写,由 `SyncMappingsFromConstituents` JOIN 派生 |
| `industry_constituent` (`taxonomy.go:57`) | source,taxonomy,market,index_code,con_code,symbol | `uk_src_tax_idx_sym` | 是 | 否 (amazing_data) | 已有代理 `id` (BIGSERIAL) |
| `industry_weight` (`taxonomy.go:77`) | source,taxonomy,market,index_code,symbol,trade_date | 复合 PK (全六列含 trade_date) | 是 | 否 | TimescaleDB hypertable;**无代理 id** |
| `industry_daily` (`taxonomy.go:95`) | source,taxonomy,market,index_code,trade_date | 复合 PK | 是 | 否 | hypertable;**无 symbol 列** (指数级,不在本次 symbol 改造范围) |
| `taxonomy_category` (`taxonomy.go:7`) | source,taxonomy,market,code | `uk_src_tax_mkt_code` | 是 | 是 (swhy+mairui) | 已有代理 `id`;分类基表,被 ref 目标 |
| `financial_statement` (`financial_statement.go:11`) | source,symbol,market | `uk_fin_stmt` (source,symbol,market,statement_type,reporting_period,report_type,statement_code) | 是 | **是 (amazing_data+baostock)** | 已有代理 `id`;多源是关键约束 (见 §3.5) |
| `corporate_action` (`corporate_action.go:11`) | source,symbol,market | `uk_corp_action` | 是 | 否 (amazing_data) | 已有代理 `id` |
| `equity_structure` (`equity_structure.go:13`) | source,symbol,market | `uk_equity_structure` | 是 | 否 (amazing_data) | 已有代理 `id` |
| `adjust_factor` (`adjust_factor.go:6`) | source,symbol,market | `uk_adjust_factor` | 是 | 否 (baostock) | 已有代理 `id` |
| `long_hu_bang` (`long_hu_bang.go:6`) | source,symbol,market | `uk_long_hu_bang` | 是 | 否 (amazing_data) | **无代理 id**,唯一键即整行 |
| `bars_stock_zh_a_daily_{nf,hfq}` (`bars.go:7`) | **仅 symbol,trade_date** | PK (symbol,trade_date) | **否** | 否 (baostock) | asset_type/market 在表名;**特殊处理,不改** (§3.2) |
| `bars_index_zh_a_daily_nf` (`bars.go:7`) | 仅 symbol,trade_date | PK (symbol,trade_date) | 否 | 否 (baostock) | 同上 |
| `bars_ext_baostock_stock_zh_a_daily` (`bars.go:52`) | 仅 symbol,trade_date | PK (symbol,trade_date) | 否 | 否 (baostock) | 同上;source 编码在表名 |

### 2.bis 已有 schema drift (改造前须先修, 应 review P1-1)

`taxonomy_security_map` 是本次改造核心表,但它本身已存在 drift:
- DDL `0001_ods.sql:70-77` **无** `created_at`/`updated_at` 列 (只有 6 个业务列 + 唯一约束)。
- Go model `taxonomy.go:34-35` **有** `CreatedAt`/`UpdatedAt` (`autoCreateTime`/`autoUpdateTime`)。
- DAO `taxonomy_dao.go:349` 的 `ListMappingsBySymbol` `SELECT ... created_at, updated_at`。

**影响**: 严格按 migration 建的库上,`GET /api/v2/taxonomy/by_security/{symbol}` 会因查不到时间列而失败 (当前能跑通,大概率是 GORM AutoMigrate 或历史库补过列,但 DDL 与代码不一致是既成事实)。本次改造动这张表时,必须**同轮把时间列 drift 解决** (DDL 补列,或移除 model/DAO 中的时间字段),不能在 drift 之上再叠 security_id 改造。

> 同类 drift 排查应扩展到其他表 (review P1-1 建议):改造前做一次 model↔DDL 全量对齐 audit,纳入 §9 阶段 0。

### 2.3 taxonomy_security_map 的派生链 (改造后: 中间表,无需 JOIN)

**现状 (改造前)** — `internal/dao/taxonomy_dao.go:180-200` `SyncMappingsFromConstituents`,用一条 `INSERT...SELECT ... JOIN` 在 SQL 里把成分股 × 分类节点拼起来:

```sql
INSERT INTO ods.taxonomy_security_map (source, taxonomy, category_code, symbol, asset_type, market)
SELECT DISTINCT ic.source, ic.taxonomy, tc.code, ic.symbol, 'stock', ic.market
FROM ods.industry_constituent ic
JOIN ods.taxonomy_category tc
  ON tc.index_code = ic.index_code
 AND tc.source = ic.source AND tc.taxonomy = ic.taxonomy AND tc.market = ic.market
WHERE ic.source = ? AND ic.taxonomy = ? AND ic.market = ?
ON CONFLICT (source, taxonomy, category_code, symbol, asset_type, market) DO NOTHING
```

这是全代码库**唯一**的非 vendor 跨表 JOIN (join 在 `index_code` 上)。

**改造后** — `taxonomy_security_map` 本质是 `security_registry` × `taxonomy_category` 的**纯中间表**,只需 `(security_id, category_id)` 两列。`asset_type/symbol/market` 全部由 `security_id` 替代,`source/taxonomy/category_code` 全部由 `category_id` 替代。

关键变化:**JOIN 被消除**。id 解析**不在派生中间表时做 DB JOIN**,而是**前移到成分股 upsert 写入时**,用 redis/内存缓存匹配:

- 成分股 upsert 时 (`industry_constituent` 已压缩为 `category_id, security_id, in_date, out_date`,见 §2.5),phoenixA 把 SDK 的 `index_code`→`category_id`、`CON_CODE`→`security_id` 用 **redis/内存缓存**解析 (taxonomy_category 全量缓存 + security_registry 全量缓存,见 §6 R7 的 getAll+缓存)。写入 industry_constituent 时两列 id 就已落库。
- 于是 `SyncMappingsFromConstituents` 派生中间表**无需任何 JOIN**:

```sql
INSERT INTO ods.taxonomy_security_map (security_id, category_id)
SELECT DISTINCT security_id, category_id
FROM ods.industry_constituent
WHERE category_id IS NOT NULL AND security_id IS NOT NULL
ON CONFLICT (security_id, category_id) DO NOTHING
```

- 好处: 派生 SQL 退化为单表 `SELECT DISTINCT`,无 JOIN、无 index_code/source/taxonomy/market 字符串比较;id 解析集中在写入路径 + 缓存,可复用、可观测。
- **path scope (应 review P0-1)**: 路由 `POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/mapping/sync_from_constituents` (`router_v2.go:76`) 的 path 参数 source/taxonomy/market 在压缩后的表上已无对应列,直接全表 `SELECT DISTINCT` 会让 path 失去范围限定。正确做法: sync 时**先把 path 的 (source,taxonomy,market) resolve 成一组 `category_id`**(经 taxonomy_category 缓存),sync SQL 加 `WHERE category_id IN (...)` 做范围限定:
```sql
INSERT INTO ods.taxonomy_security_map (security_id, category_id)
SELECT DISTINCT security_id, category_id
FROM ods.industry_constituent
WHERE category_id IN (?)   -- path 参数 resolve 出的 category_id 集合
ON CONFLICT (security_id, category_id) DO NOTHING
```
被 artemis `StockZHAIndustryConstituentSWHY` 在 upsert 成分股后调用 (见 §5.2)。
- **resolve 失败语义 (应 review P1-3)**: 成分股 upsert 时若 `index_code`→category_id 或 `CON_CODE`→security_id 缓存未命中,phoenixA 必须**拒绝该行** (返回 per-row rejected,含原始 natural key + 失败原因 + row index),**不静默写 NULL/orphan id**。若 taxonomy_category 尚未导入,industry_constituent 整批 upsert 应立即失败并提示前置依赖缺失。
- 注: 若希望中间表完全无派生步骤,亦可考虑直接做成 `industry_constituent(security_id, category_id)` 上的视图 — 但成分股表含 in_date/out_date 时序语义,视图去重需 DISTINCT,与物化中间表性能权衡留待实现定。

### 2.4 查询访问模式 (改造后: 优先用 id, 不再用 symbol)

- 改造后查询**尽量使用 `security_id` / `category_id`**,不再沿用原 `symbol` 入参。
- `ListMappingsBySymbol` (`taxonomy_dao.go:347-351`): 现按 `symbol` 单列查 `taxonomy_security_map`,是 `GET /api/v2/taxonomy/by_security/{symbol}` 的后盾。改造后改为按 `security_id` 查 (端点也随之迁 id,见 §3.6)。
- 各数据表 DAO 的 `symbol = ?` / `symbol IN ?` 过滤 (financial/corporate/equity/adjust_factor/long_hu_bang 的 Query/Count) 改为 `security_id = ?` / `security_id IN ?`。
- `catalog_coverage_dao.go:49/71/93` 的 `WHERE symbol = $1 AND market = $2` (GetSymbolCoverage) 改为 `WHERE security_id = $1`。
- **例外 (bars)**: `bars_*` 物理表无 security_id 列 (§3.2),**bars DAO/物理存储查询用 resolved symbol** (+ 表名隐含 asset_type/market);但 **bars API 仍以 security_id 为主**,phoenixA 入口 resolve 后查物理表。
- 兜底: 仍保留 `get(exchange, symbol)` / `getAll()` 形式的 security 解析 (供 artemis 加载时用,见 §6 R7/R8),但这属于 id 解析能力,非主查询路径。

### 2.5 ODS 表 FK 压缩分析 (应用户问: industry_weight/industry_daily/taxonomy_category/industry_constituent 是否都能用 FK 压缩)

| 表 | 现有冗余列 | 可否压缩 | 压缩后 |
|---|---|---|---|
| `industry_constituent` | source,taxonomy,market,index_code,con_code,symbol | **能** | `category_id` (←index_code 经 taxonomy_category 解析) + `security_id` (←symbol 经 security_registry 解析) + in_date/out_date;con_code (=exchange.symbol) 可由 security_id 派生,删除 |
| `industry_weight` | source,taxonomy,market,index_code,symbol,trade_date | **能** | `category_id` + `security_id` + trade_date + weight;source/taxonomy/market 由 category_id 派生,删除 |
| `industry_daily` | source,taxonomy,market,index_code,trade_date (无 symbol,指数级) | **能 (仅 category_id)** | `category_id` + trade_date + OHLCV/估值;无 symbol 故无 security_id;source/taxonomy/market 由 category_id 派生 |
| `taxonomy_category` | source,taxonomy,market,code | **否 (基表,被引用)** | 这是分类**基表**(类比 security_registry),自身被其他表引用。source/taxonomy/market/code 是它的业务身份,已有代理 `id`。不做 FK 压缩,只作为 ref 目标 |

> 说明: 压缩后 `source/taxonomy/market` 不再冗余存储,因其可由 `category_id` 反查 `taxonomy_category` 得到 (category 行含 source/taxonomy/market)。这是逻辑上的规范化;**实践中不建真实 FK 约束** (§6 R9),只在 id 列上加索引。
> `industry_constituent` 的 `con_code` 删除后,若查询需要带后缀代码,由 security_registry 的 (exchange,symbol) 拼接得到。

---

## 3. 关键决策 (已与用户确认)

### 3.1 自然唯一键 = (exchange, asset_type, symbol) + 代理 id

- **三元组最稳妥**。单靠 `(exchange, symbol)` 有风险: `000001.SZ` vs `000001.SH` 这种形式上仍可能因代码格式/同交易所同代码不同资产类型产生歧义。把 `asset_type` 纳入唯一键可彻底消除歧义 (如某交易所同代码的股票 vs 指数 vs ETF)。
- `asset_type` **进唯一键** (不仅是属性列),与 `exchange`/`symbol` 共同构成自然键。
- 代理 `id` (BIGSERIAL) 是 `(exchange, asset_type, symbol)` 的代理,作为被其他表引用的逻辑 FK,避免到处复制三元组字符串。
- **PK 设计**: `id` 为主键,`(exchange, asset_type, symbol)` 为 `UNIQUE NOT NULL` 约束 (保证业务唯一 + 允许 `OnConflict` 按自然键 upsert 去重)。`market` 为普通属性列 (当前恒 `zh_a`)。
- **exchange 规范**: phoenixA 定义 exchange 为**大写** (`SH/SZ/BJ`),所有调用方必须遵守;artemis `stock_zh_a_list.py` sink 时把 `code` 拆出 exchange 传入的做法正确 (§6 R1 已澄清非风险)。

### 3.2 bars_* 表: 存储层保留 symbol,API/Artemis 契约迁 security_id (用户已拍板)

- `bars_*` 数据量大 (日线,TimescaleDB hypertable),asset_type/market/adjust/period **已编码在物理表名** (`table_resolver.go` 的 `fmt.Sprintf("ods.bars_%s_%s_%s_%s", ...)`)。
- 股票 `000001.SZ` 与指数 `000001.SH` 靠**物理表名** (`bars_stock_*` vs `bars_index_*`) 区分,无需在行内用 asset_type 列。
- **存储层 (永久特例)**: bars 物理表保留 `symbol` 列与 `(symbol, trade_date)` 主键,**不引入 security_id 列** (大表宽度/写入成本 + asset_type 已在表名)。这是存储层特例,非技术债。
- **API/Artemis 契约层 (用户拍板: 迁 security_id)** — 存储特例**不外溢成 API 特例**:
  - bars query / last_update / upsert 契约以 `security_id`/`security_ids` 为主参 (另需 `period`/`adjust` 定位物理表,这两个维度不在 security_id 里)。
  - phoenixA 内部 resolve `security_id -> (symbol, asset_type, market, exchange)` 后调 `table_resolver` + bars DAO:
    ```
    caller (security_id, period, adjust)
      -> resolve security_registry(id) -> (symbol, asset_type, market, exchange)
      -> table_resolver(asset_type, market, period, adjust) -> bars 表名
      -> query bars by symbol
    ```
  - `last_update` 批量接口入参从 `symbols` 迁 `security_ids`,响应可附 `symbol` 作展示/debug,但 symbol 不再是业务身份主键。
  - **vendor 边界**: artemis 调 baostock/amazingData 时仍需 vendor code (`sz.000001` / `000001.SZ`),由 security_id resolve 出 (exchange,symbol) 后拼装,这是 SDK 格式,非业务 API 契约。
  - artemis bars 任务 payload 传 security_id,内部反解 vendor code 调 SDK、用 resolved symbol 写 bars 物理表。

### 3.3 hardcode 策略: 当前默认值用 const,扩展时升为显式维度 (应 review P1-7)

- 当前实际数据**只有 A 股股票**: `market=zh_a`、`asset_type=stock`。
- 查询/下载链路定位时,`market`/`asset_type` 取当前唯一值,**必须引用预定义 const** (`consts.MARKET_ZH_A`、`consts.ASSET_TYPE_STOCK`),**严禁散落 magic string/number**。
- **修正措辞 (review P1-7)**: 扩展到 ETF/index **不是"改 const 值"**,而是同一系统要**同时支持多个 asset_type** — 届时 asset_type 从默认常量**提升为显式维度**: task 参数/API 接收 asset_type、security_registry 同时存多类型、table_resolver 按资产类型选表、resolve/cache key 必须含 asset_type、`get_securities()` 返回结构要避免同 symbol 不同 asset_type 碰撞。
- 文档与代码注释须标注"当前 const 默认值,扩资产类型时升为显式维度"。
- 与 §3.4 govern 化配合: const 是代码侧引用,govern enum 是数据侧受控词表,二者保持一致 (const 值 = enum code)。

### 3.4 枚举 govern 化

现有 `govern.data_enum_dictionary` (`0003_govern.sql:162`,唯一键 `source, enum_name, code, contract_version`) 就是为枚举字典设计。

| 候选 | 是否 govern 化 | 理由 |
|---|---|---|
| `asset_type` | **是** | 闭集 (stock/index/etf/fund/futures/cb),现散落在 `internal/consts/asset_type.go` 硬编码。做成 `enum_name='asset_type'` 行,既给 security_registry 受控词表,也让 bars 表名拼接的 asset_type 有据可查。 |
| `exchange` | **是** | 闭集 (SH/SZ/BJ),全局稳定码,现靠代码后缀字符串派生、无统一约束。做成 `enum_name='exchange'` 行。 |
| `market` | **是 (应 review P1-8)** | 闭集 (当前 zh_a;未来 hk/us 等)。业务市场分区,与 exchange(交易场所) 区分: zh_a↔SH/SZ/BJ 是一对多。DDL/API/taxonomy 唯一键大量用 market,应进 `enum_name='market'`。 |
| `source` | **是 (provenance,应 review P1-4)** | 闭集 7 值 (`consts/data_source.go`)。**source 是数据血缘(provenance),非证券身份冗余** — 即使单源表也建议保留 (排查数据质量、未来扩源)。`bars_ext_baostock_*` 已用表名编码 source 可不存列。用固定 `source='phoenixa'` 的元枚举行承载 enum 字典本身。 |
| `taxonomy` | **否** | 开放命名空间 (swhy/mairui/未来扩展),更像标识符非闭集;强行闭集化阻碍扩展。保持自由字符串 + (source,taxonomy) 复合命名。 |

> 注: govern 化是**独立可先行**的子项,不阻塞 security_id 主改造 (见 §9 阶段 0)。

### 3.5 多源表: source 留作去重,security_id 仍每行对应

- `financial_statement` 多源 (amazing_data 的 balance_sheet/income/cashflow/profit_express/profit_notice + baostock 的 bs_balance);`corporate_action` 实际也多源 (amazing_data dividend/right_issue + baostock bs_dividend)。
- **这不是问题**: 每行记录都对应一个 `security_registry.id` (同一证券),多 source 只是同一证券的多份来源数据。
- `source` **保留在去重唯一键**里 (同证券同报表期,amazing_data 与 baostock 各一行),但不并入 security_id — security_id 只编码 `(exchange, asset_type, symbol)`。
- 即多源表唯一键形如 `(security_id, source, statement_type, reporting_period, ...)`。

### 3.5.bis source 保留策略 — 逐表终态清单 (应 review P1-2)

`source` 是 provenance(数据血缘),非证券身份冗余。逐表决定 (不再用"可留可去"模糊表述):

| 表 | source 处理 | 理由 |
|---|---|---|
| `taxonomy_security_map` | **删** (无 source 列) | 退化为 `(security_id, category_id)`,source/taxonomy/market 经 category_id 反查 taxonomy_category 得到 (通过引用保留 provenance) |
| `industry_constituent` | **删** (无 source 列) | 压缩为 `(category_id, security_id, in_date, out_date)`,provenance 经 category_id 反查 |
| `industry_weight` | **删** (无 source 列) | 同上,provenance 经 category_id 反查 |
| `industry_daily` | **删** (无 source 列) | `(category_id, trade_date, ...)`,provenance 经 category_id 反查 |
| `financial_statement` | **保留** (在唯一键) | 多源 (amazing_data+baostock),source 参与去重 + 血缘 |
| `corporate_action` | **保留** (在唯一键) | 多源 (amazing_data+baostock),同上 |
| `equity_structure` | **保留** | 单源 (amazing_data) 但留作血缘,未来可能扩源 |
| `adjust_factor` | **保留** | 单源 (baostock) 但留作血缘 |
| `long_hu_bang` | **保留** | 单源 (amazing_data) 但留作血缘 |
| `bars_ext_baostock_*` | **不存** | source 已编码在物理表名 (`bars_ext_baostock_*`) |
| `bars_stock/index_*` | **不存** | 单源 baostock,且 asset_type/market 在表名;无 source 列需求 |

> 规则: security identity 字段 (symbol/market) → 用 security_id 替代;taxonomy identity/provenance (source/taxonomy/market) → 有 category_id 的表经反查保留,无 category_id 的 vendor 数据表 (financial/corporate/equity/adjust/lhb) 直接在本表保留 source。

### 3.6 对外 API 迁移到 security_id (不做双轨)

- 用户确认: API 肯定要变,消费方使用时也要变。
- `/api/v2/*` 的 path/query 参数与请求/响应体**直接迁到 `security_id`**,**不保留 symbol 双轨**。响应每行返回 `id, symbol, ...` (id 稳妥,见 §6 R6)。
- 有 bug 立刻修,不做渐进过渡。这使 artemis (含 factor_engine/BI) + cthulhu factor/BI 前端成为**必须同步改造**的消费方;**workbench 本批 scope-out** (§8 Q4) (§5)。

---

## 4. SDK 字段可用性约束 (决定 security_registry 能填到什么程度)

来源: `docs/third_party_sdk/AmazingData_development_guide.md` + baostock 代码实测。

> **修订说明 (2026-07-02, 应 review P0-1)**: 上一版误判 `full_name/list_date/delist_date` "SDK 根本不提供"。实际是当前实现 `StockZHAList` 只调用了 `get_code_info`(§3.5.2.1),**未调用** `get_stock_basic`(§3.5.2.9)。SDK 文档层面这些字段是有来源的 (见下)。本节已据实修正。

### 4.1 填充 security_registry 的两个候选 AmazingData 端点

**A. `get_code_info` (§3.5.2.1 "每日最新证券信息") — 当前 base 任务唯一在用的端点**

返回字段 (verbatim, doc:210-215):
- DataFrame index = 股票代码 (即 symbol)
- columns: `symbol` (证券简称)、`security_status` (产品状态标志)、`pre_close`、`high_limited`、`low_limited`、`price_tick`

仅能填 `symbol`/`name`,并提供一个 `security_status` 状态标志 (文档未明确 active/delisted 枚举映射)。**不提供** full_name/list_date/delist_date/exchange/asset_type。

**B. `get_stock_basic` (§3.5.2.9 "证券基础信息") — 当前未用,但能补齐 base 元数据**

`info_data_object.get_stock_basic(code_list)`,输入 `code_list`(沪深北代码列表,含已退市)。返回字段 (verbatim, doc:357-363):

| SDK 字段 | 类型 | 含义 | → security_registry 列 |
|---|---|---|---|
| `MARKET_CODE` | string | 证券代码 | symbol (去后缀) / exchange (后缀派生) |
| `SECURITY_NAME` | string | 证券简称 | name |
| `COMP_NAME` | string | 证券中文名称 | **full_name** |
| `COMP_NAME_ENG` | string | 证券英文名称 | (可选 full_name 补充) |
| `LISTDATE` | int | 上市日期 | **list_date** |
| `DELISTDATE` | int | 退市日期 | **delist_date** |
| `LISTPLATE_NAME` | string | 上市板块名称 | (可入 attrs) |
| `IS_LISTED` | int | 上市状态 (1=上市交易, 3=终止上市) | **status** |

**关键结论 (修正后)**: 当前 `security_registry` 的 `full_name`/`list_date`/`delist_date`/`status` **未被填充,是因为 base 任务只调 `get_code_info`,不是 SDK 无来源**。SDK 的 `get_stock_basic`(§3.5.2.9) 完全能补齐这些列 (含已退市标的)。`exchange`/`asset_type` 仍需派生 (代码后缀 / `security_type` 输入),SDK 不直接返回。

**对改造的影响**:
- 若要让 `security_registry` 成为完整的 base 元数据,base 下载任务应评估升级为 `get_code_info + get_stock_basic` 组合 (见 §8 Q1、§9 阶段 1)。
- `list_date/delist_date/full_name/status` 的填充**不是本次 security_id 化的前置依赖** (id 改造只依赖 symbol/exchange/asset_type 唯一性),但与 base 任务升级高度相关,建议同阶段评估。
- 派生 `exchange` 的逻辑必须**集中到 phoenixA 侧统一处理** (见 §6 R1),不信任调用方传入,否则同证券可能因大小写/格式差异产生多行。

### 4.2 AmazingData `get_industry_base_info` (§3.5.13.1) → taxonomy_category

字段: `INDEX_CODE`、`INDUSTRY_CODE`、`LEVEL_TYPE` (1/2/3)、`LEVEL1_NAME`/`LEVEL2_NAME`/`LEVEL3_NAME`、`IS_PUB`、`CHANGE_REASON`。
- **无 parent_code/pcode 字段**。父子关系靠 `LEVEL1/2/3_NAME` 名称层级匹配派生 (当前 artemis/post_process 已这么做)。

### 4.3 AmazingData `get_industry_constituent` (§3.5.13.2) → industry_constituent

字段: `INDEX_CODE`、`CON_CODE`、`INDATE`、`OUTDATE`、`INDEX_NAME`。
- `CON_CODE` **始终带交易所后缀** (如 `603648.SH`),纯 symbol 须 `split(".")[0]` 派生 (artemis `stock_zh_a_industry_constituent_swhy.py:64-65` 已做)。
- 无直接给纯 symbol 的字段。

### 4.4 baostock `query_history_k_data_plus`

- 返回 14 列: `date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM` (`config/task.yaml:31,39`)。
- `adjustflag` 是**查询参数**不是返回字段 (hfq→1/qfq→2/nf→3)。
- **不返回 exchange/market 列**。代码以 `sh.600000` 格式输入 (lowercase-exchange-prefix),`symbol` 由 artemis 从 params 注入 (`stock_zh_a_hist_child.py:55`),非来自响应。
- baostock 对 security_registry 的 exchange/market 无贡献。

---

## 5. 影响范围分析

### 5.1 phoenixA 侧改动点

#### 5.1.1 migration (`migrations/postgresql/security/`) — 全量重建,直接改 DDL

> **决策 (用户确认, 2026-07-02)**: **不考虑现有数据和表,全部重建重新导入数据,不做增量迁移,不保留 legacy 列/代码**。有 bug 立刻修,不双轨过渡。

因此直接修改 `0001_ods.sql` 的目标结构 (新库直建到位),**不需要** existing-DB 增量迁移 / backfill / 双写。重建后由 artemis 重新下载导入全部数据。

**目标 DDL 改动**:
- `security_registry`: 加 `id BIGSERIAL PRIMARY KEY`,自然键 `UNIQUE (exchange, asset_type, symbol)`;`market` 为普通列。
- 各表用 id 列**直接替换**冗余的 symbol/source/taxonomy/category_code/market 列 (不留 legacy):
  - `taxonomy_security_map`: `security_id` + `category_id` (替换全部六元组列)。
  - `industry_constituent`: `category_id` + `security_id` (替换 source/taxonomy/market/index_code/con_code/symbol;con_code 由 security_registry 的 (exchange,symbol) 派生)。
  - `industry_weight`: `category_id` + `security_id` (替换 source/taxonomy/market/index_code/symbol)。
  - `industry_daily`: `category_id` (替换 source/taxonomy/market/index_code;无 symbol 故无 security_id)。
  - `financial_statement`/`corporate_action`/`equity_structure`/`adjust_factor`/`long_hu_bang`: `security_id` 替换 symbol/market;**多源表保留 `source`** (§3.5)。
- **`bars_*` 不动** (§3.2 永久特例)。
- **不建真实 FK 约束** (§6 R9): 设计上 security_id/category_id 是逻辑外键,但 DDL 里**不写 `REFERENCES`**,只在 id 列上加索引 (避免 hypertable FK 限制 + 写入性能 + 重建复杂性)。

**去重唯一键调整** (直接改,无过渡):
- 各表 `OnConflict` 的自然键里 `symbol`(及 market) 换成 `security_id`,`category_code` 换成 `category_id`。
- 多源表唯一键 = `(security_id, source, statement_type, reporting_period, ...)` 等 (source 留)。
- 单源表唯一键 = `(security_id, divid_operate_date)` 等 (source 保留作血缘,见 §3.5.bis 逐表清单)。

**注意**:
- `taxonomy_security_map`/`industry_weight`/`long_hu_bang` 当前无代理 id,直接按新结构建表 (重建,无需考虑历史主键迁移)。
- hypertable (`industry_weight`/`industry_daily`/`bars_*`) 按新列结构重建;`create_hypertable` 调用保留。因不建真实 FK,无 TimescaleDB FK 限制问题 (§6 R9)。

#### 5.1.2 model (`internal/model/`)
- `security.go`: 加 `ID uint64` 字段。
- 各表 model: 加 `SecurityID uint64` (及 `CategoryID`),**直接删除**被替换的冗余字段 (symbol/source/taxonomy/category_code/market,多源表保留 source)。
- json tag: response 返回 `id, symbol, ...` (id 为主,可附带 symbol 便于人读,见 §6 R6);不再保留全部 legacy 字段。

#### 5.1.3 dao (`internal/dao/`)
- `security_dao.go`: upsert `OnConflict` 按自然键 `(exchange, asset_type, symbol)` 去重 (id 自增);保留 `Get(exchange, symbol)`(asset_type 走 const,§3.3)/ `GetAll()` 形式供 artemis 加载解析 (§6 R7/R8),配缓存。
- `taxonomy_dao.go`: `SyncMappingsFromConstituents` **消除 JOIN** (见 §2.3 终态方案) — `industry_constituent` 写入时已解析 `category_id`/`security_id`,sync 阶段是单表 `SELECT DISTINCT security_id, category_id FROM industry_constituent WHERE category_id IN (...)` (path 参数 source/taxonomy/market 先 resolve 成一组 category_id 做范围限定,见 §2.3)。`ListMappingsBySymbol` 改为按 `security_id` 查 (`GET /api/v2/taxonomy/by_security/{security_id}`)。所有 `WHERE source=? AND taxonomy=? AND category_code=?` 改为 `WHERE category_id=?`。
- 各数据表 dao: `WHERE symbol=?` 改为 `WHERE security_id=?`,`OnConflict` 列调整。
- `table_resolver.go`: bars 不变。

#### 5.1.4 service / controller (`internal/service/`, `internal/controller/`)
- API 请求/响应体直接迁 `security_id` (§3.6, 不双轨)。controller 解析 path/query `security_id`,service 调 dao。
- `taxonomy_controller_test.go` / `corporate_action_controller_test.go` 等契约测试同步改 assertion (历史教训: v0.38.3 的 indate/outdate bug 因测试未断言漏网)。
- 缓存 key: 改为按 `security_id`/`category_id` 建 (如 `BuildSecurityCacheKey(securityID)`)。

#### 5.1.5 catalog 元数据 (`internal/service/catalog_service.go`)
- `:566/:583/:593` 的 declarative `CrossRefs {ToTable:"security_registry", JoinKey:"symbol"}` 是描述性元数据 (非执行 SQL),`JoinKey` 从 `"symbol"` 改 `"security_id"`。
- `:664` 的 `information_schema.columns` introspection 检查 `'source'`/`'symbol'` 列决定 per-source stats — 列结构变了此处逻辑要跟。

#### 5.1.6 openapi.yaml
- 全部 symbol-based path/query/response schema 改 security_id。

### 5.2 artemis 侧改动点

#### 5.2.1 phoenixA HTTP client (`core/clients/phoenixA_client.py`)
- 这是**唯一 chokepoint**,所有 break 集中于此 + 其调用方。
- read 方法 (break 点): `get_securities` (改返回 id)、`get_bars`/`iter_bars`/`get_bars_last_update` (symbols → security_ids,§3.2)、`query_financial_statements`/`query_corporate_actions`/`query_adjust_factors`/`query_long_hu_bang` (symbol/symbols query → security_id)、`get_taxonomy_by_security` (**symbol PATH param** `by_security/{symbol}` → `by_security/{security_id}`)、`query_industry_constituents_by_stock` (**con_code PATH param** → security_id)。
- write 方法: `upsert_securities`/`upsert_bars`/`upsert_financial_statements`/.../`upsert_industry_constituents` 等请求体里的 `symbol` 字段改 `security_id` (bars upsert payload 传 security_id,phoenixA 内部 resolve 出 symbol 写物理表,§3.2)。
- base 后下游拿 id: 不依赖 upsert 返回 id,而是通过 `Get(exchange, symbol)`/`GetAll()`(配缓存)查 id (§6 R7)。

#### 5.2.2 下载任务 (`engines/task_engine/download/zh/`)
- `STOCK_ZH_A_LIST` (`stock_zh_a_list.py`): 基础元数据任务,upsert security_registry (响应可只返 rows,不必返 id,§6 R7)。
- 依赖 `get_code_list_from_phoenixa()` (`utils.py:138-175`) 的任务 (financial/corporate/long_hu_bang/bars/baostock parents): 改为返回 `security_id` (或 (exchange,symbol,id)),下游 payload 带 id。bars 任务 payload 传 security_id,内部反解 vendor code 调 SDK、用 resolved symbol 写 bars 物理表 (§3.2)。
- `base_financial_statement.py:78` / `base_corporate_action.py:75`: 用 security_id 替代 symbol 传给 write payload。
- `stock_zh_a_industry_constituent_swhy.py`: upsert 成分股 + sync_mappings,带 security_id/category_id。

#### 5.2.3 factor_engine / BI (workbench 本批 scope-out)
- `engines/factor_engine/providers/phoenixa_provider.py`: `get_taxonomy_by_security(symbol)` (:181,:732)、`get_bars(symbol=)` (:311)、`query_financial_statements(symbol=)` — 全部 break,改 security_id。
- `services/bi/raw_queries.py` (`query_financial`/`query_corporate_action`/`query_equity_structure` 按 symbol)、`services/bi/discovery.py` (`get_symbol_coverage(symbol)` → `catalog/securities/{symbol}/datasets/summary` PATH param)、`services/bi/dupont.py`、`services/bi/securities.py`。
- factor_engine 与 BI 的结果行 key 从 symbol 改 security_id (§8 Q2 全部升级)。
- **workbench 本批 scope-out** (用户决策,§8 Q4): `services/workbench/*` (含 `phoenix_stock_hist_provider.py`、market_data、backtest) **本批不改**,未来按 id 方向迁。不影响 factor/BI 主链路改造。

### 5.3 消费方 break 矩阵

| 消费方 | 直接调 /api/v2 symbol API? | 依赖 symbol 形态? | symbol→security_id 是否 break | 证据 |
|---|---|---|---|---|
| **cronjob** (Go) | ❌ 只调 artemis `/tasks/run/{TASK_CODE}` | 否 | **否** | `config/config.yaml` 仅 artemis client;无 phoenixA HTTP client;无 DAG,任务顺序仅靠 cron 时序 (见 §5.4) |
| **cthulhu** (Angular) | 仅 `/api/v2/catalog/*`+`/api/v2/buffer/*` (无 symbol) | **间接暴露**: factor/BI 页面经 artemis 透传须改;**workbench 页面本批 scope-out** | **否(直接)**;factor/BI 间接须同步改,workbench 间接本批不动 | direct: `phoenixa.service.ts` 只消费 catalog/buffer。indirect: factor page `factor.service.ts:38-45`、BI `bi.routes.ts:25` 本批改;workbench market-data `workbench-api.service.ts:43-63`、backtest `strategy-config.component.ts`/`workbench.model.ts` 本批 scope-out (§8 Q4) |
| **atlas** (Python) | ❌ 只调 `/api/v1/kg/*`+`/api/v1/graph/*` | 否 (用 company name) | **否** | `connectors/phoenixa_client.py` 全是 kg/graph;grep `/api/v2/` 零命中 |
| **artemis** (Python) | ✅ 重度 | ✅ path/query/响应字段 | **是** | §5.2 |

**结论**: 直接爆破半径集中在 artemis。**间接**爆破半径经 artemis 蔓延到 cthulhu 的 workbench/factor/BI 页面 (review P1-2) — 这取决于 artemis 是否对前端保留 symbol 兼容层,须作为显式决策 (见 §8 Q3)。atlas/cronjob 不受影响。

### 5.3.bis 业务层 symbol 契约 (govern/strategy_run, 应 review P1-3)

用户第 6 点提到"业务层 API 大量问题"。除 ODS 外,以下业务层记录仍以 `symbol` 为标识,本次须显式决策是否纳入 (全量重建语境下,即决定重建后的目标结构):

- **`govern.strategy_run_summary`** (`0003_govern.sql:23-58`): `symbol VARCHAR(32) NOT NULL` + `idx_srs_symbol`。model `strategy_run.go:12` `Symbol string json:"symbol"`。路由 `/api/v1/strategy/run/*` (`router_v2.go:311`)。artemis client `phoenixA_client.py:377-401` 保存 summary/artifacts;workbench backtest `backtest.py:91-94` 写 `symbol=req.symbol`。
- **bars read API** (见 §3.2): 存储不改 (物理表保 symbol),但 API/artemis 契约迁 security_id (用户已拍板)。

**建议**: strategy_run_summary **不纳入第一批 ODS FK 改造**,但须列为"业务层 symbol 契约"显式决策 — 重建后是否加 `security_id`、是否保留 `symbol` 快照字段 (回测结果是历史快照,保留 symbol 快照更合理)。

### 5.4 任务依赖与编排 (用户第 5 点的核心)

- **artemis 无任何任务间依赖机制**: grep `depends_on|dependency|prerequisite` 仅命中无关 import 注释;`config/task.yaml` 只有 per-task variants,无 DAG;`TaskEngine.run` 一次一任务。
- 唯一编排原语是 `OrchestratorUnit` parent→children (同任务内 fan-out,顺序+fail-fast),非跨任务。
- **隐式运行时依赖**: 几乎所有下载任务在 execute 时调 `get_code_list_from_phoenixa()` / `get_securities()` 反查 registry,registry 空则 `ctx.fail("empty code_list ... check PhoenixA /api/v2/securities")`。依赖真实存在,但靠**运行时失败**而非声明约束强制。
- **cronjob 调度时序** (文档 `cronjob/docs/2026-05-07 CONFIG_OF_CRONJOB_AND_ARTEMIS.md`,非代码、DB 运行时数据):
  - `STOCK_ZH_A_LIST` (base): `0 0 18 * * 1-5` (周一至周五 18:00)
  - bars HIST_PARENT: `0 0 19 * * 1-5` (19:00)
  - financial (balance/cashflow/income/profit_*): `0 0 20 * * 1-5` (20:00)
  - corporate-action (dividend/right_issue): `0 0 21 * * 1-5` (21:00)
  - SWHY categories: `0 0 10 * * 1` (周一 10:00);industry-constituent: `0 0 12 * * 6` (周六 12:00);weights/daily: 工作日下午
  - 时序上 base 在前,但**非强制** — 18:00 失败/延迟,19:00/20:00 仍触发,下游会因 registry 空/缺 security_id 而失败。
- **改造影响**: 若 security_id 化后,下游任务的 write payload 必须带 security_id,则它们**强依赖** STOCK_ZH_A_LIST 已为该 symbol 分配 id。当前"运行时失败"兜底依然有效,但**风险面扩大**: 不仅是 registry 是否非空,而是某 symbol 是否已 upsert 拿到 id。建议 (见 §9) 在 artemis 引入轻量"base 任务先行"保障或 phoenixA 提供"upsert-or-resolve"原子接口。

---

## 6. 潜在风险

> **总体说明 (用户反馈, 2026-07-02)**: 本项目**全量重建重导,不考虑历史数据/现有表**,因此所有"历史数据 backfill / 现有库迁移 / schema drift 修复"类风险 (原 R2/R4/R10/R12/R13) **不适用**,已移除。下列为改造本身仍需关注的风险。

- **R1 — exchange 大小写规范 (澄清,非风险)**: phoenixA 定义 exchange 为大写 `SH/SZ/BJ`,所有调用方必须遵守。artemis `stock_zh_a_list.py` sink 时把 `code` 拆出 exchange 传入的做法**正确**。此为规范约束,非风险;实现时确保 phoenixA 侧统一 `ToUpper` 即可。
- **R3 — 多源表 source 处理 (非风险,留作去重)**: financial/corporate 多源,但每行记录都对应一个 `security_registry.id` (同一证券),多 source 只是同证券多份来源数据。`source` 保留在去重唯一键即可,不影响 security_id 设计 (§3.5)。
- **R5 — hardcode 用 const 预定义 (可控,但扩资产类型需升维度)**: 当前 `market=zh_a`/`asset_type=stock` 的 hardcode **必须引用 consts 枚举** (`consts.MARKET_ZH_A`/`ASSET_TYPE_STOCK`),禁止 magic string/number (§3.3)。注意扩展到 ETF/index 不是改 const 值,而是 asset_type 升为显式维度 (见 §3.3/review P1-7)。
- **R6 — 查询改 id (低风险)**: 查询尽量用 `security_id`/`category_id`,接口返回每行带 `id, symbol, ...` (id 稳妥)。`GET /by_security/{symbol}` 迁为 `/{security_id}`,无过渡问题。
- **R7 — base 后下游拿 id (靠 get/getAll + 缓存,非风险)**: artemis 写完 base 后下游**不必立即用 upsert 返回的 id** — 下游通过 `Get(exchange, symbol)`(asset_type 走 const) 或 `GetAll()` 查到 id,设计好缓存即可。upsert 响应是否返回 id 不是必须 (§5.2.2)。
- **R8 — baostock parent 反查 (低风险)**: `StockZhAHistParent`/`BsBalanceParent` 等加载时用 id 或 (exchange,symbol) 都能查到关键信息,与 baostock 的 `sh.600000` 格式转换 (`utils.py:206-216`) 衔接顺畅 — registry 同时持有 id 与 (exchange,symbol),怎么用都方便。
- **R9 — 不建真实 FK 约束 (设计决策,消除风险)**: 设计上用 `security_id`/`category_id` 作逻辑外键,**实践中 DDL 不写 `REFERENCES` 真实 FK**,只在 id 列上加索引。这同时消除: TimescaleDB hypertable FK 限制、写入性能损耗、重建复杂性。hypertable (industry_weight/industry_daily/bars_*) 无需担心 FK 问题。
- **R11 — 测试覆盖 (须强化)**: 多个 controller_test 存在,历史上 indate/outdate bug 因测试未断言而漏 (v0.38.3)。改造须同步强化测试,尤其 security_id 解析、多源去重、JOIN 派生。

### 6.bis 改造前只读数据校验 SQL (供重建后导入验证用)

> 因全量重建,这些 SQL 主要用于**重建后导入数据验证**(确认 id 分配、自然键唯一、多源去重正确),而非历史 backfill 风险排查。

```sql
-- (1) security_registry 自然键 (exchange,asset_type,symbol) 唯一性
SELECT exchange, asset_type, symbol, COUNT(*)
FROM ods.security_registry
GROUP BY exchange, asset_type, symbol
HAVING COUNT(*) > 1;

-- (2) exchange 取值规范 (应全大写 SH/SZ/BJ)
SELECT exchange, COUNT(*) FROM ods.security_registry GROUP BY exchange ORDER BY 2 DESC;

-- (3) 下游表 security_id 均能 resolve (以 financial_statement 为例,无 orphan)
SELECT fs.security_id, COUNT(*)
FROM ods.financial_statement fs
LEFT JOIN ods.security_registry sr ON sr.id = fs.security_id
WHERE sr.id IS NULL
GROUP BY fs.security_id;

-- (4) 多源表去重正确 (同证券同报表期,不同 source 各一行)
SELECT security_id, reporting_period, source, COUNT(*)
FROM ods.financial_statement
GROUP BY security_id, reporting_period, source
HAVING COUNT(*) > 1;
```

> cthulhu 间接暴露已并入 §5.3 (review P1-2): workbench/factor/BI 页面经 artemis 透传,是否改取决于 artemis 对前端是否保留 symbol 兼容层 (本项目 API 不双轨,故 artemis/cthulhu 须同步改)。

---

## 7. 改动成本估算 (粗粒度)

| 模块 | 文件量 | 复杂度 | 说明 |
|---|---|---|---|
| phoenixA migration | 1 (直接改 0001_ods.sql) | 中 | security_registry 加 id + 各表用 id 列直接替换冗余列;不建真实 FK 只加索引 (§6 R9);全量重建重导无 backfill |
| phoenixA model | ~8 文件 | 中 | security + 6 数据表 + taxonomy |
| phoenixA dao | ~8 文件 | **高** | security_dao OnConflict+resolve;taxonomy_dao JOIN 重写;各表 WHERE/OnConflict |
| phoenixA service/controller | ~16 文件 | 中-高 | API shape 迁移;缓存 key |
| phoenixA catalog/openapi/test | ~5 文件 | 中 | CrossRefs 元数据;openapi;controller_test |
| artemis client | 1 (`phoenixA_client.py`) | **高** | 唯一 chokepoint,所有 read/write 方法 |
| artemis 下载任务 | ~15 文件 (`download/zh/`) | 中 | base task 拿 id;依赖任务传 id;bars 物理表不动但 bars 任务契约迁 security_id |
| artemis factor_engine/BI | ~6 文件 | 中-高 | phoenixa_provider + bi/* (workbench 本批 scope-out,不计入) |
| 文档同步 | 多 | 低 | tables_description/api_biz_data_description/DATA_TABLES_REFERENCE |

总体: **中大型改造**,集中在 phoenixA dao 层与 artemis client。无 backfill 脚本需求 (全量重建重导,见 §5.1.1)。cronjob/atlas 不改,cthulhu 经 artemis 间接改,爆破半径可控。

---

## 8. 待确认问题 (已全部闭环, 2026-07-02 用户拍板)

| # | 问题 | 决策 |
|---|---|---|
| 1 | base 任务是否升级 `get_code_info + get_stock_basic` | **暂不升级** — base 任务保持 `get_code_info` 单端点;`full_name/list_date/delist_date/status` 仍为预留空列 (§4.1)。后续需要时再单独评估接入 `get_stock_basic`(§3.5.2.9)。 |
| 2 | factor_engine/BI 结果行 key + artemis 对前端契约是否改 security_id | **全部升级** — artemis client、factor_engine、BI、cthulhu 的 factor/BI 前端契约从 symbol 迁 security_id (含 bars API/artemis bars 调用,§3.2)。**workbench 本批 scope-out** (见 Q4)。 |
| 3 | `corporate_action` 是否真多源 | **是,真多源** — amazing_data (dividend/right_issue) + baostock (bs_dividend),`source` 留在去重唯一键 (§3.5)。 |
| 4 | `strategy_run_summary` 是否纳入本次改造 | **暂不纳入,以后重做** — 本批 ODS FK 改造不含;该表未来可能整体重做,届时再决定 security_id + symbol 快照策略 (§5.3.bis)。 |
| 5 | exchange 是否定义为全局稳定码枚举 | **是,枚举** — `exchange` 定义为全局稳定码,落入 `govern.data_enum_dictionary` (`enum_name='exchange'`);`market`(业务分区) 与 `exchange`(交易场所) 区分治理 (§3.4)。 |

### 8.bis 设计边界说明 (应 review P1-1/P1-4/P1-5/P0-2, 需用户确认)

1. **BIGSERIAL id 的重建边界 (P1-1)** — `security_id`/`category_id` 是 `BIGSERIAL`,**只在当前重建周期内稳定**;重建后 id 值随导入顺序可能重分配,跨重建边界的引用会失效。
   - 接受此边界 (本项目全量重建重导): 每次重建**必须同步清理** Redis 缓存、artemis 内存/文件缓存、factor store、cthulhu 前端本地状态、保存的任务参数和 URL deep link。
   - 若未来需跨重建稳定引用: 引入 `security_uid`/`category_uid` (由自然键确定性生成),`BIGSERIAL id` 继续作内部 join key。本批不引入。
   - "响应每行返回 `id, symbol`"的"id 稳妥"仅限**单次库内 join**;跨重建/跨系统缓存/前端持久链接不稳妥。

2. **source 保留策略 (P1-4)** — `source` 是数据血缘(provenance),非证券身份冗余。表级决策:
   - `symbol/market` 由 `security_id` 替换 (identity 规范化)。
   - `source` **默认保留**在 ODS 落地表 (多源表参与去重,单源表留作血缘)。
   - 例外: `bars_ext_baostock_*` 已用表名编码 source,可不存 source 列。

3. **base 元数据不升级的业务风险 (P1-5)** — base 任务暂不接 `get_stock_basic`,`list_date/delist_date/status` 仍空。**实测影响**: artemis factor engine `PhoenixADataProvider._security_active_as_of` (`phoenixa_provider.py:503-510`) 读 `list_date/delist_date` 做 as-of 过滤,空列会导致 `get_active_symbols` **不按上市/退市日期过滤** → 历史回测有 **survivorship bias** (退市证券、历史上市前过滤不可靠)。
   - 建议把 base registry 拆两层: **identity base** (本批最低要求,只需三元组) + **metadata enrichment** (接 get_stock_basic 补上市/退市/全称,供 factor engine/历史回测)。
   - 本批不做 enrichment,则须列为**已知业务风险**,而非仅"预留空列"。

4. **bars API 契约 (P0-2,已拍板)** — 见 §3.2。bars 存储**永久**保持 symbol;bars **API/artemis 契约迁 security_id** (用户确认: caller 传 security_id + period + adjust,phoenixA 内部 resolve 出 symbol 查物理表)。

5. **resolve 语义 (P1-6)** — artemis 显式参数路径需重新定义 resolve 边界: 用户传 `security_ids` 时 artemis 反解为 vendor code (`sz.000001`/`000001.SZ`) 调 SDK;是否仍允许 `symbols+exchange` 便捷输入 (应先 resolve 成 security_id 再入统一链);传入证券不在 registry 时是任务失败还是自动 upsert registry。建议阶段 1 增加 `resolve_securities` 能力 (非仅 getAll 本地拼)。

> 其他已闭环 (前轮拍板): 自然键三元组 `(exchange,asset_type,symbol)` (§3.1);全量重建重导不做增量/双轨 (§5.1.1);不建真实 FK (§6 R9);hardcode 须用 consts 且扩资产类型时升为显式维度 (§3.3);API 直接迁 security_id 不并存 (§3.6);中间表派生消除 JOIN、id 解析走缓存 + path scope + orphan 拒绝 (§2.3)。

---

## 9. 分阶段改造计划 (建议)

> 原则: 全量重建重导,每阶段改 DDL + 代码,重建库验证;base 元数据先行。
> **不双轨、不留 legacy、不增量迁移** — 每阶段产出的 DDL/代码即终态。

### 阶段 0 — 枚举 govern 化 + const 规范化 (独立可先行,不阻塞)
- 把 `asset_type`/`exchange`/`source` 落入 `govern.data_enum_dictionary` (`source='phoenixa'` 元枚举行);`exchange` 定义为**全局稳定码** (§8 Q5)。
- 代码侧 const 规范化: 所有 `market`/`asset_type` 取值引用 `consts.MARKET_ZH_A`/`ASSET_TYPE_STOCK`,消除散落 magic string (§3.3)。
- phoenixA 侧提供 enum 读取 API (若未有)。
- 价值: 为 security_registry 与 bars 表名拼接提供受控词表 + 代码侧可溯源。零破坏。
- 成本: 低。

### 阶段 1 — security_registry 加代理 id (重建即到位)
- migration: 直接改 `0001_ods.sql`,`security_registry` 加 `id BIGSERIAL PK`,自然键 `UNIQUE (exchange, asset_type, symbol)`;`market` 为普通列。
- `security_dao`: OnConflict 按自然键 `(exchange,asset_type,symbol)` 去重 (id 自增);保留 `Get(exchange, symbol)`(asset_type 走 const)/`GetAll()`(配缓存) 供 artemis 解析 (§6 R7/R8)。
- base 任务**保持 `get_code_info` 单端点** (§8 Q1 暂不升级);full_name/list_date/delist_date/status 仍为预留空列。
- API: `/api/v2/securities/*` 直接迁 security_id (响应每行 `id, symbol, ...`),不双轨 (§3.6)。
- 价值: 建立 id 体系。重建后由 STOCK_ZH_A_LIST 重新导入。
- 验证: id 唯一性、自然键唯一、upsert 幂等。

### 阶段 2 — taxonomy 链路引用 id (用户 1/2/3 点 + §2.5 FK 压缩 + §2.3 JOIN 消除)
- migration: 直接改 DDL,`taxonomy_security_map`/`industry_constituent`/`industry_weight`/`industry_daily` 用 `security_id`/`category_id` **直接替换**冗余列 (不留 legacy,见 §2.5)。`taxonomy_security_map` 退化为纯中间表 `(security_id, category_id)`。
- id 解析缓存: 成分股 upsert 时用 redis/内存缓存解析 `index_code`→`category_id`、`CON_CODE`→`security_id` (taxonomy_category + security_registry 全量缓存,§6 R7)。
- `taxonomy_dao`: `SyncMappingsFromConstituents` **消除 JOIN**,改为单表 `SELECT DISTINCT security_id, category_id FROM industry_constituent` (§2.3);所有查询改 `WHERE security_id=?`/`category_id=?`。
- API: `/api/v2/taxonomy/*` 直接迁 security_id/category_id,不双轨。
- artemis: `StockZHAIndustryConstituentSWHY` + `STOCK_ZH_A_MKT_CATEGORY_SWHY` + weight/daily 任务适配 (带 id)。
- 价值: 落地用户核心诉求 (1/2/3);中间表 JOIN 消除;表结构规范化压缩。
- 验证: SyncMappings 派生正确 (无 JOIN)、缓存解析正确、§6.bis 校验 SQL 通过。

### 阶段 3 — 数据表 (financial/corporate/equity/adjust_factor/long_hu_bang) 引用 id
- migration: 各表用 `security_id` **直接替换** symbol/market (不留 legacy);多源表 (financial/corporate,§8 Q3) 保留 `source` (§3.5)。
- API `/api/v2/financial|corporate-action|equity-structure|adjust-factors|long-hu-bang` 直接迁 security_id,不双轨。
- artemis 各下载任务 + factor_engine/BI 适配。
- 价值: 全链路 security_id 化。
- bars_* **物理表不动** (§3.2 永久存储特例);但 bars API/artemis 契约迁 security_id (在阶段 4 完成)。
- 验证: §6.bis 多源去重校验、orphan 校验。

### 阶段 4 — 业务层全链路迁移 (§8 Q2 全部升级)
- artemis `PhoenixAClient` 全部 read/write 走 security_id (含 bars API: security_id + period + adjust 入参,phoenixA 内部 resolve,§3.2)。
- factor_engine 内部 key 从 symbol 改 security_id。
- BI 接口 key 迁 security_id。
- cthulhu factor/BI 页面同步 (artemis 对前端契约改, §5.3)。
- **workbench + `govern.strategy_run_summary` 本批 scope-out** (§8 Q4: workbench market-data/backtest/strategy_run 暂不改,未来按 id 方向迁;不影响 ODS/API/factor/BI 主链路)。
- 缓存 key 按 security_id/category_id 重做;**重建后必须清理** Redis/arthemis 缓存/factor store/前端本地状态 (§8.bis-1)。
- 风险最高,需充分测试 (R11)。

### 9.bis 重建导入顺序 (应 review §4.4)

全量重建重导须按依赖顺序,前置缺失则下游 upsert 拒绝 (§2.3 resolve 失败语义):
1. govern enum (asset_type/exchange/market/source)
2. security_registry identity base (STOCK_ZH_A_LIST, get_code_info)
3. taxonomy_category (SWHY/MAIRUI categories)
4. industry_constituent / industry_weight / industry_daily (写入时 resolve category_id + security_id)
5. taxonomy_security_map sync (单表 SELECT DISTINCT,无 JOIN;`WHERE category_id IN (...)` 限定 path scope)
6. financial / corporate / equity / adjust_factor / long_hu_bang
7. bars (stock/index/ext — 任务/API 契约传 security_id,写物理表用 resolved symbol)
8. factor / BI smoke test (验证 security_id 全链路)
9. workbench / strategy_run 标注本批 scope-out

> 校验: 每步导入后跑 §6.bis 校验 SQL (自然键唯一、exchange 规范、无 orphan、多源去重)。

> 无"阶段 5 清理 legacy 列" — 因每阶段已直接替换不留 legacy,bars 为永久存储特例已文档化,hardcode 用 const 已在阶段 0 规范化。后续 ETF/index 落地时 asset_type 从默认 const 升为显式维度 (§3.3),非专门清理阶段。

---

## 10. 终态契约 artifact (应 review §4)

### 10.a 终态 DDL 表格

> 全量重建,直接改 `0001_ods.sql`/`0002_dwd.sql`/`0003_govern.sql`。下表为重建后目标结构。`id`/`security_id`/`category_id` 均为 BIGSERIAL/BIGINT,**不建真实 FK 约束** (§6 R9),只加索引。`id` 随重建重分配,仅当前重建周期内稳定 (§8.bis-1)。

#### govern 层 (0003_govern.sql)

| 表 | 列 (终态) | 唯一键 | 索引 | source | 说明 |
|---|---|---|---|---|---|
| `govern.data_enum_dictionary` | id, contract_version, source, enum_name, code, label_zh, description, sort_order, source_doc, review_status, deprecated, created_at, updated_at | `uk_data_enum_dict (source, enum_name, code, contract_version)` | `(source, enum_name, sort_order, code)` | — | 新增 enum_name=asset_type/exchange/market/source 行 (§3.4) |
| `govern.security_registry` → **移到 ods** | — | — | — | — | 见 ods 行 (主数据归 ods) |

#### ods 层 (0001_ods.sql)

| 表 | 列 (终态) | 唯一键/PK | 索引 | source 列 | logical FK |
|---|---|---|---|---|---|
| `ods.security_registry` | **id**, exchange, asset_type, symbol, market, name, full_name, status, list_date, delist_date, created_at, updated_at | PK: id; UNIQUE: `(exchange, asset_type, symbol)` | `(exchange)`、`(asset_type, market)`、partial `(status) WHERE status!='active'` | 无 (单源主数据) | — (基表,被引用) |
| `ods.taxonomy_category` | id, source, taxonomy, market, code, name, parent_code, index_code, level, is_leaf, attrs_json, created_at, updated_at | PK: id; UNIQUE: `(source, taxonomy, market, code)` | `(source,taxonomy,market,parent_code)`、`(source,taxonomy,index_code)` | 保留 (基表身份) | — (基表,被引用) |
| `ods.taxonomy_security_map` | **security_id, category_id**, created_at, updated_at | PK/UNIQUE: `(security_id, category_id)` | `(security_id)`、`(category_id)` | 无 (经 category_id 反查) | → security_registry.id, taxonomy_category.id |
| `ods.industry_constituent` | id, **category_id, security_id**, in_date, out_date, created_at, updated_at | UNIQUE: `(category_id, security_id)` | `(security_id)`、`(category_id)` | 无 (经 category_id 反查) | → security_registry.id, taxonomy_category.id |
| `ods.industry_weight` | **category_id, security_id**, trade_date, weight, created_at, updated_at | PK: `(category_id, security_id, trade_date)` | `(category_id, trade_date)`、`(security_id, trade_date)` | 无 | → security_registry.id, taxonomy_category.id (hypertable, 无真实 FK) |
| `ods.industry_daily` | **category_id**, trade_date, open, high, close, low, pre_close, amount, volume, pb, pe, total_cap, a_float_cap, created_at, updated_at | PK: `(category_id, trade_date)` | `(category_id, trade_date)` | 无 | → taxonomy_category.id (hypertable, 无 symbol) |
| `ods.financial_statement` | id, **security_id**, source, statement_type, reporting_period, report_type, statement_code, security_name, ann_date, actual_ann_date, comp_type_code, data_json, created_at, updated_at | UNIQUE: `(security_id, source, statement_type, reporting_period, report_type, statement_code)` | `(security_id, statement_type)`、`(reporting_period)`、GIN(data_json) | **保留** (多源,在唯一键) | → security_registry.id |
| `ods.corporate_action` | id, **security_id**, source, action_type, report_period, ann_date, progress_code, data_json, created_at, updated_at | UNIQUE: `(security_id, source, action_type, report_period, ann_date)` | `(security_id, action_type)`、GIN(data_json) | **保留** (多源,在唯一键) | → security_registry.id |
| `ods.equity_structure` | id, **security_id**, source, ann_date, change_date, current_sign, is_valid, data_json, created_at, updated_at | UNIQUE: `(security_id, source, ann_date, change_date)` | `(security_id, change_date)`、GIN(data_json) | **保留** (血缘) | → security_registry.id |
| `ods.adjust_factor` | id, **security_id**, source, divid_operate_date, fore_adjust_factor, back_adjust_factor, adjust_factor | UNIQUE: `(security_id, source, divid_operate_date)` | `(security_id, divid_operate_date DESC)` | **保留** (血缘) | → security_registry.id |
| `ods.long_hu_bang` | id, **security_id**, source, trade_date, security_name, reason_type, reason_type_name, trader_name, flow_mark, change_range, buy_amount, sell_amount, total_amount, total_volume, created_at, updated_at | UNIQUE: `(security_id, source, trade_date, reason_type, trader_name, flow_mark)` | `(security_id, trade_date DESC)`、`(reason_type, trade_date)` | **保留** (血缘) | → security_registry.id |
| `ods.bars_stock_zh_a_daily_{nf,hfq}` | symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg | PK: `(symbol, trade_date)` | `(trade_date)`、`(symbol)` | 无 (表名编码) | 无 (永久存储特例,§3.2) |
| `ods.bars_index_zh_a_daily_nf` | symbol, trade_date, open, high, low, close, volume, amount, preclose, pct_chg | PK: `(symbol, trade_date)` | `(trade_date)`、`(symbol)` | 无 | 无 |
| `ods.bars_ext_baostock_stock_zh_a_daily` | symbol, trade_date, turn, pe_ttm, ps_ttm, pb_mrq, pcf_ncf_ttm | PK: `(symbol, trade_date)` | `(trade_date)`、`(symbol)` | 无 (表名编码) | 无 |

#### dwd 层 (0002_dwd.sql)

| 表 | 列 (终态) | 唯一键 | 说明 |
|---|---|---|---|
| `dwd.taxonomy_category_derived_flags` | id, source, taxonomy, market, code, derived_flags, created_at, updated_at | `uk_tcdf_src_tax_mkt_code (source, taxonomy, market, code)` | 不变 (派生标记,仍用自然键,不引入 category_id — 它是 taxonomy_category 的派生,可后续加 category_id 优化但非必须) |

> **hypertable** (industry_weight/industry_daily/bars_*): `create_hypertable(..., 'trade_date', chunk_time_interval=>INTERVAL '1 year')` 保留;因不建真实 FK,无 TimescaleDB FK 限制 (§6 R9)。
> **created_at/updated_at drift** (§2.bis): `taxonomy_security_map` 终态 DDL **补上** created_at/updated_at 列,与 model/DAO 对齐。

### 10.b API 契约矩阵

> 对外 `/api/v2/*` 直接迁 security_id,不双轨 (§3.6)。响应每行返回 `security_id` (+ 可附 symbol/exchange/asset_type 作展示)。workbench 相关端点本批 scope-out (标 ⏸)。

| 端点 | 旧入参 (symbol 形态) | 新入参 (security_id 形态) | 响应 | 备注 |
|---|---|---|---|---|
| `GET /api/v2/securities/` | `?symbol=&exchange=&asset_type=&market=` | `?security_id=&exchange=&asset_type=&market=` (id 优先,自然键仍可筛) | `[{security_id, symbol, exchange, asset_type, market, name, ...}]` | List |
| `POST /api/v2/securities/upsert` | body `[{symbol, exchange, ...}]` | body `[{symbol, exchange, asset_type, market, name, ...}]` (按自然键 upsert,id 自增) | `{rows: N}` (不必返 id,§6 R7) | 自然键 upsert |
| `GET /api/v2/securities/{symbol}` | path `{symbol}` | path `{security_id}` | `{security_id, symbol, ...}` | Get |
| `GET /api/v2/securities/count` | `?asset_type=&market=` | `?asset_type=&market=` | `{count: N}` | 不变 |
| `DELETE /api/v2/securities/all` | `?asset_type=&market=` | `?asset_type=&market=` | `{rows: N}` | 不变 |
| `GET /api/v2/bars/{asset_type}/{market}` | `?symbol=&start_date=&end_date=&period=&adjust=` | `?security_id=&period=&adjust=&start_date=&end_date=` (asset_type/market 由 resolve 得,但仍可在 path;period/adjust 必传) | `[{security_id, symbol, trade_date, OHLCV}]` | §3.2: 内部 resolve→table_resolver→查 symbol |
| `POST /api/v2/bars/{asset_type}/{market}/upsert` | body `{meta:{period,adjust,source}, bars:[{symbol,...}]}` | body `{meta:{period,adjust,source}, bars:[{security_id,...}]}` | `{status:ok}` | phoenixA resolve 出 symbol 写物理表 |
| `GET /api/v2/bars/{asset_type}/{market}/last_update` | `?symbols=&period=&adjust=` | `?security_ids=&period=&adjust=` | `[{security_id, symbol, last_update}]` | 批量 |
| `GET /api/v2/taxonomy/by_security/{symbol}` | path `{symbol}` | path `{security_id}` | `[{security_id, category_id, category_name, ...}]` | ListMappingsBySecurity |
| `POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/upsert` | body `[{source,taxonomy,category_code,symbol,...}]` | body `[{security_id, category_id}]` | `{status:ok}` | |
| `POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_symbol` | body `{symbol:[categoryCodes]}` | body `{security_id:[category_ids]}` | `{status:ok}` | |
| `POST /api/v2/taxonomy/{source}/{taxonomy}/mapping/replace/by_category` | body `{categoryCode:[symbols]}` | body `{category_id:[security_ids]}` | `{status:ok}` | |
| `GET /api/v2/taxonomy/{source}/{taxonomy}/mapping/by_category/{categoryCode}` | path `{categoryCode}` | path `{category_id}` | `[{security_id, category_id}]` | |
| `DELETE /api/v2/taxonomy/{source}/{taxonomy}/mapping/{categoryCode}/{symbol}` | path `{categoryCode}/{symbol}` | path `{category_id}/{security_id}` | 204 | |
| `POST /api/v2/taxonomy/{source}/{taxonomy}/{market}/mapping/sync_from_constituents` | path (source/taxonomy/market) | path 不变 (resolve 成 category_id 范围,§2.3) | `{rows_synced: N}` | 单表 SELECT DISTINCT,无 JOIN |
| `GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories` | `?parent_code=&level=` | `?parent_code=&level=` (taxonomy_category 仍用自然键,未迁 id) | `{list:[{id, source, taxonomy, code, ...}]}` | category 是基表,保留自然身份 |
| `GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_stock/{con_code}` | path `{con_code}` | path `{security_id}` | `[{category_id, security_id, in_date, out_date}]` | |
| `GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/by_index/{indexCode}` | path `{indexCode}` | path `{category_id}` (或保留 indexCode 经 resolve) | `{list:[{category_id, security_id, ...}]}` | |
| `POST /api/v2/financial/{source}/{statement_type}/upsert` | body `[{symbol, ...}]` | body `[{security_id, ...}]` | `{status:ok,count:N}` | 多源 source 在 path+body |
| `GET /api/v2/financial/{source}/{statement_type}` | `?symbol=&symbols=` | `?security_id=&security_ids=` | rows 含 security_id | |
| `POST /api/v2/corporate-action/{source}/{action_type}/upsert` | body `[{symbol,...}]` | body `[{security_id,...}]` | `{status:ok,count:N}` | |
| `GET /api/v2/corporate-action/{source}/{action_type}` | `?symbol=&symbols=` | `?security_id=&security_ids=` | rows 含 security_id | |
| `POST /api/v2/equity-structure/{source}/upsert` | body `[{symbol,...}]` | body `[{security_id,...}]` | `{status:ok,count:N}` | |
| `GET /api/v2/equity-structure/{source}` | `?symbol=&symbols=` | `?security_id=&security_ids=` | rows 含 security_id | |
| `POST /api/v2/adjust-factors/{source}/upsert` | body `[{symbol,...}]` | body `[{security_id,...}]` | `{status:ok,count:N}` | |
| `GET /api/v2/adjust-factors/{source}` | `?symbol=&symbols=` | `?security_id=&security_ids=` | rows 含 security_id | |
| `POST /api/v2/long-hu-bang/{source}/upsert` | body `[{symbol,...}]` | body `[{security_id,...}]` | `{status:ok,count:N}` | |
| `GET /api/v2/long-hu-bang/{source}` | `?symbol=&symbols=` | `?security_id=&security_ids=` | rows 含 security_id | |
| `GET /api/v2/catalog/securities/{symbol}/datasets/summary` | path `{symbol}` | path `{security_id}` | coverage summary | GetSymbolCoverage |
| `POST /api/v1/strategy/run/summary/upsert` | body `{symbol,...}` | **⏸ 本批 scope-out** (保持 symbol) | — | §8 Q4,workbench/strategy_run 不动 |
| `GET /api/v1/strategy/run/{run_id}` | — | **⏸ 本批 scope-out** | — | |

> ⏸ = workbench/strategy_run 本批 scope-out,未来按 id 方向迁。
> legacy v1 代理路由 (router_v2.go:325-360) 同步迁或废弃。
> `openapi.yaml` 全量同步本表。

### 10.c resolve 语义

> 定义 security_id ↔ 自然键 ↔ vendor code 之间的解析边界与失败处理。

**解析方向与时机**:

| 方向 | 触发时机 | 执行方 | 输入→输出 |
|---|---|---|---|
| 自然键→security_id | artemis 下载任务加载证券池、phoenixA 写入逻辑FK表前 | phoenixA (缓存) | `(exchange, asset_type, symbol)` → `security_id` |
| security_id→自然键 | phoenixA bars controller 选物理表、artemis 调 SDK 前 | phoenixA (缓存) | `security_id` → `(symbol, exchange, asset_type, market)` |
| security_id→vendor code | artemis 调 baostock/amazingData 前 | artemis | `security_id` → `(symbol, exchange)` → `sz.000001` / `000001.SZ` |
| index_code→category_id | industry_constituent upsert 写入前 | phoenixA (缓存) | `index_code` (+source/taxonomy/market) → `category_id` |
| (source,taxonomy,market)→category_id 集 | sync_from_constituents path scope | phoenixA (缓存) | path 三元组 → `category_id IN (...)` 范围 |

**解析能力 (phoenixA 侧,阶段 1 提供)**:
- `GetSecurity(exchange, asset_type, symbol) → {id, ...}` (asset_type 当前走 const `ASSET_TYPE_STOCK`,§3.3)
- `GetAllSecurities() → map[(exchange,asset_type,symbol)]id` (全量缓存,§6 R7)
- `ResolveSecurityID(security_id) → (symbol, exchange, asset_type, market)` (反向)
- `ResolveCategoryID(index_code, source, taxonomy, market) → category_id`
- 缓存: redis + 进程内,全量 security_registry + taxonomy_category 缓存,TTL + upsert 失效。

**artemis 侧 resolve (阶段 1 增加,§8.bis-5)**:
- `resolve_securities(security_ids) → [(symbol, exchange, ...)]` (批量反解,调 phoenixA 或本地缓存)
- 显式参数: 用户传 `security_ids` 为主;是否仍允许 `symbols+exchange` 便捷输入 — **允许,但先 resolve 成 security_id 再入统一链** (便捷输入非主契约)。
- 传入证券不在 registry: **任务失败** (不自动 upsert registry;registry 只由 STOCK_ZH_A_LIST 维护)。

**resolve 失败语义 (§2.3,§6 R9 应用层 orphan 防线)**:
- 写入逻辑 FK 表时,phoenixA **必须先校验 security_id/category_id 存在**。
- 解析失败 (id 不存在/缓存未命中且 DB 无此行): **拒绝该行**,不静默写 NULL/orphan id。
- 批量 upsert 返回 **per-row rejected list**: `{index, natural_key, reason}` (如 `security_id 12345 not found` / `category_id missing, taxonomy_category not imported`)。
- 前置依赖缺失 (如 taxonomy_category 未导入时写 industry_constituent): **整批失败**,响应提示前置依赖缺失。
- 缓存与 DB 不一致 (重建后旧 id 失效): 写入校验会因 id 不存在而 reject,触发缓存清理 + 重新 resolve (§8.bis-1 重建边界)。

**bars 查询 resolve 链 (§3.2)**:
```
caller (security_id, period, adjust)
  → phoenixA: ResolveSecurityID(security_id) → (symbol, asset_type, market, exchange)
  → table_resolver(asset_type, market, period, adjust) → bars 物理表名
  → bars DAO: WHERE symbol = ? AND trade_date BETWEEN ? AND ?
  → 响应附 security_id (由 (exchange,asset_type,symbol) 反查 id,或查询时已持有)
```

### 10.d 实施前须闭合的真实代码路径 (应 review 第五版 P1)

> 以下不是文档残留,而是会导致**运行时查询/写入失败**的真实路径,终态契约 §10.a-c 未覆盖,实施前必须纳入任务拆解。

#### 10.d.1 govern field dictionary / 0004 seed 的 MARKET_CODE→symbol (review P1-1) — 严重

- **问题**: `0004_govern_seed.sql:20` 把 `MARKET_CODE` 的 `canonical_field='symbol'`、`storage_location='top_level'`。`financial_statement`/`corporate_action`/`equity_structure`/`long_hu_bang` 等表终态删 `symbol` 列后,`field_dictionary_dao.ResolveFields` 对 top_level 字段直接当真实列 SELECT (field_dictionary_dao.go) → `fields=symbol` 或 raw explorer 选 `MARKET_CODE` **运行时查不存在的列**。
- **背景 — 谁在用 MARKET_CODE**: cthulhu "Raw Data Explorer" 页面 (`raw-data-explorer.page.ts:110`) 让用户浏览 phoenixA 实际存储的数据:用户选 dataset (如 balance_sheet) → 前端调 `/api/v2/catalog/datasets/{dataset}/fields` 拿字段列表 → 用户勾选字段 (如 `MARKET_CODE`) → 前端带 `fields=MARKET_CODE,...` 调 `/api/v2/financial/.../` → `ResolveFields` 查字典生成 `SELECT symbol, ...`。artemis dupont (`dupont.py:92`) 也用 `fields=` 但只拉 data_json 字段 (TOTAL_ASSETS 等),不碰 MARKET_CODE。
- **产品定位 (用户确认)**: Raw Data Explorer 浏览的是**系统里实际存储的数据**,不是 SDK 原始字段名透明翻译。`MARKET_CODE` (SDK 带后缀代码如 `600000.SH`) 的值进系统后已被 `security_id` 取代,表里不存在了。
- **方案 (据此定位决定,非 review 的 A/B)**:
  - **删除** 字典里 `MARKET_CODE → symbol` 这条登记 (以及各 dataset 里的重复行)。SDK 原始 `MARKET_CODE` 值进系统后不存在,前端字段列表不再出现它,诚实反映"系统实际存什么"。
  - **新增** 把 `security_id` 本身登记为一个 top_level 字段,明确 `raw_field='security_id'`、`canonical_field='security_id'`、`aliases=[]` (空别名,避免旧 `symbol`/`MARKET_CODE` 经 alias 继续被解析命中)、`storage_location='top_level'`、`value_type='integer'`。让前端字段列表出现 `security_id`,用户勾它即拿到证券标识。
  - 前端要显示 `600000.SH` 代码:用响应行附带的 symbol (§10.b 规定每行返 `security_id + symbol`),不需字典支持。**注意**: 该 symbol 只是 decoration/debug 展示字段,**不等于** `fields=symbol` 可选 — `fields=symbol` 仍返 400 (symbol 不是登记字段)。
  - **不引入** `storage_location='virtual'` (review 方案 B) — 现有 CHECK 约束 (`0003_govern.sql:141` 只允许 top_level/data_json)、DAO (`field_dictionary_dao.go:473` switch 仅两 case)、query builder (`query_helpers.go:51` SplitResolved) 均不支持 virtual,需新增一整套能力,工程量与本次目标不匹配。
  - **不采用** review 方案 A (MARKET_CODE→security_id 保留 top_level) — 语义错位:用户看到字段名 `MARKET_CODE` 却拿到数字 id,不如直接登记 `security_id` 字段诚实。
- **改造范围**:
  - `scripts/field_dictionary/amazing_data/*.jsonl` (seed 源): 删 `MARKET_CODE` 行,加 `security_id` top_level 行。
  - `generate_field_dictionary_from_docs.py`: 去掉 `MARKET_CODE` 的 top-level map 固定为 `symbol` 的逻辑。
  - `regenerate_seed_sql.py` → 重新生成 `0004_govern_seed.sql`。
- **value_type 同步 (review P2-2)**: 新增 `security_id` 字段 `value_type='integer'`;`source_value_type` 不填 (非 SDK 原始字段,是系统代理键)。
- **影响**: BI raw data explorer / field discovery / dupont 字段选择均依赖此字典,非纯文档同步;但 dupont 只用 data_json 字段不受影响。
- **测试 (review P2-3)**: `fields=security_id` 返回数字 id;旧 `fields=symbol` 或 `fields=MARKET_CODE` 返回 400 (unknown field);field discovery 列表含 security_id、不含 MARKET_CODE。

#### 10.d.2 bars upsert ext + write buffer resolve 时机 (review P1-2)

- **问题**: `BarsUpsertRequest` 有 `Bars` + `Ext` 两块 (`bars.go:45-49`),`StandardBar`/`BarsExtBaostock` 都是 `symbol+trade_date` 物理模型。`BarsController.Upsert` 在 write buffer 开启时 unmarshal 成 `[]StandardBar` 再 `BufferMgr.Submit` (`bars_controller.go:63`),buffer 异步 flush。终态契约只写 `bars:[{security_id}]`,未定义 ext 与 resolve 时机。
- **规则**:
  - bars 标准行 + ext 行 API 输入**统一用 `security_id`**。
  - phoenixA 在 **controller/service 入口**先批量 resolve 所有 `security_id` → 物理 `symbol`,**进入 DAO/write buffer 的对象必须是 resolved physical rows**。
  - **不要**把未校验的 `security_id` 延迟到异步 flush 才发现失败 (buffer 内 payload 已 resolved)。
  - write buffer key 仍按 table name 分组;`security_id` 不存在或 path mismatch 时按 §10.c reject 规则 (per-row rejected)。

#### 10.d.3 industry_weight / industry_daily write buffer 旧维度签名 (review P1-3)

- **问题**: `WriteBufferManager.SubmitIndustryWeights(source, taxonomy, market, weights)` / `SubmitIndustryDaily(...)` (`write_buffer.go:360,394`) 签名仍用旧维度,与终态表 (category_id/security_id) 不一致。
- **规则**:
  - buffer key 由 `category_id` (或 (source,taxonomy,market) resolved 后的 category 范围) 决定,不依赖表中已删的 source/taxonomy/market 列。
  - `industry_weight` / `industry_daily` 的 resolve (`index_code→category_id`、`symbol→security_id`) 须在 **controller/service 入口、进入 write buffer 前**完成 (与 bars 口径一致,§10.d.2);buffer 内 payload 必须已是 resolved physical rows,不把未校验 id 延迟到异步 flush 才暴露失败。
  - `write_buffer_test.go` 覆盖新 payload,否则 small batch 路径与 direct path 不一致。

#### 10.d.4 bars route {asset_type}/{market} 与 security_id resolve 双来源 (review P1-4)

- **问题**: §10.b 保留 `GET /api/v2/bars/{asset_type}/{market}?security_id=...`,同时 asset_type/market 由 resolve 得 — 双来源可能把同一 security_id 路由到错误物理表。
- **规则 (二选一,倾向前者)**:
  - (A) 保留 path,但 path 的 `asset_type/market` 必须与 `ResolveSecurityID(security_id)` 一致,**不一致返 400**。
  - (B) 新增 id-first 路由 `/api/v2/bars?security_id=&period=&adjust=`,旧 path 降为内部 table routing 逐步消失。

#### 10.d.5 dwd.taxonomy_category_derived_flags 自然键 — 显式 scope decision (review P2-2)

- 该表继续用 `(source,taxonomy,market,code)` 自然键,不引入 `category_id` (§10.a dwd 行)。这是**有意保留的 DWD 派生表设计** (它本身是 taxonomy_category 的派生,可后续优化为 `category_id + derived_flags`),非遗漏。未来可改,本批不动。

#### 10.d.6 测试清单补充 (review P2-3)

- **field dictionary / dynamic fields**: `fields=security_id` 返回数字 id;旧 `fields=symbol` 或 `fields=MARKET_CODE` **返回 400 (unknown field)** (不 reject 成虚拟 resolve)。
- **write buffer**: bars small batch + ext、industry_weight small batch、industry_daily small batch — 验证与 direct path 一样在落库前完成 id resolve。

---

## 11. 附录: 关键 file:line 索引

- security_registry DDL: `migrations/postgresql/security/0001_ods.sql:575-609`
- security_registry model: `internal/model/security.go:7-21`
- security upsert OnConflict: `internal/dao/security_dao.go:76-80`
- security Get (三元组): `internal/dao/security_dao.go:89`
- taxonomy_security_map model: `internal/model/taxonomy.go:27-38`
- SyncMappingsFromConstituents: `internal/dao/taxonomy_dao.go:180-200`
- ListMappingsBySymbol (单列 symbol): `internal/dao/taxonomy_dao.go:347-351`
- industry_constituent model: `internal/model/taxonomy.go:57-72`
- 各数据表 dao OnConflict: `financial_statement_dao.go:57-65` / `corporate_action_dao.go:57-63` / `equity_structure_dao.go:58-64` / `adjust_factor_dao.go:52-55` / `long_hu_bang_dao.go:52-58`
- bars table_resolver: `internal/dao/table_resolver.go` (整文件)
- bars StandardBar model: `internal/model/bars.go:7-18`
- catalog CrossRefs (描述性): `internal/service/catalog_service.go:566,583,593`
- artemis phoenixA client: `app/projects/artemis/artemis/core/clients/phoenixA_client.py`
- artemis get_code_list_from_phoenixa: `app/projects/artemis/.../download/zh/utils.py:138-175`
- artemis STOCK_ZH_A_LIST sink: `app/projects/artemis/.../download/zh/stock_zh_a_list.py`
- cronjob 调度文档: `app/projects/cronjob/docs/2026-05-07 CONFIG_OF_CRONJOB_AND_ARTEMIS.md`
- SDK doc: `docs/third_party_sdk/AmazingData_development_guide.md` (§3.5.2.1 / §3.5.13.1 / §3.5.13.2)
- 枚举 consts: `internal/consts/asset_type.go` / `data_source.go` / `market.go`
- data_enum_dictionary DDL: `migrations/postgresql/security/0003_govern.sql:162-180`
- field dictionary seed (MARKET_CODE→symbol): `migrations/postgresql/security/0004_govern_seed.sql:20` + `scripts/field_dictionary/amazing_data/*.jsonl` + `internal/dao/field_dictionary_dao.go` (ResolveFields top_level)
- bars upsert request/ext: `internal/model/bars.go:44-60` + `internal/controller/bars_controller.go:39-63`
- write buffer (bars/industry): `internal/buffer/write_buffer.go` (SubmitIndustryWeights:360 / SubmitIndustryDaily:394)
