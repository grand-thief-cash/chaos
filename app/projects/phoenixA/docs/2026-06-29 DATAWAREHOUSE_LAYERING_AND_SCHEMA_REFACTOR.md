# PhoenixA 数仓分层与 Schema 改造方案

## 日期
2026-06-29（2026-06-29 修订：改为单数据源 + 多 schema search_path 方案；2026-06-29 再修订：修复 _migrations 追踪表问题 + 保持 datasource 名称为 security；2026-06-29 三修订：修正附录 C 函数签名 + 补充 tracking 表落点说明；2026-06-29 四修：按数据血缘复核分层，security_registry 由 govern 移至 ods，新增分层判定标准 + 数据就绪风险）

---

## 现状 Review

### 一、postgresgorm 组件对 schema 的支持度

#### 生效链路
```
DataSourceConfig.Schema 
    → buildDSN 注入 search_path 参数（对池内每条连接都生效）
    → 启动时会话级 SET search_path + CREATE SCHEMA IF NOT EXISTS（兜底）
```

#### 当前支持能力
- ✅ **多 datasource = 多 schema**：每个 datasource 独立绑定 schema，存入 `c.dbs map[string]*gorm.DB`
- ✅ **单 datasource 内多 schema search_path**：`Schema` 字段支持逗号分隔（如 `"public,kg"`），DSN 会注入 `search_path=public,kg`
- ❌ **运行时 schema 切换**：无 `UseSchema()`/`WithSchema()` API
- ❌ **GORM AutoMigrate**：不存在，全靠 SQL 迁移

#### 缺陷列表

| 缺陷 | 文件位置 | 问题描述 | 影响 |
|------|----------|----------|------|
| 多 schema 创建失败 | `postgresgorm/component.go:137` | 对逗号分隔多 schema 直接拼 `CREATE SCHEMA IF NOT EXISTS public,kg` → SQL 语法错误；`isValidIdentifier` 允许逗号但 PG 不接受 | 无法自动创建多个 schema |
| SET search_path 会话级无效 | `postgresgorm/component.go:131` | `sqlDB.ExecContext()` 只对池中当前一条连接生效，新连接不继承；与 DSN 注入重复且冗余 | search_path 设置不可靠 |
| migration 不设 search_path | `migration/migration.go:226` | `executeMigrationFile` 把 schema 形参直接丢弃（`_ string`）；`Run()` 的 docstring（migration.go:79-81）声称 "search_path is set before execution" 但实现没做 | 裸表名 migration 落对 schema 纯属运气（靠 DSN 提前注入） |
| **组件启动顺序** | `postgresgorm/component.go:102-142` | 先执行 `migration.Run()`，后执行 `SET search_path + CREATE SCHEMA IF NOT EXISTS`；全新库上迁移在 schema 存在前就跑了 | 裸名 CREATE TABLE 失败或落到 public |
| **_migrations 追踪表逗号问题** | `migration/migration.go:133,164,188` | 直接拼 `schema + "._migrations"`，当 schema="ods,dwd,govern,kg,public" 时生成非法 SQL `CREATE TABLE ods,dwd,govern,kg,public._migrations` | 全新库上 Run() 在 ensureTrackingTable 处立即失败 |

#### 组件来源
phoenixA 编译使用 **vendor 目录** 下的 `github.com/grand-thief-cash/chaos/app/infra/go/application v0.18.3`，本地源码目录 `app/infra/go/application` 存在但 `go.mod` 第 69 行的 replace 被注释掉。本地修改源码不会影响 phoenixA 构建，除非取消 replace + 重新 go mod vendor。

---

### 二、PhoenixA Schema 使用现状

#### 两套不对称策略

| 域 | 策略 | Migration 写法 | Model TableName() | 示例 |
|----|------|----------------|-------------------|------|
| **kg** | 显式 schema | `CREATE SCHEMA IF NOT EXISTS kg; CREATE TABLE kg.documents (...)` | 返回 `kg.表名` | `kg.go` |
| **security** | 隐式 search_path | 裸表名 `CREATE TABLE taxonomy_category (...) TABLESPACE xxx` | 返回裸表名 | `taxonomy.go` |

#### 现状细节
- 只有 **1 个 pg datasource**：`security`，配置 `schema: security_dev`，`migrate_enabled: true`，`migrate_base: ./migrations`
- 没有 `kg` datasource，尽管 `migrations/postgresql/kg/0001_kg_init.sql` 文件头标注 "data source: kg"
- kg 表目前是手动创建，或靠 model 的 `TableName()` 带 `kg.` 前缀访问

#### 分层判定标准（数据血缘驱动）

分层以**数据来源/血缘**为准，不按业务域或冷热分层。标准：

| 层 | 判定标准 | 典型特征 |
|----|----------|----------|
| **ODS** | artemis 从外部 API 下载并落地到 phoenixA 的数据（源忠实或轻度规范化）。artemis 是唯一外部数据入口，phoenixA 自身不调任何外部 API。 | 多数带 `source` 列、`data_json` 保留原始字段；单源主数据例外（无 source 列） |
| **DWD** | phoenixA 内部从已有 ODS/DWD 表 JOIN/计算派生，无外部抓取 | 无 source 列；由内部触发或定时计算 |
| **Govern** | phoenixA 自建治理/观察元数据、artemis 生成的操作记录（回测）、migration seed 的数据契约字典 | 非外部行情数据；多为只读或运行期生成 |

**关键澄清：`source` 列不是 ODS 的硬门槛。** `security_registry` 由 artemis `StockZHAList` 从 AmazingData 下载落地（唯一外部来源，仅做了规范化），归 ODS；它无 `source` 列是因为单源、source 隐含固定，是 ODS 内的"单源主数据"显式例外。


#### security_dev 表混居现状
所有表挤在 `security_dev` 一个 schema 里，仅靠表名前缀做"软分层"：

| 层 | 表名 | 说明 |
|----|------|------|
| **ODS（拉取落地）** | `taxonomy_category`、`industry_constituent`、`industry_weight`、`industry_daily`、`financial_statement`、`corporate_action`、`adjust_factor`、`long_hu_bang`、`equity_structure`、`bars_*`、`security_registry` | 外部源直接落地，保留 source 字段；`security_registry` 为单源主数据（无 source 列） |
| **DWD（加工派生）** | `taxonomy_category_derived_flags` | 基于 ODS 衍生的语义标记 |
| **ODS/DWD 混合** | `taxonomy_security_map` | 直推端点（带 source）+ JOIN 派生灌入；归 ODS，但主灌入路径是 `SyncMappingsFromConstituents` 派生 |
| **Govern（自建治理）** | `strategy_run_summary`、`strategy_run_artifact`、`data_dataset_dictionary`、`data_field_dictionary`、`data_enum_dictionary`、`data_field_coverage_observation` | 回测记录、数据字典、字段覆盖观察 |

冷热分层用 `TABLESPACE pg_default/warm_storage` 实现，与 schema 无关。

#### DAO 裸名 SQL 现状
多个 DAO 直接用裸名拼 SQL（不通过 TableName()）：
- `taxonomy_dao.go:181-193`：JOIN taxonomy_category、FROM industry_constituent、INSERT INTO taxonomy_security_map
- `catalog_coverage_dao.go:48,70,92`：FROM financial_statement / corporate_action / equity_structure
- `field_dictionary_dao.go`：FROM data_*_dictionary（这三个表**没有 TableName() 方法**，表名只在 DAO 里作为硬编码字符串存在）
- `schema_dao.go:113,168,207`：fmt.Sprintf("SELECT COUNT(*) FROM %s ...", spec.Table)
- `bars.go`：bars 没有 TableName()，动态表名由 `dao/table_resolver.go` 的 `BarsTableName()` 生成

---

## 方案选型对比

| 维度 | 三数据源方案（原计划） | **单数据源 + 多 schema search_path（最终选择）** |
|------|------------------------|--------------------------------------------------|
| datasource 数量 | 3 个：`ods`/`dwd`/`govern` | **1 个：保持名称为 `security`（最小改动，无需改 DAO）** |
| search_path | 每个 datasource 单独：`ods` 用 `search_path=ods`、`dwd` 用 `search_path=dwd`… | 单个 datasource 用 `search_path=ods,dwd,govern,kg,public` |
| DAO 重连 | 需要 —— 每个 DAO 要改连到对应数据源（`registry_ext/dao_v2.go` 全改） | **不需要** —— DAO 继续用 `NewXxxDao("security")`，无需变更 |
| 裸名 SQL 改 schema 限定 | 必须全改，否则跨层查询挂 | 不需要改 —— search_path 自动解析 |
| _migrations 跟踪表 | 每个 schema 有自己的 `ods._migrations`/`dwd._migrations`/`govern._migrations` | **单个 `ods._migrations`（仅取 schema 字符串的第一个）** |
| 侵入性 | 高 —— 改 20+ DAO 注册、一堆裸名 SQL | 低 —— 主要改 migration 和 model `TableName()` 加显式 schema 前缀 |
| 隔离性 | 严格 —— ods DAO 不会误写到 dwd | 宽松 —— 所有表同 search_path，靠 discipline 不写错 |

---

## 改造方案（单数据源 + 多 schema search_path）

### 决策
- **分层粒度**：ods / dwd / govern 三层
- **kg 处理**：保持 kg 不变（继续显式 `kg.表名`）；kg migration 目前与框架脱节，可选手动跑或并入主迁移
- **组件缺陷**：顺手修复
- **旧数据处理**：全部删表重新导入
- **架构选择**：单数据源 + `search_path=ods,dwd,govern,kg,public`
- **datasource 名称**：保持为 `security`（最小改动，无需改 DAO 注册）
- **操作前提**：需对 ods/dwd/govern/kg 拥有 CREATE SCHEMA 权限（CREATE SCHEMA 失败仅记录警告）
- **_migrations tracking 表落点**：固定落在第一个 schema（ods），与迁移事务内 search_path 一致，二者无冲突

---

### 改造步骤

#### 阶段 1：修复组件层缺陷（在源码目录，不是 vendor）

修改 `C:\Users\gaoc3\projects\chaos\app\infra\go\application\components`：

##### 1.1 `postgresgorm/component.go` — 调整启动顺序 + 多 schema 创建
- **关键顺序调整**：将 `CREATE SCHEMA IF NOT EXISTS`（按逗号拆分逐个执行）移到 **`migration.Run()` 之前**
- 删除多余的会话级 `SET search_path TO %s` 代码块（依赖 DSN 注入即可）

**修改前/修改后**见附录 A。

##### 1.2 `migration/migration.go` — 修复 migration search_path
- `executeMigrationFile` 不再丢弃 schema 参数
- 仅在**事务分支**设置 `search_path`（PostgreSQL 始终支持事务，非事务分支删掉 SET 避免连接池问题）

**修改前/修改后**见附录 B。

##### 1.3 `migration/migration.go` — 修复 _migrations 追踪表逗号问题
- `ensureTrackingTable`/`listApplied`/`recordApplied` 不再直接拼全 schema 字符串
- 改为仅取**逗号分隔后的第一个 schema**：`strings.TrimSpace(strings.Split(schema, ",")[0]) + "._migrations"`

**修改前/修改后**见附录 C。

---

#### 阶段 2：切换 phoenixA 到本地组件源码
修改 `phoenixA/go.mod`：取消注释第 69 行的 replace 指令：
```go
replace github.com/grand-thief-cash/chaos/app/infra/go/application => ../../infra/go/application
```

---

#### 阶段 3：重构 phoenixA migration
重构 `phoenixA/migrations/postgresql/security/`（**保持目录名 security 不动，原地重写 SQL**）：
- 原 15 个 SQL 文件备份（或 git 保留历史）
- 原地重写为：`0001_ods.sql`、`0002_dwd.sql`、`0003_govern.sql`
- 每个 migration 文件内：显式 `CREATE SCHEMA IF NOT EXISTS ods/dwd/govern/kg` + `CREATE TABLE ods.xxx (...) TABLESPACE xxx`
- kg migration 保持在 `kg/0001_kg_init.sql` 不动（可选手动跑或加入 security）
- 更新 `config/config.yaml`：
  - **datasource 名称保持为 `security`**
  - `schema` 设为 `"ods,dwd,govern,kg,public"`
  - `migrate_base` 仍指向 `./migrations`（自动选 `migrations/postgresql/security/`）

---

#### 阶段 4：更新 model/DAO 表名映射
修改 `phoenixA/internal/model/*.go` 里的 `TableName()` 方法：
- ODS 表 → `ods.表名`（如 `taxonomy_category` → `ods.taxonomy_category`、`security_registry` → `ods.security_registry`）
- DWD 表 → `dwd.表名`（如 `taxonomy_category_derived_flags` → `dwd.taxonomy_category_derived_flags`）
- Govern 表 → `govern.表名`（如 `strategy_run_summary` → `govern.strategy_run_summary`）
- kg 表 → 保持 `kg.表名` 不变
- bars 动态表名 `BarsTableName(...)` → 加 `ods.bars_xxx` 前缀
- **三个 data_*_dictionary 表**：没有 TableName()，直接在 `field_dictionary_dao.go` 里的硬编码 SQL 改成 `govern.data_*_dictionary`

修改 `phoenixA/internal/dao/catalog_dao.go:87` 和 `catalog_service.go:1028,1030` 的 schema 枚举，把 `security_dev`/`security` 替换为 `ods`/`dwd`/`govern`/`kg`。

**注意**：DAO 里的裸名 SQL **不需要改**（因为 search_path=ods,dwd,govern,kg,public 会自动解析），但为了清晰和可维护性，建议**统一改成显式 schema 限定**。

---

#### 阶段 5：清理并重新导入
- 删除旧的 `security_dev` schema（或整个库重建）
- 启动 phoenixA，`security` datasource 会自动执行 `migrations/postgresql/security/` 下的 migrations
- 重新拉取导入 ODS 数据到 `ods.*`
- 重新运行派生/治理流程生成 `dwd.*`/`govern.*`

---

#### 数据就绪风险（ODS 表分类正确但 artemis 暂无生产者）

下列 ODS 表分层无误，但 artemis `download/zh` 目前**没有对应下载任务**写入，fresh reload 后会是空表。需补 artemis 下载任务，或在 migration 里标注为"预留"：

| 表 | 现状 | 说明 |
|----|------|------|
| `equity_structure` | phoenixA 全链路就绪（model/dao/service/controller + 路由 `POST /api/v2/equity-structure/{source}/upsert`），但 artemis 无 `upsert_equity_structure` 调用 | artemis 仅在 BI 只读查询引用；数据字典已登记其 AmazingData `get_equity_structure` 契约 |
| `bars_index_zh_a_daily_nf` | 需 `asset_type=index` 的 bars 写入，但唯一 bars 任务是股票（`asset_type=stock`） | 无 index 行情下载任务；`industry_daily` 是另一张表，不是 index bars |

> 注：`equity_structure` 出现在 `0004_govern_seed.sql` 是**数据字典元数据**（登记 equity_structure 这个数据集的契约），并非向 equity_structure 表插入数据行——它是 ODS 而非 govern 的证据。

---

## 表分类映射完整清单

| 原表名 | 新 Schema | 新全名 | 位置 | 说明 |
|--------|-----------|--------|------|------|
| `taxonomy_category` | ods | `ods.taxonomy_category` | `taxonomy.go` | 有 TableName() |
| `taxonomy_security_map` | ods | `ods.taxonomy_security_map` | `taxonomy.go` | 有 TableName()；ODS/DWD 混合（主灌入为 JOIN 派生） |
| `industry_constituent` | ods | `ods.industry_constituent` | `taxonomy.go` | 有 TableName() |
| `industry_weight` | ods | `ods.industry_weight` | `taxonomy.go` | 有 TableName() |
| `industry_daily` | ods | `ods.industry_daily` | `taxonomy.go` | 有 TableName() |
| `financial_statement` | ods | `ods.financial_statement` | `financial_statement.go` | 有 TableName() |
| `corporate_action` | ods | `ods.corporate_action` | `corporate_action.go` | 有 TableName() |
| `adjust_factor` | ods | `ods.adjust_factor` | `adjust_factor.go` | 有 TableName() |
| `long_hu_bang` | ods | `ods.long_hu_bang` | `long_hu_bang.go` | 有 TableName() |
| `equity_structure` | ods | `ods.equity_structure` | `equity_structure.go` | 有 TableName() |
| `security_registry` | ods | `ods.security_registry` | `security.go` | 有 TableName()；单源主数据，无 source 列 |
| `bars_stock_zh_a_daily_nf` | ods | `ods.bars_stock_zh_a_daily_nf` | `dao/table_resolver.go` | 动态表名，无 TableName() |
| `bars_stock_zh_a_daily_hfq` | ods | `ods.bars_stock_zh_a_daily_hfq` | `dao/table_resolver.go` | 动态表名，无 TableName() |
| `bars_index_zh_a_daily_nf` | ods | `ods.bars_index_zh_a_daily_nf` | `dao/table_resolver.go` | 动态表名，无 TableName() |
| `bars_ext_baostock_stock_zh_a_daily` | ods | `ods.bars_ext_baostock_stock_zh_a_daily` | `dao/table_resolver.go` | 动态表名，无 TableName() |
| `taxonomy_category_derived_flags` | dwd | `dwd.taxonomy_category_derived_flags` | `taxonomy.go` | 有 TableName() |
| `strategy_run_summary` | govern | `govern.strategy_run_summary` | `strategy_run.go` | 有 TableName() |
| `strategy_run_artifact` | govern | `govern.strategy_run_artifact` | `strategy_run.go` | 有 TableName() |
| `data_dataset_dictionary` | govern | `govern.data_dataset_dictionary` | `field_dictionary_dao.go` | 无 TableName()，仅 DAO 硬编码 |
| `data_field_dictionary` | govern | `govern.data_field_dictionary` | `field_dictionary_dao.go` | 无 TableName()，仅 DAO 硬编码 |
| `data_enum_dictionary` | govern | `govern.data_enum_dictionary` | `field_dictionary_dao.go` | 无 TableName()，仅 DAO 硬编码 |
| `data_field_coverage_observation` | govern | `govern.data_field_coverage_observation` | `field_coverage.go` | 有 TableName() |
| `kg.documents` | kg | 保持不变 | `kg.go` |  |
| `kg.extractions` | kg | 保持不变 | `kg.go` |  |
| `kg.events` | kg | 保持不变 | `kg.go` |  |
| `kg.graph_ingestions` | kg | 保持不变 | `kg.go` |  |
| `kg.daily_runs` | kg | 保持不变 | `kg.go` |  |
| `kg.impact_logs` | kg | 保持不变 | `kg.go` |  |

---

## 附录 A：`postgresgorm/component.go` 修复代码

### A.1 调整启动顺序 + 多 schema 创建修复
```go
// 修改前（component.go:102-142）
if ds.MigrateEnabled {
	migrateDir := migration.ResolveMigrateDir(ds.MigrateBase, migration.DialectPostgres, name)
	schema := strings.TrimSpace(ds.Schema)
	result, err := migration.Run(ctx, sqlDB, migration.DialectPostgres, migrateDir, schema)
	// ...
}
if schema := strings.TrimSpace(ds.Schema); schema != "" {
	if !isValidIdentifier(schema) {
		_ = sqlDB.Close()
		return fmt.Errorf("postgres_gorm datasource %s invalid schema name: %s", name, schema)
	}
	setPath := fmt.Sprintf("SET search_path TO %s", schema)
	if _, err := sqlDB.ExecContext(ctx, setPath); err != nil {
		_ = sqlDB.Close()
		return fmt.Errorf("set search_path for %s failed: %w", name, err)
	}
	createSchema := fmt.Sprintf("CREATE SCHEMA IF NOT EXISTS %s", schema)
	if _, err := sqlDB.ExecContext(ctx, createSchema); err != nil {
		logging.Warnf(ctx, "[postgres_gorm] create schema %s hint: %v (may require privileges)", schema, err)
	}
	logging.Infof(ctx, "[postgres_gorm] datasource %s search_path set to %s", name, schema)
}

// 修改后
if schema := strings.TrimSpace(ds.Schema); schema != "" {
	if !isValidIdentifier(schema) {
		_ = sqlDB.Close()
		return fmt.Errorf("postgres_gorm datasource %s invalid schema name: %s", name, schema)
	}
	// Split schema by comma and create each one individually BEFORE migrations
	schemas := strings.Split(schema, ",")
	for _, s := range schemas {
		s = strings.TrimSpace(s)
		if s == "" {
			continue
		}
		createStmt := fmt.Sprintf("CREATE SCHEMA IF NOT EXISTS %s", s)
		if _, err := sqlDB.ExecContext(ctx, createStmt); err != nil {
			logging.Warnf(ctx, "[postgres_gorm] create schema %s hint: %v (may require privileges)", s, err)
		}
	}
	logging.Infof(ctx, "[postgres_gorm] datasource %s schemas created: %s", name, schema)
}
if ds.MigrateEnabled {
	migrateDir := migration.ResolveMigrateDir(ds.MigrateBase, migration.DialectPostgres, name)
	schema := strings.TrimSpace(ds.Schema)
	result, err := migration.Run(ctx, sqlDB, migration.DialectPostgres, migrateDir, schema)
	// ...
}
// 删除会话级 SET search_path，完全依赖 DSN 注入
```

---

## 附录 B：`migration/migration.go` executeMigrationFile 修复代码
```go
// 修改前
func executeMigrationFile(ctx context.Context, db *sql.DB, dialect Dialect, path string, _ string) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}

	content := string(b)
	var stmts []string
	switch dialect {
	case DialectPostgres:
		stmts = SplitPostgresStatements(content)
	default:
		stmts = splitSimple(content)
	}

	// Try to run in a transaction
	tx, txErr := db.BeginTx(ctx, nil)
	if txErr != nil {
		// If transaction not supported, run without
		for _, s := range stmts {
			if strings.TrimSpace(s) == "" {
				continue
			}
			if _, err := db.ExecContext(ctx, s); err != nil {
				return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
			}
		}
		return nil
	}

	for _, s := range stmts {
		if strings.TrimSpace(s) == "" {
			continue
		}
		if _, err := tx.ExecContext(ctx, s); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
		}
	}
	return tx.Commit()
}

// 修改后
func executeMigrationFile(ctx context.Context, db *sql.DB, dialect Dialect, path string, schema string) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}

	content := string(b)
	var stmts []string
	switch dialect {
	case DialectPostgres:
		stmts = SplitPostgresStatements(content)
	default:
		stmts = splitSimple(content)
	}

	// Try to run in a transaction
	tx, txErr := db.BeginTx(ctx, nil)
	if txErr != nil {
		// If transaction not supported, run without (no SET search_path to avoid connection pool issues)
		for _, s := range stmts {
			if strings.TrimSpace(s) == "" {
				continue
			}
			if _, err := db.ExecContext(ctx, s); err != nil {
				return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
			}
		}
		return nil
	}

	// Set search_path IN TRANSACTION if schema provided and dialect is Postgres
	if dialect == DialectPostgres && schema != "" {
		setPath := fmt.Sprintf("SET search_path TO %s", schema)
		if _, err := tx.ExecContext(ctx, setPath); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("set search_path for migration %s: %w", filepath.Base(path), err)
		}
	}

	for _, s := range stmts {
		if strings.TrimSpace(s) == "" {
			continue
		}
		if _, err := tx.ExecContext(ctx, s); err != nil {
			_ = tx.Rollback()
			return fmt.Errorf("exec statement in %s: %w\nSQL: %.200s", filepath.Base(path), err, s)
		}
	}
	return tx.Commit()
}
```

---

## 附录 C：`migration/migration.go` _migrations 追踪表修复代码

```go
// 修改前
func ensureTrackingTable(ctx context.Context, db *sql.DB, dialect Dialect, schema string) error {
	tableName := "_migrations"
	if schema != "" {
		tableName = schema + "._migrations"
	}
	// ... CREATE TABLE ...
}

func listApplied(ctx context.Context, db *sql.DB, schema string) (map[string]bool, error) {
	tableName := "_migrations"
	if schema != "" {
		tableName = schema + "._migrations"
	}
	// ... SELECT ...
}

func recordApplied(ctx context.Context, db *sql.DB, filename string, schema string) error {
	tableName := "_migrations"
	if schema != "" {
		tableName = schema + "._migrations"
	}
	// ... INSERT ...
}

// 修改后
func firstSchema(schema string) string {
	schema = strings.TrimSpace(schema)
	if schema == "" {
		return ""
	}
	return strings.TrimSpace(strings.Split(schema, ",")[0])
}

func ensureTrackingTable(ctx context.Context, db *sql.DB, dialect Dialect, schema string) error {
	tableName := "_migrations"
	if s := firstSchema(schema); s != "" {
		tableName = s + "._migrations"
	}
	// ... CREATE TABLE ...
}

func listApplied(ctx context.Context, db *sql.DB, schema string) (map[string]bool, error) {
	tableName := "_migrations"
	if s := firstSchema(schema); s != "" {
		tableName = s + "._migrations"
	}
	// ... SELECT ...
}

func recordApplied(ctx context.Context, db *sql.DB, filename string, schema string) error {
	tableName := "_migrations"
	if s := firstSchema(schema); s != "" {
		tableName = s + "._migrations"
	}
	// ... INSERT ...
}
```
