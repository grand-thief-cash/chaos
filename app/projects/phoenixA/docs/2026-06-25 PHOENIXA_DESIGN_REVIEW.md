# PhoenixA 设计 Review 报告

> 日期: 2026-06-25  
> 范围: `docs/system_design`、`app/projects/phoenixA/docs`、`internal/{model,dao,service,controller,api}`、PostgreSQL migrations  
> 重点: 数据中台总体设计、财务三张表 JSONB 存储、字段对外可发现性和读取便利性

## 1. 总体结论

PhoenixA 的总体方向是正确的: 以 Go 服务作为统一数据中台，底层收敛到 PostgreSQL 16 + TimescaleDB + PGVector，向 Artemis、Atlas、Cthulhu 暴露 HTTP CRUD 和数据目录能力。这和大仓 `docs/system_design` 中的定位一致，也比早期按 `stock_zh_a_*` 全栈硬编码的模式更可扩展。

财务三张表采用 `financial_statement` 单表 + `statement_type` + `data_json JSONB` 的物理设计，在当前阶段是可以接受的，前提是它被明确定位为“灵活原始明细存储 + 元数据契约 + 便捷读取 API”的组合，而不是让调用方直接面对无约束 JSON。财务字段数量大、来源字段变化快、银行/保险/证券/非金融报表结构差异明显，JSONB 能显著降低 schema 变更成本。

但当前实现里，JSONB 周边的外部契约还不够硬。最主要的问题不是“JSONB 不能用”，而是字段字典、日期格式、symbol 格式、`fields` 投影、OpenAPI、索引语义和写入规范之间存在不一致。这会直接影响你特别关心的点: 外界如何知道有哪些字段、字段什么意思、怎么稳定读取。

建议结论: 保留 JSONB 作为财务明细存储，但必须补一层稳定的财务字段契约和读取 facade。对高频核心字段，增加 typed projection 或 generated/materialized view，不要让因子引擎和外部调用者长期依赖散落在 JSONB 里的原始字段名。

## 2. 设计亮点

1. PhoenixA 的领域边界基本清晰: `bars`、`security`、`taxonomy`、`financial`、`strategy`、`kg`、`factor` 等域已经在文档和 Catalog 中成型。
2. v2 API 的方向正确: `bars/{asset_type}/{market}`、`taxonomy/{source}/{taxonomy}/{market}`、`financial/{source}/{statement_type}` 比旧 v1 路由更接近业务语义。
3. PostgreSQL JSONB 用在财务和公司行为上有合理性: 大量低频变动字段放 JSONB，常用过滤维度如 `source/symbol/market/statement_type/reporting_period/ann_date/comp_type_code` 提升为顶层列。
4. 已经有数据目录能力: `/api/v2/schema/*`、`/api/v2/catalog/data-dictionary`、`/api/v2/catalog/capabilities` 能为 UI、下游服务和 LLM tool discovery 提供基础入口。
5. 存储分层决策务实: 财务和大体量业务数据进入 `warm_storage`，小表和低延迟随机读数据留在 NVMe，符合个人量化平台的资源条件。

## 3. 主要问题

### 3.1 `data_json` 写入形态可能不是对象

测试用例显示 Artemis payload 中的 `data_json` 是双重编码字符串，例如:

```json
"data_json": "{\"TOTAL_ASSETS\":5600000000000.0,\"TOTAL_LIAB\":5100000000000.0}"
```

`model.FinancialStatement.DataJSON` 是 `json.RawMessage`，controller 和 service 没有在写入前把 JSON 字符串规范化成 JSON object。结果是 PostgreSQL 里可能存成 JSONB string，而不是 JSONB object。

这会带来三个问题:

1. `data_json @> '{"TOTAL_ASSETS": ...}'`、`data_json ? 'TOTAL_ASSETS'`、`data_json->>'TOTAL_ASSETS'` 这些查询语义对 JSONB string 不成立。
2. `idx_fs_data_gin` 的价值会被削弱，因为索引是建在 JSONB object 查询假设上的。
3. API 文档承诺 `data_json` 是 object，但实际响应可能仍是字符串。

SchemaDao 对双重编码做了兼容，这说明问题已经被观察到，但更合理的处理点应该在写入边界: 接收 string 或 object 都可以，但落库前统一为 object，并加约束或校验保证 `jsonb_typeof(data_json) = 'object'`。

### 3.2 字段发现有入口，但不是稳定字段契约

当前外界感知字段主要依赖三类来源:

1. Markdown 文档: `docs/tables_description/financial_statement.md` 和 `docs/api_biz_data_description/financial_statements.md`
2. 动态发现: `/api/v2/schema/fields?domain=financial_statement&type=balance_sheet`
3. 数据目录: `/api/v2/catalog/data-dictionary`、`/api/v2/catalog/capabilities`

这些入口方向正确，但还不足以成为外部稳定契约:

1. `schema/fields` 是采样发现，默认 sample size 有上限，且没有按 `source`、`market`、`comp_type_code` 区分，可能漏掉银行、保险、证券等低频字段。
2. 动态发现只能告诉调用方“出现过哪些 key”，不能稳定表达字段中文名、单位、量纲、币种、口径、是否累计值、是否核心字段、来源字段别名、废弃状态。
3. Markdown 中有完整字段说明，但不是机器可读单一来源，和 Catalog/Capabilities 里的字段描述容易漂移。
4. API 文档说元数据字段不放进 `data_json`，表文档又把 `MARKET_CODE`、`SECURITY_NAME`、`REPORTING_PERIOD` 等列在 `data_json` 字段结构里，实现也没有强制剥离这些字段。

建议新增一个权威的财务字段字典，可以是数据库表、YAML/JSON 文件或 Go 生成代码，但必须单一来源生成文档和 API 元数据。字段至少应包含:

| 字段 | 说明 |
|------|------|
| source | 数据源，如 `amazing_data`、`baostock` |
| statement_type | `balance_sheet`、`income`、`cashflow` 等 |
| raw_field | 原始字段名，如 `TOTAL_ASSETS` |
| canonical_field | 平台标准字段名，如 `total_assets` |
| label_zh | 中文名 |
| value_type | number/string/date/boolean |
| unit | 元、万元、股、百分比、元/股等 |
| scale | 原始单位换算因子 |
| comp_type_scope | 非金融/银行/保险/证券适用范围 |
| required/core | 是否核心常用字段 |
| aliases | 历史别名或不同源字段映射 |
| deprecated | 是否废弃 |

### 3.3 `fields` 参数实现和文档不匹配

文档承诺:

```text
fields=symbol,reporting_period,data_json.TOT_OPERA_REV
```

期望返回:

```json
{
  "symbol": "000001",
  "reporting_period": "2023-12-31",
  "data_json": {
    "TOT_OPERA_REV": 12345678900.0
  }
}
```

但 DAO 当前把字段拼为:

```go
data_json->'TOT_OPERA_REV' as data_json.TOT_OPERA_REV
```

问题:

1. alias 中带点号，未加引号，PostgreSQL 语法和 GORM scan 都不可靠。
2. 查询结果仍 scan 到 `[]*model.FinancialStatement`，动态字段不会自然组装回嵌套 `data_json` object。
3. `fields` 中普通字段直接拼入 SQL select，没有白名单校验，存在 SQL 注入和误用风险。
4. controller 只是 `strings.Split`，没有 trim/dedup，也没有校验字段是否存在。
5. 财务 API 文档里示例出现了 `data_json.DVD_PER_SHARE_PRE_TAX_CASH` 这类公司行为字段，容易误导调用方。

建议: `fields` 需要改为显式投影层，不应直接复用 GORM model scan。

推荐行为:

1. 只允许字段来自 top-level 白名单和财务字段字典。
2. JSONB 字段用参数化/安全构造表达式，并统一返回嵌套 `data_json`。
3. partial response 用 `[]map[string]any` 或专门 DTO，而不是 `[]FinancialStatement`。
4. 未知字段返回 400，并提示通过 `/api/v2/financial/schema` 或 `/api/v2/catalog/data-dictionary` 查看字段。

### 3.4 日期和 symbol 契约不一致

DDL、表文档和 API 文档写的是 `YYYY-MM-DD`，但 financial/corporate action 测试 payload 使用 `YYYYMMDD`。同时 `symbol` 文档写“纯代码，不含交易所后缀”，测试使用 `000001.SZ`。

当前财务 controller 没有复用 `normalizeDateYYYYMMDD`，也没有 normalize symbol。结果可能出现:

1. 同一公司同时存在 `000001` 和 `000001.SZ` 两套数据。
2. `period_start=2023-01-01` 与库内 `20231231` 字符串比较不符合预期。
3. PIT 查询 `ann_date_before` 依赖字符串大小比较，格式混用会产生隐性错误。
4. 文档和实际调用方式不一致，外部调用者会很难排查。

建议短期选择一个外部格式，推荐 ISO `YYYY-MM-DD`；写入时把 `YYYYMMDD`、RFC3339、已有 ISO 全部规范化为 `YYYY-MM-DD`。中期把 `reporting_period`、`ann_date`、`actual_ann_date` 从 `VARCHAR(10)` 迁移为 `DATE`，至少增加 generated date columns 供查询和索引使用。

PIT 还需要明确包含边界: 现在 DAO 用 `ann_date < ann_date_before`，而因子场景通常期望“截至某日已公告”，更常见是 `ann_date <= as_of_date`。如果坚持 before 语义，需要文档明确是 exclusive；否则建议改为 inclusive 或新增 `ann_date_lte`。

### 3.5 JSONB 索引设计需要按查询语义调整

迁移里 `idx_fs_data_gin` 使用:

```sql
USING GIN (data_json jsonb_path_ops)
```

`jsonb_path_ops` 对 `@>` containment 很合适，但不支持所有 key existence 场景。迁移注释和 DAO 注释都提到 `data_json ? 'TOTAL_ASSETS'`，但如果主要需要 `?`、`?|` 这种 key 查询，应使用默认 `jsonb_ops`，或者同时建立更有针对性的 expression index。

更关键的是，因子和财务分析常见查询不是“是否包含某个 JSON key”，而是:

```sql
(data_json->>'TOTAL_ASSETS')::numeric
(data_json->>'NET_PRO_EXCL_MIN_INT_INC')::numeric
(data_json->>'TOT_OPERA_REV')::numeric
```

这些高频字段如果需要过滤、排序、聚合或 JOIN，建议:

1. 为核心字段建立 typed generated columns 或 expression indexes。
2. 建一个 `financial_statement_core` view/materialized view，按三张表输出稳定 typed 字段。
3. 让因子引擎读取 core view/API，而不是长期自己解析原始 JSONB。

### 3.6 单表存五类报表可以保留，但外部要暴露“逻辑三表”

当前 `financial_statement` 实际承载:

1. `balance_sheet`
2. `income`
3. `cashflow`
4. `profit_express`
5. `profit_notice`
6. 以及 baostock 的 `bs_balance`

物理单表的好处是 DAO/API/索引/去重逻辑统一，适合多来源和长尾字段。但调用方从业务上关心的是资产负债表、利润表、现金流量表这些“逻辑表”。因此建议保留物理单表，同时提供逻辑表 facade:

```text
GET /api/v2/financial/{source}/balance_sheet
GET /api/v2/financial/{source}/income
GET /api/v2/financial/{source}/cashflow
GET /api/v2/financial/{source}/schema?statement_type=income
GET /api/v2/financial/{source}/income/core-fields
```

更进一步，可以提供扁平化输出选项:

```text
GET /api/v2/financial/amazing_data/income?symbol=000001&flatten=true
```

返回 top-level metadata + selected JSONB 字段展开后的稳定对象，便于 Python/pandas 直接消费。

### 3.7 OpenAPI 已经明显落后于实际 v2 API

`docs/openapi.yaml` 基本还停留在 stock/list 等旧接口，没有覆盖:

1. `/api/v2/financial/{source}/{statement_type}`
2. `/api/v2/schema/*`
3. `/api/v2/catalog/*`
4. `/api/v2/corporate-action/*`
5. `/api/v2/bars/{asset_type}/{market}`

这会降低外部接入便利性。Markdown 文档对人可读，但真正的外部契约应由 OpenAPI 覆盖，并且能生成客户端或至少用于接口校验。

### 3.8 schema/catalog 设计方向正确，但需要避免漂移

CatalogService 里有静态 map: table metadata、column description、capability registry、domain API registry。这让 `/catalog` 很快能提供业务语义，是务实方案。但长期风险是:

1. Go map、Markdown 文档、OpenAPI、migration、真实数据库会相互漂移。
2. 字段说明分散，JSONB 字段更容易只在文档里存在。
3. 静态 capability 只描述 `data_json` 这个容器，不能完整描述 `TOTAL_ASSETS`、`TOT_OPERA_REV` 等财务字段。

建议把“字段字典”作为第一等数据资产管理，Catalog 从它生成，而不是手写多份。

## 4. 财务 JSONB 设计的最终评估

### 适合继续使用 JSONB 的原因

1. 财务字段多且来源差异大，直接宽表会非常宽，后续变更成本高。
2. 三张表字段集合差异明显，银行/保险/证券又有行业专属科目。
3. 主要查询入口已经把关键过滤条件提升为顶层列，JSONB 不承担全部查询职责。
4. PostgreSQL JSONB 比 MySQL JSON 更适合作为灵活字段存储，并能配合 GIN、表达式索引、jsonb 函数做发现和查询。

### 不能只靠 JSONB 的原因

1. 外部调用方需要稳定字段契约，而不是采样发现出来的 key 列表。
2. 因子计算需要 typed numeric/date 字段、单位和口径，不适合每次从 JSONB 中临时猜。
3. 高频核心字段应该有 typed projection，否则性能、正确性和可维护性都会下降。
4. 如果写入层允许 JSONB string、格式混乱日期、混乱 symbol，JSONB 的灵活性会变成数据质量风险。

结论: JSONB 作为底层灵活存储合理；JSONB 直接作为外部主要契约不合理。应该用“JSONB 原始层 + 字段字典 + typed core projection + 友好查询 API”组合落地。

## 5. 推荐整改优先级

### P0: 先修数据契约正确性

1. 写入时规范化 `data_json`: object/string 都接收，但落库必须是 JSONB object。
2. 财务和公司行为 upsert/query 统一日期格式，建议落库为 `YYYY-MM-DD`。
3. 统一 `symbol`: 明确纯代码还是带交易所后缀，写入边界做 normalize。
4. 修复 `fields` 投影: 白名单、DTO/map 返回、嵌套 `data_json` 输出、未知字段 400。
5. 给 `fields`、日期格式、symbols 批量查询、PIT 边界补 API 测试。

### P1: 建立字段可发现的权威来源

1. 新增财务字段字典，覆盖 `balance_sheet/income/cashflow/profit_express/profit_notice/bs_balance`。
2. 字段字典生成 Markdown、Catalog、OpenAPI schema extension，避免多处手写。
3. `/api/v2/schema/fields` 保留为“实际数据发现/审计”，不要作为唯一契约。
4. `schema/fields` 增加 `source`、`market`、`comp_type_code` 可选过滤，返回 sample coverage。

### P2: 提升读取便利性和性能

1. 增加 `flatten=true` 或专门的 `core` endpoint，方便 pandas/因子引擎直接读取。
2. 建 `financial_statement_core` view 或 materialized view，承载常用 typed 字段。
3. 为核心字段增加 expression index 或 generated columns。
4. 重新选择 JSONB GIN opclass: `jsonb_ops` 用于 key existence，`jsonb_path_ops` 用于 containment，也可以按查询模式双索引或局部索引。
5. 更新 `docs/openapi.yaml` 到 v2，并把 catalog/schema/financial 纳入契约。

## 6. 建议的目标形态

建议把财务数据分为四层:

```text
Layer 1: Raw ingest
  接收 Artemis/AmazingData/Baostock 原始字段，做 JSON object、date、symbol normalize

Layer 2: Storage
  financial_statement: top-level metadata + data_json JSONB
  仍以 statement_type 区分逻辑表

Layer 3: Contract
  financial_field_dictionary: raw_field/canonical_field/label/type/unit/source/scope
  catalog/schema/openapi/docs 都从它派生

Layer 4: Consumption
  /financial/{source}/{statement_type}: 原始兼容查询
  /financial/{source}/{statement_type}?fields=...: 安全字段投影
  /financial/{source}/{statement_type}?flatten=true: pandas 友好扁平输出
  financial_statement_core: 因子引擎常用 typed projection
```

这样可以同时保留 JSONB 的灵活性和外部读取的便利性。

## 7. 需要补充验证的测试

建议至少增加这些测试用例:

1. Upsert `data_json` object 和 JSON string，查询返回都必须是 object。
2. `fields=symbol,reporting_period,data_json.TOTAL_ASSETS` 返回嵌套 `data_json`，且不返回未请求字段。
3. 未知字段、危险字段名、SQL 片段都返回 400。
4. `symbols=000001,600519` 在没有 `market` 参数时，data 和 total 一致。
5. `reporting_period`、`period_start/end`、`ann_date_before` 同时覆盖 `YYYYMMDD` 和 `YYYY-MM-DD` 输入。
6. `ann_date_before` 的 inclusive/exclusive 语义有明确测试。
7. `/api/v2/schema/fields` 与字段字典的差异能被发现并报告，而不是静默覆盖。

## 8. 最后判断

PhoenixA 的设计已经从“面向单一数据源/单一资产的 CRUD 服务”向“真正的数据中台”演进，Catalog 和 Schema Discovery 是很重要的进步。财务三张表用 JSONB 不需要推倒重来，但它现在还缺“外界可感知、可验证、可生成客户端”的字段契约。

如果只补文档，不补写入规范和字段 API，JSONB 会持续制造读取不便利和数据质量风险。优先把 `data_json` 对象化、日期/symbol 规范化、`fields` 投影修好，再建设财务字段字典，是最小成本、收益最高的路线。
