# Industry Data & Taxonomy 迭代计划

> Date: 2026-05-07  
> Scope: Artemis (下载/ETL) + PhoenixA (存储/API)  
> Status: **Implementing**

### Key Decisions
1. **security_registry 不加 id** — 当前 `(symbol, asset_type, market)` 复合主键足够。industry 表通过 `symbol` + `market` 逻辑关联即可，无需物理 FK。如果未来需要单列 FK，再加 surrogate id。
2. **存量数据可以删除** — 所有 taxonomy/industry 表 DROP + 重建，无需 ALTER 迁移。Artemis 重新拉取数据。
3. **con_code 保留** — `industry_constituent` 和 `industry_weight` 保留 `con_code` 存原始值，新增 `symbol` 存纯代码。

---

## 1. 现状问题总结

### 1.1 Source 命名不一致
| 表 | 当前 source 值 | 实际数据来源 |
|---|---|---|
| `taxonomy_category` | `swhy` | AmazingData SDK |
| `industry_constituent` | `amazing_data` | AmazingData SDK |
| `industry_weight` | `amazing_data` | AmazingData SDK |
| `industry_daily` | `amazing_data` | AmazingData SDK |

**问题**: `taxonomy_category` 的 source 用了 `swhy`（分类体系名），其余用 `amazing_data`（数据供应商名）。两者混用导致无法通过统一 source 关联查询。

**结论**: source 应该统一表达**数据供应商**，分类体系标识应单独建模。

### 1.2 taxonomy_category 字段问题
- `parent_code` 为空 — `StockZHAMarketCategorySWHY.post_process` 中虽有 `code_map` 逻辑推算 parent，但 SWHY 的 `INDUSTRY_CODE` 层级截断规则未能正确匹配所有情况
- `code` 字段存的是 `INDUSTRY_CODE`（如 `110000`），而 `INDEX_CODE`（如 `801010.SI`）被塞到了 `attrs_json` 里 — 这两个是独立概念，应分开存

### 1.3 con_code 未关联 security_registry
- `industry_constituent.con_code` 存的是 SDK 返回的原始代码（如 `603648.SH`），这是 **exchange.symbol** 格式
- `security_registry` 的 PK 是 `(symbol, asset_type, market)`，symbol 是纯代码（如 `603648`）
- 没有外键或字段能直接 JOIN

### 1.4 缺少多市场支持
- 当前 industry 相关表没有 `market` 字段，默认全是 A 股
- 未来 US/JP/EUR 市场的行业分类无法区分

### 1.5 taxonomy_category 缺少分类体系标识
- SWHY（申万宏源）、CITIC（中信）、GICS 等不同分类体系没有专门字段标识
- 目前 `source` 混用了数据供应商和分类体系两个概念

---

## 2. 目标数据模型

### 2.1 设计原则
1. **source** = 数据供应商（amazing_data / tushare / mairui / baostock）
2. **taxonomy** = 分类体系（swhy / citic / gics / concept / region）— 新增字段
3. **market** = 市场（zh_a / us / jp / hk）— 新增字段
4. **con_code → symbol** = 成分股代码统一使用 security_registry 的纯 symbol
5. **industry_code vs index_code** = 行业代码（分类树节点）与行业指数代码（可交易指数）分开存

### 2.2 taxonomy_category 表改造

```sql
-- 新增字段: taxonomy, market, index_code
-- code 仍然存 industry_code（分类树节点标识）
-- index_code 存行业指数代码（可交易指数，如 801010.SI）

ALTER TABLE taxonomy_category
  ADD COLUMN taxonomy VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类体系: swhy/citic/gics/concept/region' AFTER source,
  ADD COLUMN market   VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场: zh_a/us/jp/hk' AFTER taxonomy,
  ADD COLUMN index_code VARCHAR(64) NULL COMMENT '关联的行业指数代码（若有）' AFTER parent_code;

-- 调整唯一键: source + taxonomy + market + code
ALTER TABLE taxonomy_category
  DROP INDEX uk_source_code,
  ADD UNIQUE KEY uk_src_tax_mkt_code (source, taxonomy, market, code);

-- 调整 parent 索引
ALTER TABLE taxonomy_category
  DROP INDEX idx_parent,
  ADD KEY idx_parent (source, taxonomy, market, parent_code);

ALTER TABLE taxonomy_category
  DROP INDEX idx_level,
  ADD KEY idx_level (source, taxonomy, market, level);
```

### 2.3 industry_constituent 表改造

```sql
-- con_code → symbol (纯代码), 新增 market
-- 保留 con_code_raw 记录原始值便于排查

ALTER TABLE industry_constituent
  ADD COLUMN taxonomy VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类体系' AFTER source,
  ADD COLUMN market   VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场' AFTER taxonomy,
  ADD COLUMN symbol   VARCHAR(32) NOT NULL DEFAULT '' COMMENT '成分股代码(纯symbol)' AFTER con_code;

-- 数据迁移: 从 con_code 提取纯 symbol
-- 例: '603648.SH' → '603648', '000001.SZ' → '000001'
UPDATE industry_constituent SET symbol = SUBSTRING_INDEX(con_code, '.', 1) WHERE symbol = '';

-- 调整唯一键
ALTER TABLE industry_constituent
  DROP INDEX uk_src_idx_con,
  ADD UNIQUE KEY uk_src_tax_idx_sym (source, taxonomy, index_code, symbol, market);
```

### 2.4 industry_weight 表改造

```sql
ALTER TABLE industry_weight
  ADD COLUMN taxonomy VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类体系' AFTER source,
  ADD COLUMN market   VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场' AFTER taxonomy,
  ADD COLUMN symbol   VARCHAR(32) NOT NULL DEFAULT '' COMMENT '成分股代码(纯symbol)' AFTER con_code;

UPDATE industry_weight SET symbol = SUBSTRING_INDEX(con_code, '.', 1) WHERE symbol = '';

ALTER TABLE industry_weight
  DROP INDEX uk_src_idx_con_dt,
  ADD UNIQUE KEY uk_src_tax_idx_sym_dt (source, taxonomy, index_code, symbol, market, trade_date);
```

### 2.5 industry_daily 表改造

```sql
ALTER TABLE industry_daily
  ADD COLUMN taxonomy VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类体系' AFTER source,
  ADD COLUMN market   VARCHAR(16) NOT NULL DEFAULT 'zh_a' COMMENT '市场' AFTER taxonomy;

ALTER TABLE industry_daily
  DROP INDEX uk_src_idx_dt,
  ADD UNIQUE KEY uk_src_tax_idx_mkt_dt (source, taxonomy, index_code, market, trade_date);
```

### 2.6 taxonomy_security_map 表改造

```sql
-- 增加 taxonomy 字段
ALTER TABLE taxonomy_security_map
  ADD COLUMN taxonomy VARCHAR(32) NOT NULL DEFAULT '' COMMENT '分类体系' AFTER source;

ALTER TABLE taxonomy_security_map
  DROP INDEX uk_source_cat_sec,
  ADD UNIQUE KEY uk_src_tax_cat_sec (source, taxonomy, category_code, symbol, asset_type, market);
```

---

## 3. Artemis 侧改动

### 3.1 统一 source 常量

**文件**: `artemis/consts/data_source.py`

```python
class DataSource(str, Enum):
    DS_AMAZING_DATA = "amazing_data"
    DS_MAIRUI = "mairui"
    DS_BAOSTOCK = "baostock"
    DS_TUSHARE = "tushare"

class Taxonomy(str, Enum):
    """分类体系标识（独立于数据供应商）"""
    SWHY = "swhy"          # 申万宏源
    CITIC = "citic"        # 中信
    GICS = "gics"          # 全球行业分类标准
    CONCEPT = "concept"    # 概念板块
    REGION = "region"      # 地域板块
    MAIRUI = "mairui"      # 麦蕊分类
```

### 3.2 StockZHAMarketCategorySWHY 修改

| 修改点 | 说明 |
|---|---|
| source | `DS_AMAZING_DATA` → 统一为 `amazing_data` |
| 新增 taxonomy | `Taxonomy.SWHY` = `"swhy"` |
| 新增 market | `"zh_a"` |
| code 字段 | 继续使用 `INDUSTRY_CODE` |
| 新增 index_code | 从 SDK 数据中提取 `INDEX_CODE` 单独存 |
| parent_code 修复 | 修正层级截断逻辑，保证 parent_code 正确填充 |
| attrs_json 精简 | 移除已提升为独立字段的 index_code，只保留 is_pub / change_reason |

### 3.3 StockZHAIndustryConstituentSWHY 修改

| 修改点 | 说明 |
|---|---|
| source | 保持 `amazing_data` |
| 新增 taxonomy | `"swhy"` |
| 新增 market | `"zh_a"` |
| con_code → symbol | 从 `603648.SH` 提取纯 `603648` 作为 symbol |
| con_code 保留 | 继续传 con_code 作为原始值（PhoenixA 侧可选存储） |

### 3.4 StockZHAIndustryWeightSWHY 修改

同 3.3 — 增加 taxonomy / market，con_code 提取纯 symbol。

### 3.5 StockZHAIndustryDailySWHY 修改

增加 taxonomy / market 字段。

### 3.6 StockZHAMarketCategory (Mairui) 修改

| 修改点 | 说明 |
|---|---|
| source | 保持 `mairui` |
| 新增 taxonomy | `"mairui"` |
| 新增 market | `"zh_a"` |

### 3.7 PhoenixAClient 接口调整

所有 taxonomy/industry 相关接口增加 `taxonomy` 和 `market` 参数：

```python
def upsert_market_categories(self, categories, source, taxonomy, market, run_id=None)
def upsert_industry_constituents(self, constituents, source, taxonomy, market, run_id=None)
def upsert_industry_weights(self, weights, source, taxonomy, market, run_id=None)
def upsert_industry_daily(self, bars, source, taxonomy, market, run_id=None)
```

API path 调整为 `/api/v2/taxonomy/{source}/{taxonomy}/{market}/...`

---

## 4. PhoenixA 侧改动

### 4.1 Model 改造

所有 taxonomy 相关 model 增加 `Taxonomy` 和 `Market` 字段。`TaxonomyCategory` 增加 `IndexCode` 字段。

### 4.2 DAO 改造

- 所有 upsert/query 方法增加 taxonomy + market 参数
- 唯一键冲突条件对应调整

### 4.3 Router / Controller 改造

路由调整为：
```
/api/v2/taxonomy/{source}/{taxonomy}/{market}/categories/upsert
/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-constituents/upsert
/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-weights/upsert
/api/v2/taxonomy/{source}/{taxonomy}/{market}/industry-daily/upsert
```

### 4.4 Migration

- MySQL: `migrations/mysql/security/0002_taxonomy_v2.sql`
- PostgreSQL: `migrations/postgresql/security/0001_security_init.sql` (若尚未创建)

两端都需要：
1. ALTER 增加字段 (taxonomy, market, index_code, symbol)
2. 数据迁移 (con_code → symbol, source 修正)
3. 唯一键调整

---

## 5. 迭代阶段

### Phase 1: 表结构与迁移 (PhoenixA)
- [ ] 编写 MySQL migration `0002_taxonomy_v2.sql`
- [ ] 编写 PostgreSQL 对应 migration
- [ ] 更新 Go model (taxonomy.go)
- [ ] 更新 DAO 层
- [ ] 更新 Controller / Router
- [ ] 更新 CHANGELOG

### Phase 2: Artemis 常量与 Client
- [ ] 新增 `Taxonomy` 枚举到 `data_source.py`
- [ ] 更新 `PhoenixAClient` 所有 taxonomy 相关方法签名
- [ ] 向下兼容：旧接口暂保留，标记 deprecated

### Phase 3: 下载任务修正
- [ ] `StockZHAMarketCategorySWHY`: 修正 source/taxonomy/parent_code/index_code
- [ ] `StockZHAIndustryConstituentSWHY`: con_code → symbol 提取
- [ ] `StockZHAIndustryWeightSWHY`: 同上
- [ ] `StockZHAIndustryDailySWHY`: 增加 taxonomy/market
- [ ] `StockZHAMarketCategory` (Mairui): 增加 taxonomy/market
- [ ] 更新 CHANGELOG

### Phase 4: 数据关联验证
- [ ] 验证 industry_constituent.symbol 能 JOIN security_registry.symbol
- [ ] 验证 taxonomy_category.parent_code 树状结构完整性
- [ ] 验证 index_code 在 taxonomy_category 和 industry_daily 之间可关联

### Phase 5: 多市场扩展 (Future)
- [ ] US 市场行业分类 (GICS) 接入
- [ ] JP / EUR 市场分类接入
- [ ] 统一 taxonomy 查询接口支持跨市场

---

## 6. 数据流示意 (改造后)

```
AmazingData SDK
    │
    ├── get_industry_base_info()
    │       ↓
    │   StockZHAMarketCategorySWHY
    │       ↓ post_process: 提取 industry_code, index_code, parent_code
    │       ↓ sink → PhoenixA POST /api/v2/taxonomy/amazing_data/swhy/zh_a/categories/upsert
    │       ↓
    │   taxonomy_category (source=amazing_data, taxonomy=swhy, market=zh_a)
    │
    ├── get_industry_constituent()
    │       ↓
    │   StockZHAIndustryConstituentSWHY
    │       ↓ post_process: con_code "603648.SH" → symbol "603648"
    │       ↓ sink → PhoenixA POST .../industry-constituents/upsert
    │       ↓
    │   industry_constituent (source=amazing_data, taxonomy=swhy, market=zh_a, symbol=603648)
    │       └── symbol FK → security_registry.symbol (logical, not enforced)
    │
    ├── get_industry_weight()
    │       ↓ (同上模式)
    │   industry_weight
    │
    └── get_industry_daily()
            ↓
        industry_daily (index_code → taxonomy_category.index_code 可关联)
```

---

## 7. 兼容性与风险

| 风险 | 缓解措施 |
|---|---|
| 改唯一键导致存量数据冲突 | migration 中先 backfill 新字段默认值再改 UK |
| 旧版 Artemis 调用新版 PhoenixA | PhoenixA 旧路由保留 6 个月，返回 deprecation warning |
| MySQL → PostgreSQL 迁移期间两端都要改 | migration 脚本分 MySQL/PG 两套，CI 分别验证 |
| con_code 提取 symbol 精度 | 先 split by '.'，再校验是否存在于 security_registry |

---

## 8. 预计改动文件清单

### PhoenixA (Go)
- `internal/model/taxonomy.go`
- `internal/dao/taxonomy_dao.go`
- `internal/service/taxonomy_service.go`
- `internal/api/router_v2.go`
- `internal/api/controller/taxonomy_controller.go` (if exists)
- `migrations/mysql/security/0002_taxonomy_v2.sql` (new)
- `migrations/postgresql/security/0001_security_init.sql` (new or update)
- `CHANGELOG`

### Artemis (Python)
- `artemis/consts/data_source.py`
- `artemis/core/clients/phoenixA_client.py`
- `artemis/engines/task_engine/download/zh/stock_zh_a_market_category_swhy.py`
- `artemis/engines/task_engine/download/zh/stock_zh_a_industry_constituent_swhy.py`
- `artemis/engines/task_engine/download/zh/stock_zh_a_industry_weight_swhy.py`
- `artemis/engines/task_engine/download/zh/stock_zh_a_industry_daily_swhy.py`
- `artemis/engines/task_engine/download/zh/stock_zh_a_market_category.py`
- `CHANGELOG`

