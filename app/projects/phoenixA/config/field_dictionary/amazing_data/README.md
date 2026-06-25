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
config/field_dictionary/amazing_data/*.jsonl
    ↓
migrations/postgresql/security/0013_seed_amazing_data_field_dictionary.sql
    ↓
data_dataset_dictionary / data_field_dictionary / data_enum_dictionary
```

需要重新生成时执行:

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

生成后必须 review `config/field_dictionary/amazing_data/*.jsonl` 和 `migrations/postgresql/security/0013_seed_amazing_data_field_dictionary.sql` 的 diff。

## 使用流程

### 1. 生成或刷新字典源文件

```bash
cd app/projects/phoenixA
sh scripts/generate_field_dictionary_from_docs.sh
```

这一步会刷新:

```text
config/field_dictionary/amazing_data/*.jsonl
config/field_dictionary/amazing_data/datasets.json
migrations/postgresql/security/0013_seed_amazing_data_field_dictionary.sql
```

### 2. 运行 PostgreSQL migration

PhoenixA 的 `config/config.yaml` 中 `postgres_gorm.data_sources.security.migrate_enabled=true` 时，服务启动会按文件名顺序执行:

```text
0012_field_dictionary.sql
0013_seed_amazing_data_field_dictionary.sql
0014_equity_structure.sql
```

也可以用你们现有的 migration 执行方式手动跑 `app/projects/phoenixA/migrations/postgresql/security` 目录。

注意:

| migration | 作用 | tablespace |
|----------|------|------------|
| `0012_field_dictionary.sql` | 创建 dataset/field/enum 字典表 | `pg_default` |
| `0013_seed_amazing_data_field_dictionary.sql` | 导入 AmazingData 字典数据 | 写入 `pg_default` 上的字典表 |
| `0014_equity_structure.sql` | 创建股本结构业务表 | `warm_storage` |

### 3. 验证字典是否入库

```sql
SELECT dataset, data_type, COUNT(*)
FROM data_field_dictionary
WHERE source = 'amazing_data'
  AND contract_version = '2026-06-25'
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

验证字段发现:

```sql
SELECT raw_field, canonical_field, label_zh, unit, storage_location, is_core
FROM data_field_dictionary
WHERE source = 'amazing_data'
  AND dataset = 'financial_statement'
  AND data_type = 'balance_sheet'
  AND raw_field IN ('TOTAL_ASSETS', 'TOT_SHARE');
```

验证同名字段单位差异:

```sql
SELECT dataset, data_type, raw_field, label_zh, unit, scale
FROM data_field_dictionary
WHERE source = 'amazing_data'
  AND raw_field = 'TOT_SHARE'
ORDER BY dataset, data_type;
```

这里应能看到资产负债表的 `TOT_SHARE` 单位是 `股`，股本结构的 `TOT_SHARE` 单位是 `万股` 且 `scale=10000`。

## tablespace 约定

字典表是小型元数据，migration 中显式使用 `TABLESPACE pg_default`。

底层业务数据仍按已有规划落盘:

| 数据 | 表 | tablespace |
|------|----|------------|
| 财务报表明细 | `financial_statement` | `warm_storage` |
| 公司行为明细 | `corporate_action` | `warm_storage` |
| 股本结构明细 | `equity_structure` | `warm_storage` |
| 字段字典和枚举 | `data_*_dictionary` | `pg_default` |
