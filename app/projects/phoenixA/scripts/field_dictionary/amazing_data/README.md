# AmazingData 字段字典源文件

本目录是 PhoenixA 对 AmazingData 数据的机器可读字段契约源文件。

## 文件说明

| 文件 | 说明 |
|------|------|
| `datasets.json` | 数据集级元数据，包括 dataset、data_type、底层存储表和 tablespace |
| `financial_statement.fields.jsonl` | 财务报表字段，覆盖 `balance_sheet`、`cashflow`、`income`、`profit_express`、`profit_notice` |
| `corporate_action.fields.jsonl` | 公司行为字段，覆盖 AmazingData `dividend`、`right_issue` |
| `equity_structure.fields.jsonl` | 股本结构字段，来自 AmazingData `get_equity_structure` |
| `enums.jsonl` | 字段枚举，包括 `REPORT_TYPE`、`COMP_TYPE_CODE`、`DIV_PROGRESS`、`PROGRESS`、`P_TYPECODE` 等 |

维护脚本（同目录）:

| 脚本 | 说明 |
|------|------|
| `regenerate_seed_sql.py` | 读取 jsonl + datasets.json，生成 `migrations/postgresql/security/0004_govern_seed.sql`（jsonl → seed SQL 的唯一转换器）|
| `update_version.py` | 把所有 jsonl + datasets.json 的 `contract_version` 统一刷成新值（升版本时用）|

字段内容（单位、口径、`comp_type_scope`、PDF 断行校正等）直接编辑对应的 `*.fields.jsonl` 单行记录，再用 `regenerate_seed_sql.py` 重新生成 seed。历史上一次性治理用的 `fix_dictionary.py` / `fix_all_dictionaries.py` 已删除，治理结果已固化进 jsonl。

JSONL 中每一行是一条可直接映射到 `data_field_dictionary` 或 `data_enum_dictionary` 的记录。选择 JSONL 是为了让 Go 可以用标准库直接读取，也方便 diff 单行字段变化。

## 来源和校对规则

原始权威来源是 `docs/third_party_sdk/AmazingData_development_guide.md`。

已有的 `docs/tables_description` 和 `docs/api_biz_data_description` 继续有价值，但定位是 bootstrap 和人读文档，不再作为唯一事实源。当前源文件生成规则是:

1. 从 `docs/tables_description/financial_statement.md` 和 `docs/tables_description/corporate_action.md` 抽取字段表。
2. 按 AmazingData SDK 章节校对数据类型、SDK 函数和枚举。
3. 把元数据字段标记为 `storage_location=top_level`，例如 `MARKET_CODE`、`REPORTING_PERIOD`、`ANN_DATE`。
4. 把业务明细字段标记为 `storage_location=data_json`，保留 SDK 原始字段名。
5. 对 PDF 转 Markdown 的断行问题做人工校正，例如股本结构的 `TOT_TRADABLE_SHARE`。
6. 对现有文档和 SDK 的字段名差异使用 `aliases` 表达，例如现金流 `NET_CASH_FLOW_OPERA_ACT` 兼容 `NET_CASH_FLOWS_OPERA_ACT`。

## 入库方式

字段不是手工逐条插入数据库。

当前流程是:

```text
AmazingData SDK 原文
    + docs/tables_description bootstrap
    ↓
scripts/generate_field_dictionary_from_docs.ps1
    ↓
scripts/field_dictionary/amazing_data/*.jsonl
    ↓
scripts/field_dictionary/amazing_data/regenerate_seed_sql.py
    ↓
migrations/postgresql/security/0004_govern_seed.sql
    ↓
govern.data_dataset_dictionary / govern.data_field_dictionary / govern.data_enum_dictionary
```

需要重新生成 seed SQL 时执行:

```bash
cd app/projects/phoenixA/scripts/field_dictionary/amazing_data
python3 regenerate_seed_sql.py
```

`regenerate_seed_sql.py` 只负责把 jsonl + datasets.json 转换成 seed migration（`DELETE` + `INSERT`，对同一 `contract_version` 幂等）。它**不**改动字段内容，字段内容的来源是 jsonl 本身（由 `scripts/generate_field_dictionary_from_docs.*` 从 SDK 文档半自动抽取并人工校对后产出）。

需要从 SDK 文档重新 bootstrap 字段时执行:

```bash
cd app/projects/phoenixA
sh scripts/generate_field_dictionary_from_docs.sh
```

如果环境中的 Python 命令不是 `python3`，可以指定:

```bash
PYTHON_BIN=python sh scripts/generate_field_dictionary_from_docs.sh
```

Windows 本地也可以直接调用同一份 Python 主脚本:

```powershell
python app/projects/phoenixA/scripts/generate_field_dictionary_from_docs.py --project-root app/projects/phoenixA
```

`generate_field_dictionary_from_docs.ps1` 现在也是薄包装器，会调用同一份 Python 主脚本。生成和测试环境推荐使用 `.sh`，Windows 本地可以使用 `.ps1`。

生成后必须 review `scripts/field_dictionary/amazing_data/*.jsonl` 和 `migrations/postgresql/security/0004_govern_seed.sql` 的 diff。

## 使用流程

### 1. 生成或刷新字典源文件

从 SDK 文档 bootstrap 字段内容:

```bash
cd app/projects/phoenixA
sh scripts/generate_field_dictionary_from_docs.sh
```

这一步会刷新:

```text
scripts/field_dictionary/amazing_data/*.jsonl
scripts/field_dictionary/amazing_data/datasets.json
```

jsonl 是字段内容的唯一事实源；之后再用 `regenerate_seed_sql.py` 把它们转成 seed migration:

```bash
cd app/projects/phoenixA/scripts/field_dictionary/amazing_data
python3 regenerate_seed_sql.py
```

这一步会刷新:

```text
migrations/postgresql/security/0004_govern_seed.sql
```

### 2. 运行 PostgreSQL migration

PhoenixA 的 `config/config.yaml` 中 `postgres_gorm.data_sources.security.migrate_enabled=true` 时，服务启动会按文件名顺序执行 `migrations/postgresql/security/` 下的迁移。当前该目录的迁移按 warehouse layer 分层:

```text
0001_ods.sql
0002_dwd.sql
0003_govern.sql
0004_govern_seed.sql
0005_govern_phoenixa_meta_enums.sql
```

也可以用你们现有的 migration 执行方式手动跑 `app/projects/phoenixA/migrations/postgresql/security` 目录。

注意:

| migration | 作用 | tablespace |
|----------|------|------------|
| `0003_govern.sql` | 创建 dataset/field/enum 字典表（`govern` schema） | `pg_default` |
| `0004_govern_seed.sql` | 导入 AmazingData 字典数据 | 写入 `pg_default` 上的 `govern.*` 字典表 |
| `0005_govern_phoenixa_meta_enums.sql` | 导入 phoenixA 平台元枚举（`asset_type`/`exchange`/`market`/`source`，source=`phoenixa`） | 写入 `pg_default` 上的 `govern.data_enum_dictionary` |
| `0001_ods.sql` | 创建财务报表 / 公司行为 / 股本结构等 ODS 落地表 | `warm_storage`（明细）|

seed migration 用 `DELETE WHERE source='amazing_data' AND contract_version=...` + `INSERT` 写入，对同一 `contract_version` 幂等，可重跑。

### 3. 验证字典是否入库

```sql
SELECT dataset, data_type, COUNT(*)
FROM govern.data_field_dictionary
WHERE source = 'amazing_data'
  AND contract_version = '2026-06-27'
GROUP BY dataset, data_type
ORDER BY dataset, data_type;
```

预期行数:

| dataset | data_type | 字段数 |
|---------|-----------|--------|
| `corporate_action` | `dividend` | 24 |
| `corporate_action` | `right_issue` | 30 |
| `equity_structure` | `equity_structure` | 54 |
| `financial_statement` | `balance_sheet` | 179 |
| `financial_statement` | `cashflow` | 120 |
| `financial_statement` | `income` | 110 |
| `financial_statement` | `profit_express` | 33 |
| `financial_statement` | `profit_notice` | 15 |

合计 565 条字段记录。枚举字典共 56 条，覆盖 `REPORT_TYPE`、`STATEMENT_TYPE`、`COMP_TYPE_CODE`、`DIV_PROGRESS`、`PROGRESS`、`P_TYPECODE`、`BOOLEAN_FLAG`。

验证字段发现:

```sql
SELECT raw_field, canonical_field, label_zh, unit, storage_location, is_core
FROM govern.data_field_dictionary
WHERE source = 'amazing_data'
  AND dataset = 'financial_statement'
  AND data_type = 'balance_sheet'
  AND raw_field IN ('TOTAL_ASSETS', 'TOT_SHARE');
```

验证同名字段单位差异:

```sql
SELECT dataset, data_type, raw_field, label_zh, unit, scale
FROM govern.data_field_dictionary
WHERE source = 'amazing_data'
  AND raw_field = 'TOT_SHARE'
ORDER BY dataset, data_type;
```

这里应能看到资产负债表的 `TOT_SHARE` 单位是 `股`，股本结构的 `TOT_SHARE` 单位是 `万股` 且 `scale=10000`。

## tablespace 约定

字典表是小型元数据，`0003_govern.sql` 中显式使用 `TABLESPACE pg_default`，位于 `govern` schema。

底层业务数据仍按已有规划落盘:

| 数据 | 表 | tablespace |
|------|----|------------|
| 财务报表明细 | `financial_statement`（ods） | `warm_storage` |
| 公司行为明细 | `corporate_action`（ods） | `warm_storage` |
| 股本结构明细 | `equity_structure`（ods） | `warm_storage` |
| 字段字典和枚举 | `govern.data_*_dictionary` | `pg_default` |
