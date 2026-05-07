# 2026-05-07 财务数据 MySQL → PostgreSQL 迁移

> 更新日期：2026-05-07  
> 关联文档：`2026-04-26 FINANCIAL_DATA_FIELDS.md`  
> 影响范围：PhoenixA (Go), Artemis (Python)

---

## 一、背景

之前基于 `2026-04-26 FINANCIAL_DATA_FIELDS.md` 的设计和 `AmazingData_development_guide.pdf` 描述的接口，完成了 `financial_statement`（资产负债表/利润表/现金流量表/业绩快报/业绩预告）和 `corporate_action`（分红/配股）两大数据域的下载 + 存储，写入目标是 MySQL 的 `JSON` 列。

当前项目正在从 MySQL 迁移到 PostgreSQL（见 `2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md` Phase B），本轮迭代将这两个数据域的 DAO 全面切换到 PostgreSQL，并利用 PG 的原生 JSONB 优势。

---

## 二、对照 MD 版 AmazingData 开发手册的设计审查

基于新提供的 `AmazingData_development_guide.md`（V1.0.24），逐项对比现有实现：

### 2.1 SDK 接口调用 — ✅ 无问题

| 数据类型 | SDK 方法 | 返回类型 | 现有实现 | 状态 |
|----------|----------|----------|----------|------|
| balance_sheet | `get_balance_sheet` | `dict{code: DataFrame}` | `_normalize_result` 走 dict 分支 | ✅ |
| cashflow | `get_cash_flow` | `dict{code: DataFrame}` | 同上 | ✅ |
| income | `get_income` | `dict{code: DataFrame}` | 同上 | ✅ |
| profit_express | `get_profit_express` | `DataFrame` | `_normalize_result` 走 DataFrame 分支 | ✅ |
| profit_notice | `get_profit_notice` | `DataFrame` | 同上 | ✅ |
| dividend | `get_dividend` | `DataFrame` | 同上 | ✅ |
| right_issue | `get_right_issue` | `DataFrame` | 同上 | ✅ |

### 2.2 字段完整性 — ✅ 无问题（data_json 动态存储）

由于我们采用 `data_json` JSONB 存储所有数值字段的方案，SDK 返回的所有字段都会自动进入 `data_json`，不存在遗漏风险。结构化字段（`METADATA_FIELDS`）正确排除了非数值元数据。

### 2.3 元数据字段处理 — 🐛 发现 1 个潜在 BUG

**BUG: `COMP_TYPE_CODE` 类型不一致**

| 数据类型 | SDK 声明类型 | 实际表现 |
|----------|-------------|---------|
| balance_sheet | `int` | 正常 |
| cashflow | `str` (SDK 文档标注) | 可能返回 `"1"` 而非 `1` |
| income | `int` | 正常 |

`base_financial_statement.py` 中的 `_int(val)` 原来直接 `int(val)`，如果 SDK 返回浮点字符串如 `"1.0"` 会抛出 `ValueError`。

**已修复：** `_int` 改为 `int(float(val))`，增加异常捕获兜底。

### 2.4 profit_express 元数据缺失处理 — ✅ 正确

SDK `get_profit_express` 不返回 `REPORT_TYPE`, `SECURITY_NAME`, `STATEMENT_TYPE`, `COMP_TYPE_CODE`。
`StockZHAProfitExpress._get_metadata_overrides` 正确地将这些设为空值/零值。

### 2.5 profit_notice 元数据缺失处理 — ✅ 正确

SDK `get_profit_notice` 不返回 `STATEMENT_TYPE`, `ACTUAL_ANN_DATE`, `COMP_TYPE_CODE`。
`StockZHAProfitNotice._get_metadata_overrides` 正确处理。

### 2.6 corporate_action 字段映射 — ✅ 正确

| 子类 | REPORT_PERIOD_FIELD | PROGRESS_FIELD | SDK 吻合 |
|------|-------|---------|-------|
| dividend | `REPORT_PERIOD` | `DIV_PROGRESS` | ✅ |
| right_issue | `RIGHTSISSUE_YEAR` | `PROGRESS` | ✅ |

---

## 三、MySQL → PostgreSQL 迁移变更

### 3.1 数据类型变更

| 原 MySQL 类型 | 新 PG 类型 | 说明 |
|--------------|-----------|------|
| `JSON` | `JSONB` | 二进制存储，支持 GIN 索引，查询性能显著提升 |
| `INT` (comp_type_code) | `SMALLINT` | 只有 4 个值（1-4），节省空间 |
| `DATETIME` | `TIMESTAMPTZ` | 含时区，避免时区问题 |
| `BIGINT UNSIGNED AUTO_INCREMENT` | `BIGSERIAL` | PG 原生自增序列 |

### 3.2 索引策略升级

**GIN 索引（核心 PG 优势）：**

```sql
-- financial_statement: 支持 data_json 内容查询
CREATE INDEX idx_fs_data_gin ON financial_statement USING GIN (data_json jsonb_path_ops);

-- corporate_action: 同上
CREATE INDEX idx_ca_data_gin ON corporate_action USING GIN (data_json jsonb_path_ops);
```

**`jsonb_path_ops` vs 默认 GIN：**
- `jsonb_path_ops` 仅支持 `@>` 包含查询，但索引体积更小、查询更快
- 对我们的场景（按 key-value 查数据）完全够用

**部分索引（Partial Index）：**

```sql
-- 只有非空 ann_date 才建索引，节省空间
CREATE INDEX idx_fs_ann_date ON financial_statement (ann_date) WHERE ann_date != '';
-- 只有 comp_type_code > 0 时才有意义
CREATE INDEX idx_fs_comp_type ON financial_statement (comp_type_code) WHERE comp_type_code > 0;
```

### 3.3 DAO 层切换

| DAO 文件 | 原依赖 | 新依赖 | 核心变更 |
|----------|--------|--------|---------|
| `financial_statement_dao.go` | `mysql_gorm` | `postgres_gorm` | + JSONB @>, ?? 查询 |
| `corporate_action_dao.go` | `mysql_gorm` | `postgres_gorm` | + JSONB @>, ?? 查询 |
| `schema_dao.go` | `mysql_gorm` | `postgres_gorm` | `JSON_TABLE` → `jsonb_object_keys()` |

### 3.4 Schema Discovery 重写

MySQL 版本使用 `JSON_TABLE(JSON_KEYS(...))` 语法，PostgreSQL 不支持。替换为：

```sql
-- 旧 (MySQL):
SELECT DISTINCT jk.field_name
FROM (SELECT data_json FROM ... LIMIT ?) sub,
     JSON_TABLE(JSON_KEYS(sub.data_json), '$[*]'
       COLUMNS (field_name VARCHAR(128) PATH '$')
     ) jk;

-- 新 (PostgreSQL):
SELECT DISTINCT k AS field_name
FROM (SELECT data_json FROM ... LIMIT $2) sub,
     LATERAL jsonb_object_keys(sub.data_json) AS k
ORDER BY field_name;
```

`LATERAL` + `jsonb_object_keys()` 是 PG 的标准做法，性能优于 MySQL 的 JSON_TABLE。

---

## 四、新增 JSONB 查询能力

### 4.1 Model 层新增 Filter 字段

```go
// FinancialStatementFilters (新增)
DataContains map[string]interface{} // data_json @> '{"key": value}'
DataHasKey   string                 // data_json ? 'key'

// CorporateActionFilters (新增)
DataContains map[string]interface{} // 同上
DataHasKey   string                 // 同上
```

### 4.2 查询示例

```sql
-- 查找所有总资产超过 1000 亿的资产负债表
SELECT * FROM financial_statement
WHERE statement_type = 'balance_sheet'
  AND data_json @> '{"TOTAL_ASSETS": 100000000000}'::jsonb;

-- 查找所有包含 EBITDA 字段的利润表
SELECT * FROM financial_statement
WHERE statement_type = 'income'
  AND data_json ? 'EBITDA';

-- 查找特定股票的派息金额
SELECT symbol, data_json ->> 'DVD_PER_SHARE_PRE_TAX_CASH' AS div_per_share
FROM corporate_action
WHERE action_type = 'dividend'
  AND symbol = '600519.SH';

-- 通过 JSONB 路径表达式查询
SELECT * FROM financial_statement
WHERE data_json @@ '$.TOTAL_ASSETS > 1000000000';
```

---

## 五、变更文件清单

### PhoenixA (Go)

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `migrations/postgresql/security/0002_financial_data.sql` | **新增** | PG 建表 + JSONB GIN 索引 + 部分索引 |
| `internal/model/financial_statement.go` | 修改 | `type:json` → `type:jsonb`, `int` → `smallint`, 新增 JSONB Filter 字段 |
| `internal/model/corporate_action.go` | 修改 | `type:json` → `type:jsonb`, 新增 JSONB Filter 字段 |
| `internal/dao/financial_statement_dao.go` | 修改 | `mysql_gorm` → `postgres_gorm`, + JSONB 查询 |
| `internal/dao/corporate_action_dao.go` | 修改 | `mysql_gorm` → `postgres_gorm`, + JSONB 查询 |
| `internal/dao/schema_dao.go` | 修改 | `mysql_gorm` → `postgres_gorm`, `JSON_TABLE` → `jsonb_object_keys()` |

### Artemis (Python)

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `engines/task_engine/download/zh/base_financial_statement.py` | 修改 | `_int()` 健壮性修复 |

### 无需修改的文件

| 文件 | 原因 |
|------|------|
| `base_corporate_action.py` | 不涉及 COMP_TYPE_CODE，无 BUG |
| 所有子类 (balance_sheet/income/...) | 逻辑不变，只是底层 DAO 切换 |
| Service 层 / Controller 层 | 接口不变，DAO 切换对上层透明 |
| `phoenixA_client.py` (Artemis) | HTTP API 不变 |
| `dao_v2.go` (registry) | 数据源名 "security" 不变 |

---

## 六、数据迁移注意事项

### 6.1 MySQL → PG 数据迁移

如果 MySQL 中已有 financial_statement / corporate_action 数据，使用 pgloader 迁移：

```bash
pgloader mysql://user:pass@localhost/chaos_mysql \
         postgresql://chaos_app:pass@localhost/chaos_db

# data_json 列会自动从 MySQL JSON → PG text，需要转换为 JSONB：
psql -d chaos_db -c "
ALTER TABLE financial_statement ALTER COLUMN data_json TYPE JSONB USING data_json::jsonb;
ALTER TABLE corporate_action ALTER COLUMN data_json TYPE JSONB USING data_json::jsonb;
"
```

### 6.2 如果是全新环境

直接启动 phoenixA，migration `0002_financial_data.sql` 会自动创建 JSONB 表。
Artemis 重新跑一轮调度即可填充数据。

---

## 七、后续可优化项

1. **JSONB 值提取列（Generated Column）**  
   对高频查询字段可创建 PG 生成列：
   ```sql
   ALTER TABLE financial_statement 
     ADD COLUMN total_assets NUMERIC GENERATED ALWAYS AS ((data_json ->> 'TOTAL_ASSETS')::numeric) STORED;
   ```
   配合 B-tree 索引可实现超快范围查询。

2. **JSONB 聚合查询（PG 原生）**  
   ```sql
   -- 某只股票历年营业收入趋势
   SELECT reporting_period, (data_json ->> 'OPERA_REV')::numeric AS opera_rev
   FROM financial_statement
   WHERE symbol = '000001.SZ' AND statement_type = 'income'
   ORDER BY reporting_period;
   ```

3. **物化视图（Materialized View）**  
   对常用的跨期对比、行业对比查询创建物化视图，定期刷新。

4. **分区表**  
   当数据量超过千万级，可按 `statement_type` / `reporting_period` 年份做 PG 原生分区。

---

## 八、测试验证

```bash
# 1. 启动 phoenixA (PG migration 自动执行)
cd app/projects/phoenixA && go run cmd/main.go

# 2. 验证表已创建
psql -d chaos_db -c "\d financial_statement"
psql -d chaos_db -c "\d corporate_action"

# 3. 验证 GIN 索引
psql -d chaos_db -c "\di idx_fs_data_gin"
psql -d chaos_db -c "\di idx_ca_data_gin"

# 4. 运行 Artemis 调度任务填充数据
# 5. 验证 Schema Discovery API
curl http://localhost:18085/api/v2/schema/domains
curl http://localhost:18085/api/v2/schema/fields?domain=financial_statement&type=balance_sheet

# 6. 验证 JSONB 查询
curl "http://localhost:18085/api/v2/financial/amazing_data/balance_sheet?symbol=000001.SZ"
```

