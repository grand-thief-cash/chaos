# AmazingData 字段字典与 PhoenixA 数据访问设计

> 日期: 2026-06-25  
> 范围: `docs/third_party_sdk/AmazingData_development_guide.md`、PhoenixA 财务与公司行为表设计、`2026-06-25 PHOENIXA_DESIGN_REVIEW.md`  
> 目标: 让其他服务即使不知道底层字段，也能轻松发现字段、理解字段含义，并稳定查询这些数据。

## 1. 结论

PhoenixA 当前用 `financial_statement` 单表 + `statement_type` + `data_json JSONB` 存储资产负债表、利润表、现金流量表、业绩快报、业绩预告，这个方向可以保留。AmazingData 财务字段多、变化快，且银行、保险、证券、非金融企业字段口径差异明显，全部拆成强 schema 表会带来很高的迁移和维护成本。

但 JSONB 只能作为灵活明细存储，不能作为外部服务的字段契约。外部服务真正需要的是:

1. 先知道有哪些数据集和报表类型。
2. 不知道字段名时，可以搜索字段名、中文含义、单位、口径、适用范围。
3. 知道字段名后，可以用稳定参数查询、投影和过滤。
4. 字段来自哪里、是否和 SDK 原始字段一致、是否有别名、是否已废弃，都能被机器读取。

因此建议将 AmazingData SDK 文档中的字段说明整理为 PhoenixA 的权威字段字典。Markdown 文档可以继续保留，但字段含义不能只存在于 Markdown 中；应落到数据库表、YAML/JSON 配置或生成代码中，并由它统一生成 API 元数据、OpenAPI、表说明文档和查询校验逻辑。

一句话设计原则:

> JSONB 负责存数据，字段字典负责解释数据，查询 facade 负责让外部服务安全、稳定、低心智成本地使用数据。

## 2. AmazingData 原始来源整理

AmazingData SDK 是底层字段的源头。当前 PhoenixA 至少应把以下 SDK 函数纳入同一个字段字典体系。

| 数据域 | PhoenixA 类型 | SDK 章节与函数 | 当前/建议存储 | 说明 |
|------|---------------|---------------|--------------|------|
| 财务报表 | `balance_sheet` | 3.5.5.1 `get_balance_sheet` | `financial_statement` | 资产负债表，包含 `TOTAL_ASSETS`、`TOTAL_LIAB`、`TOT_SHARE` 等 |
| 财务报表 | `cashflow` | 3.5.5.2 `get_cash_flow` | `financial_statement` | 现金流量表，包含经营、投资、筹资现金流等 |
| 财务报表 | `income` | 3.5.5.3 `get_income` | `financial_statement` | 利润表，包含收入、利润、EPS、EBIT、EBITDA 等 |
| 财务报表 | `profit_express` | 3.5.5.4 `get_profit_express` | `financial_statement` | 业绩快报，字段比正式报表少，但对及时性很重要 |
| 财务报表 | `profit_notice` | 3.5.5.5 `get_profit_notice` | `financial_statement` | 业绩预告，包含预告类型、净利润上下限、变动原因 |
| 股本数据 | `equity_structure` | 3.5.6.3 `get_equity_structure` | 建议独立表或独立 dataset | 与估值、流通市值、复权相关，不能混进三张表 |
| 公司行为 | `dividend` | 3.5.7.1 `get_dividend` | `corporate_action` | 分红、送转、除权除息、派息日 |
| 公司行为 | `right_issue` | 3.5.7.2 `get_right_issue` | `corporate_action` | 配股价格、比例、募集资金、进度 |

SDK 附录中的枚举也应进入枚举字典:

| 枚举 | SDK 章节 | 用途 |
|-----|---------|------|
| `REPORT_TYPE` | 4.1.8 | 报告期名称，1/2/3/4 对应 3/6/9/12 月 |
| `STATEMENT_TYPE` | 4.1.9 | 报表类型代码，如合并报表、单季度、调整、更正前、母公司报表等 |
| `DIV_PROGRESS` | 4.1.10 | 分红进度，如董事会预案、股东大会通过、实施、未通过 |
| `PROGRESS` | 4.1.11 | 配股进度，如董事会预案、股东大会通过、实施、证监会核准 |
| `COMP_TYPE_CODE` | 财务字段备注 | 公司类型，1 非金融、2 银行、3 保险、4 证券 |

注意: SDK 文档由 PDF 转成 Markdown 后存在断行问题，例如字段名被拆成 `REPORTING_PERI OD`、`DVD_PER_SHARE_PRE_T AX_CASH`、`NET_CASH_FLO WS_*`。字段字典初版可以半自动抽取，但必须人工校对，不能把 PDF 换行噪声直接作为字段契约。

## 3. JSONB 设计边界

### 3.1 可以保留 JSONB 的原因

财务三张表以及快报、预告存在几个现实特点:

1. 字段数量大，且不同行业适用字段不同。
2. AmazingData 字段可能随版本变化。
3. 很多字段低频使用，强行全部建列会让表结构膨胀。
4. 下游常用过滤维度集中在证券代码、报告期、公告日、报表类型、公司类型等少数字段。

因此，`financial_statement.data_json` 存储 AmazingData 原始业务字段是合理的。更合适的定位是:

| 层次 | 职责 |
|-----|------|
| 顶层列 | 稳定过滤、去重、排序、权限、索引 |
| `data_json` | 保存 AmazingData 明细字段 |
| 字段字典 | 解释 `data_json` 中每个字段的含义、类型、单位、别名、枚举 |
| 查询 API | 让外部服务不直接拼 JSONB SQL |
| typed view/materialized view | 承载高频核心字段和因子引擎读取 |

### 3.2 不能只靠 JSONB 的原因

如果外部服务直接面对无约束 JSONB，会出现几个问题:

1. 不知道有哪些字段，必须看文档或猜字段名。
2. 只看到 `TOTAL_ASSETS`，不知道单位、口径、是否适用银行/保险。
3. 字段同名但单位可能不同，例如股本结构中的 `TOT_SHARE` 是万股，而资产负债表中的 `TOT_SHARE` 是股。
4. 字段类型可能在 SDK 文档中不一致，例如 `COMP_TYPE_CODE` 在不同表里可能标成 `int` 或 `str`。
5. 动态扫描样本只能发现出现过的 key，不能保证覆盖所有字段，也不能说明字段含义。
6. 当前 `jsonb_path_ops` GIN 索引适合 `@>` 和 JSONPath 查询，不覆盖所有 `?` key-exists 场景。如果 API 要支持字段存在性查询，应补充 `jsonb_ops` 索引或表达式索引。

所以结论不是“把 JSONB 改成宽表”，而是“保留 JSONB，但必须把字段解释和读取体验补齐”。

## 4. 推荐数据契约

### 4.1 顶层列规范

`financial_statement` 顶层列应作为查询和去重的权威字段:

| 顶层列 | 来源字段 | 说明 |
|-------|---------|------|
| `source` | 固定为 `amazing_data` | 数据源 |
| `symbol` | `MARKET_CODE` 规范化 | 证券代码，建议统一为纯代码，输入可兼容带交易所后缀 |
| `market` | 由代码或来源推导 | 市场，如 `zh_a` |
| `statement_type` | SDK 函数映射 | `balance_sheet`、`income`、`cashflow`、`profit_express`、`profit_notice` |
| `reporting_period` | `REPORTING_PERIOD` | 统一为 `YYYY-MM-DD`，兼容输入 `YYYYMMDD` |
| `report_type` | `REPORT_TYPE` | 报告期名称代码或归一化值 |
| `statement_code` | `STATEMENT_TYPE` | 报表类型代码 |
| `security_name` | `SECURITY_NAME` | 证券名称 |
| `ann_date` | `ANN_DATE` | 公告日期，统一为 `YYYY-MM-DD` |
| `actual_ann_date` | `ACTUAL_ANN_DATE` | 实际公告日期 |
| `comp_type_code` | `COMP_TYPE_CODE` | 公司类型 |
| `data_json` | 其他 SDK 明细字段 | JSONB object，不能落成 JSON string |

`corporate_action` 顶层列应作为公司行为查询入口:

| 顶层列 | 来源字段 | 说明 |
|-------|---------|------|
| `source` | 固定为 `amazing_data` | 数据源 |
| `symbol` | `MARKET_CODE` 规范化 | 证券代码 |
| `market` | 由代码或来源推导 | 市场 |
| `action_type` | SDK 函数映射 | `dividend`、`right_issue` |
| `report_period` | `REPORT_PERIOD` 或业务年度 | 分红年度/报告期 |
| `ann_date` | `ANN_DATE` | 公告日期 |
| `progress_code` | `DIV_PROGRESS` 或 `PROGRESS` | 进度代码 |
| `data_json` | 其他 SDK 明细字段 | JSONB object |

原则上，外部服务应优先读取顶层列，不从 `data_json` 中读取元数据。若为了原始数据追溯需要保留完整 SDK payload，可以新增 `raw_json`，或在 `data_json` 中保留镜像字段，但字段字典必须标明顶层列才是权威位置。

### 4.2 字段字典表

建议新增权威字段字典，表名可以是 `data_field_dictionary`。

```sql
CREATE TABLE data_field_dictionary (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    dataset VARCHAR(64) NOT NULL,
    data_type VARCHAR(64) NOT NULL,
    sdk_section VARCHAR(32) NOT NULL,
    sdk_function VARCHAR(64) NOT NULL,
    raw_field VARCHAR(128) NOT NULL,
    canonical_field VARCHAR(128) NOT NULL,
    label_zh VARCHAR(256) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    value_type VARCHAR(32) NOT NULL,
    source_value_type VARCHAR(32) NOT NULL DEFAULT '',
    unit VARCHAR(64) NOT NULL DEFAULT '',
    scale NUMERIC(32, 12),
    enum_ref VARCHAR(64) NOT NULL DEFAULT '',
    storage_location VARCHAR(32) NOT NULL,
    is_metadata BOOLEAN NOT NULL DEFAULT false,
    is_core BOOLEAN NOT NULL DEFAULT false,
    comp_type_scope VARCHAR(64) NOT NULL DEFAULT 'all',
    aliases JSONB NOT NULL DEFAULT '[]',
    examples JSONB NOT NULL DEFAULT '[]',
    source_note TEXT NOT NULL DEFAULT '',
    deprecated BOOLEAN NOT NULL DEFAULT false,
    contract_version VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source, dataset, data_type, raw_field, contract_version)
);
```

关键字段解释:

| 字段 | 说明 |
|-----|------|
| `source` | 数据源，如 `amazing_data` |
| `dataset` | 数据集，如 `financial_statement`、`corporate_action`、`equity_structure` |
| `data_type` | 类型，如 `balance_sheet`、`income`、`cashflow`、`dividend` |
| `raw_field` | AmazingData 原始字段名，如 `TOTAL_ASSETS` |
| `canonical_field` | PhoenixA 推荐字段名，如 `total_assets` |
| `label_zh` | 中文名，如资产总计 |
| `description` | 业务含义和口径 |
| `value_type` | PhoenixA 规范类型，`number`、`string`、`date`、`enum`、`boolean` |
| `source_value_type` | SDK 原始类型，保留 SDK 文档差异 |
| `unit` | 元、万元、股、万股、百分比、元/股等 |
| `scale` | 原始值换算因子，例如万股转股可填 `10000` |
| `enum_ref` | 枚举引用，如 `STATEMENT_TYPE` |
| `storage_location` | `top_level` 或 `data_json` |
| `is_metadata` | 是否为元数据字段 |
| `is_core` | 是否为高频核心字段 |
| `comp_type_scope` | 适用公司类型，`all`、`non_financial`、`bank`、`insurance`、`securities` |
| `aliases` | 别名和历史字段名，用于兼容 SDK 换名或 PDF 断行校正 |
| `source_note` | SDK 章节、人工校验备注、已知问题 |

这张表是外部服务感知字段的唯一权威来源。`schema/fields` 这类动态扫描 API 仍有价值，但应定位为“实际观测字段”，不能替代字段字典。

### 4.3 枚举字典表

建议新增 `data_enum_dictionary`。

```sql
CREATE TABLE data_enum_dictionary (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(32) NOT NULL,
    enum_name VARCHAR(64) NOT NULL,
    code VARCHAR(32) NOT NULL,
    label_zh VARCHAR(256) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_doc VARCHAR(128) NOT NULL DEFAULT '',
    sort_order INT NOT NULL DEFAULT 0,
    contract_version VARCHAR(32) NOT NULL,
    UNIQUE (source, enum_name, code, contract_version)
);
```

至少应先整理:

| 枚举 | 示例 |
|-----|------|
| `REPORT_TYPE` | `1` = 3 月，`2` = 6 月，`3` = 9 月，`4` = 12 月 |
| `STATEMENT_TYPE` | `1` = 合并报表，`2` = 合并报表单季度，`4` = 合并报表调整，`6` = 母公司报表 |
| `DIV_PROGRESS` | `1` = 董事会预案，`2` = 股东大会通过，`3` = 实施 |
| `PROGRESS` | `1` = 董事会预案，`2` = 股东大会通过，`3` = 实施，`5` = 证监会核准 |
| `COMP_TYPE_CODE` | `1` = 非金融，`2` = 银行，`3` = 保险，`4` = 证券 |

## 5. 对外 API 设计

### 5.1 数据集发现

外部服务第一步应能发现 PhoenixA 有哪些数据集。

```http
GET /api/v2/catalog/datasets
```

建议返回:

```json
{
  "datasets": [
    {
      "dataset": "financial_statement",
      "label_zh": "财务报表",
      "source": "amazing_data",
      "types": ["balance_sheet", "income", "cashflow", "profit_express", "profit_notice"],
      "field_discovery": "/api/v2/catalog/datasets/financial_statement/fields",
      "query": "/api/v2/financial/{source}/{statement_type}"
    },
    {
      "dataset": "corporate_action",
      "label_zh": "公司行为",
      "source": "amazing_data",
      "types": ["dividend", "right_issue"],
      "field_discovery": "/api/v2/catalog/datasets/corporate_action/fields",
      "query": "/api/v2/corporate-actions/{source}/{action_type}"
    }
  ]
}
```

### 5.2 字段发现

核心 API:

```http
GET /api/v2/catalog/datasets/{dataset}/fields
```

查询参数:

| 参数 | 说明 |
|-----|------|
| `source` | 数据源，默认 `amazing_data` |
| `type` | `balance_sheet`、`income`、`cashflow`、`dividend` 等 |
| `include` | `core`、`all`、`metadata` |
| `search` | 搜索 raw field、canonical field、中文名、描述 |
| `comp_type_code` | 限定公司类型字段 |
| `with_observed_stats` | 是否返回实际出现次数、覆盖率、最近出现时间 |
| `format` | `full` 或 `compact` |

返回示例:

```json
{
  "dataset": "financial_statement",
  "type": "balance_sheet",
  "source": "amazing_data",
  "contract_version": "2026-06-25",
  "fields": [
    {
      "raw_field": "TOTAL_ASSETS",
      "canonical_field": "total_assets",
      "label_zh": "资产总计",
      "description": "企业在报告期末的资产总额",
      "value_type": "number",
      "unit": "元",
      "storage_location": "data_json",
      "query_name": "TOTAL_ASSETS",
      "is_core": true,
      "source_doc": "AmazingData 3.5.5.1 get_balance_sheet"
    },
    {
      "raw_field": "REPORTING_PERIOD",
      "canonical_field": "reporting_period",
      "label_zh": "报告期",
      "value_type": "date",
      "storage_location": "top_level",
      "query_name": "reporting_period",
      "is_metadata": true,
      "source_doc": "AmazingData 3.5.5.1 get_balance_sheet"
    }
  ]
}
```

这样其他服务即使不知道字段名，也可以搜索:

```http
GET /api/v2/catalog/datasets/financial_statement/fields?type=balance_sheet&search=资产
```

搜索结果应能返回 `TOTAL_ASSETS`、`TOTAL_CUR_ASSETS`、`FIXED_ASSETS` 等字段及含义。

### 5.3 枚举发现

```http
GET /api/v2/catalog/enums/{enum_name}?source=amazing_data
```

例如:

```http
GET /api/v2/catalog/enums/STATEMENT_TYPE?source=amazing_data
```

返回 `code`、`label_zh`、`description`，外部服务不需要再翻 SDK 附录。

### 5.4 数据查询

财务查询:

```http
GET /api/v2/financial/{source}/{statement_type}
```

常用参数:

| 参数 | 说明 |
|-----|------|
| `symbols` | 逗号分隔证券代码，兼容 `000001` 与 `000001.SZ` |
| `start_period` / `end_period` | 报告期范围，兼容 `YYYY-MM-DD` 和 `YYYYMMDD` |
| `ann_start` / `ann_end` | 公告日期范围 |
| `fields` | 投影字段，支持 raw field 和 canonical field |
| `format` | `nested` 或 `flat` |
| `field_profile` | `core`、`all`、自定义 profile |
| `statement_code` | 报表类型代码 |
| `report_type` | 报告期类型 |
| `comp_type_code` | 公司类型 |

例子:

```http
GET /api/v2/financial/amazing_data/balance_sheet?symbols=000001&start_period=2023-01-01&fields=TOTAL_ASSETS,TOTAL_LIAB&format=flat
```

`flat` 返回适合 pandas、因子引擎、BI 工具:

```json
{
  "rows": [
    {
      "source": "amazing_data",
      "symbol": "000001",
      "market": "zh_a",
      "statement_type": "balance_sheet",
      "reporting_period": "2023-12-31",
      "TOTAL_ASSETS": 5600000000000.0,
      "TOTAL_LIAB": 5100000000000.0
    }
  ],
  "fields": [
    {
      "name": "TOTAL_ASSETS",
      "label_zh": "资产总计",
      "unit": "元"
    },
    {
      "name": "TOTAL_LIAB",
      "label_zh": "负债合计",
      "unit": "元"
    }
  ]
}
```

`nested` 返回适合保留原始结构:

```json
{
  "rows": [
    {
      "source": "amazing_data",
      "symbol": "000001",
      "market": "zh_a",
      "statement_type": "balance_sheet",
      "reporting_period": "2023-12-31",
      "data_json": {
        "TOTAL_ASSETS": 5600000000000.0,
        "TOTAL_LIAB": 5100000000000.0
      }
    }
  ]
}
```

公司行为查询同理:

```http
GET /api/v2/corporate-actions/amazing_data/dividend?symbols=000001&fields=DVD_PER_SHARE_PRE_TAX_CASH,DATE_EX&format=flat
```

## 6. 字段清单初版重点

以下不是完整字段字典，而是第一批应标记为 `is_core=true` 的候选字段，便于下游快速使用。

### 6.1 资产负债表 `balance_sheet`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `TOTAL_ASSETS` | 资产总计 | 核心资产规模字段 |
| `TOTAL_LIAB` | 负债合计 | 核心负债规模字段 |
| `TOTAL_CUR_ASSETS` | 流动资产合计 | 流动性分析 |
| `TOTAL_CUR_LIAB` | 流动负债合计 | 流动性分析 |
| `TOT_SHARE_EQUITY_EXCL_MIN_INT` | 归属母公司股东权益合计 | ROE、PB 常用 |
| `TOT_SHARE` | 期末总股本 | SDK 备注单位为股 |
| `CURRENCY_CAP` | 货币资金 | 现金资产 |
| `INV` | 存货 | SDK 原始字段 |
| `GOODWILL` | 商誉 | 资产质量分析 |

### 6.2 利润表 `income`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `TOT_OPERA_REV` | 营业总收入 | 收入规模核心字段 |
| `OPERA_REV` | 营业收入 | 部分报表口径使用 |
| `OPERA_PROFIT` | 营业利润 | 核心利润字段 |
| `TOTAL_PROFIT` | 利润总额 | 核心利润字段 |
| `NET_PRO_EXCL_MIN_INT_INC` | 归属母公司股东净利润 | 最常用净利润口径 |
| `NET_PRO_INCL_MIN_INT_INC` | 净利润 | 含少数股东损益 |
| `BASIC_EPS` | 基本每股收益 | 元/股 |
| `DILUTED_EPS` | 稀释每股收益 | 元/股 |
| `EBIT` | 息税前利润 | 盈利质量和估值 |
| `EBITDA` | 息税折旧摊销前利润 | 盈利质量和估值 |

### 6.3 现金流量表 `cashflow`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `NET_CASH_FLOWS_OPERA_ACT` | 经营活动产生的现金流量净额 | 字段名需按 SDK 原始表校对，避免 PDF 断行误差 |
| `NET_CASH_FLOWS_INV_ACT` | 投资活动产生的现金流量净额 | 同上 |
| `NET_CASH_FLOWS_FIN_ACT` | 筹资活动产生的现金流量净额 | 同上 |
| `FREE_CASH_FLOW` | 自由现金流 | 核心现金流指标 |
| `CASH_RECP_SG_AND_RS` | 销售商品、提供劳务收到的现金 | 收入质量分析 |
| `NET_PROFIT` | 净利润 | 现金流和利润勾稽 |

如果 PhoenixA 现有文档或历史数据中使用 `NET_CASH_FLOW_*` 单数形式，应在字段字典中配置 aliases，而不是让调用方自己猜。

### 6.4 业绩快报 `profit_express`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `TOTAL_ASSETS` | 资产总计 | 快报资产规模 |
| `TOT_OPERA_REV` | 营业总收入 | 快报收入 |
| `OPERA_PROFIT` | 营业利润 | 快报利润 |
| `TOTAL_PROFIT` | 利润总额 | 快报利润 |
| `NET_PRO_EXCL_MIN_INT_INC` | 归属母公司股东净利润 | 核心净利润 |
| `EPS_BASIC` | 基本每股收益 | 注意与利润表 `BASIC_EPS` 建立别名关系 |
| `ROE_WEIGHTED` | 加权平均净资产收益率 | 百分比 |
| `PERFORMANCE_SUMMARY` | 业绩简要说明 | 文本字段 |

### 6.5 业绩预告 `profit_notice`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `P_TYPECODE` | 预告类型代码 | 应建立枚举 |
| `P_CHANGE_MAX` | 净利润变动幅度上限 | 百分比 |
| `P_CHANGE_MIN` | 净利润变动幅度下限 | 百分比 |
| `NET_PROFIT_MAX` | 预计净利润上限 | 单位需校对 |
| `NET_PROFIT_MIN` | 预计净利润下限 | 单位需校对 |
| `FIRST_ANN_DATE` | 首次公告日期 | 时间排序常用 |
| `P_REASON` | 业绩变动原因 | 文本 |
| `P_SUMMARY` | 业绩预告摘要 | 文本 |
| `P_NET_PARENT_FIRM` | 上年同期归母净利润 | 同比计算 |

### 6.6 分红 `dividend`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `DIV_PROGRESS` | 方案进度 | 枚举 `DIV_PROGRESS` |
| `DVD_PER_SHARE_STK` | 每股送转 | 股 |
| `DVD_PER_SHARE_PRE_TAX_CASH` | 每股派息税前 | 元 |
| `DVD_PER_SHARE_AFTER_TAX_CASH` | 每股派息税后 | 元 |
| `DATE_EQY_RECORD` | 股权登记日 | 日期 |
| `DATE_EX` | 除权除息日 | 日期 |
| `DATE_DVD_PAYOUT` | 派息日 | 日期 |
| `DIV_BASESHARE` | 基准股本 | SDK 备注单位为万股 |

### 6.7 配股 `right_issue`

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `PROGRESS` | 方案进度 | 枚举 `PROGRESS` |
| `PRICE` | 配股价格 | 元 |
| `RATIO` | 配股比例 | 比例 |
| `AMT_PLAN` | 配股计划数量 | SDK 备注单位为万股 |
| `AMT_REAL` | 配股实际数量 | SDK 备注单位为万股 |
| `COLLECTION_FUND` | 募集资金 | 元 |
| `SHAREB_REG_DATE` | 股权登记日 | 日期 |
| `EX_DIVIDEND_DATE` | 除权日 | 日期 |

### 6.8 股本结构 `equity_structure`

股本结构来自 `get_equity_structure`，虽然不是财务三张表，但它对估值和因子计算很关键，建议作为独立 dataset 暴露。

| raw_field | 中文含义 | 备注 |
|----------|---------|------|
| `TOT_SHARE` | 总股本 | SDK 备注单位为万股，和资产负债表中的 `TOT_SHARE` 不同 |
| `FLOAT_SHARE` | 流通股本 | 万股 |
| `FLOAT_A_SHARE` | 流通 A 股 | 万股 |
| `ANN_DATE` | 公告日期 | 顶层列 |
| `CHANGE_DATE` | 变动日期 | 核心时间字段 |

这个例子说明字段字典里 `dataset`、`data_type`、`unit`、`scale` 必须同时存在。只看字段名 `TOT_SHARE` 不足以判断含义和单位。

## 7. 写入与读取规则

### 7.1 写入规则

1. `data_json` 入库前必须归一化为 JSON object。如果上游传来 JSON 字符串，应先反序列化再落库。
2. 日期统一存成 `YYYY-MM-DD`。API 输入可以兼容 `YYYYMMDD`，但输出必须统一。
3. 证券代码统一规范化，建议内部用纯代码 + `market`，输入兼容 `000001.SZ`。
4. 顶层元数据字段从 SDK payload 中抽取出来，作为查询权威字段。
5. `data_json` 中保留 AmazingData 原始业务字段名，不在 JSON 内部强行改成 snake_case。
6. 未登记字段不应直接丢弃。建议写入 `unknown_source_fields` 日志或表，供字段字典后续补录。
7. 写入时可做弱校验: 已登记字段检查类型和日期格式，未知字段允许落库但标记为未登记。

### 7.2 读取规则

1. `fields` 参数必须先经过字段字典校验和解析，不能直接拼 SQL。
2. 支持 raw field 和 canonical field 两种写法，但响应中应明确返回实际字段名和中文含义。
3. 默认返回核心字段和元数据；需要完整 JSON 时使用 `fields=*` 或 `format=nested`。
4. 数值过滤必须通过字段字典知道类型后再生成 cast，避免文本比较和 SQL 注入。
5. 字段不存在时返回结构化错误，给出相似字段建议。

示例错误:

```json
{
  "error": "unknown_field",
  "field": "NET_CASH_FLOW_OPER_ACT",
  "dataset": "financial_statement",
  "type": "cashflow",
  "suggestions": [
    {
      "field": "NET_CASH_FLOWS_OPERA_ACT",
      "label_zh": "经营活动产生的现金流量净额"
    }
  ]
}
```

## 8. 与现有 Catalog/Schema API 的关系

PhoenixA 已有 `/api/v2/schema/*`、`/api/v2/catalog/data-dictionary`、`/api/v2/catalog/capabilities` 方向是对的，但需要重新分工。

| 能力 | 推荐定位 |
|-----|---------|
| `data_field_dictionary` | 权威字段含义和查询契约 |
| `schema/fields` | 实际数据观测结果，如出现过哪些 JSON key、覆盖率、样例值 |
| `catalog/data-dictionary` | 对外聚合视图，合并权威字典 + 观测统计 |
| `catalog/capabilities` | 告诉调用方哪些 dataset/type 支持查询、过滤、投影、时间范围 |
| Markdown 表说明 | 人读文档，由字段字典生成或校验 |
| OpenAPI | 由路由和字段字典补充生成，避免手工漂移 |

建议对外推荐入口是:

1. `/api/v2/catalog/datasets`
2. `/api/v2/catalog/datasets/{dataset}/fields`
3. `/api/v2/catalog/enums/{enum_name}`
4. 具体数据查询 API

不要让新服务直接依赖 `schema/fields` 的样本扫描结果做字段契约。

## 9. 索引与视图建议

### 9.1 JSONB 索引

当前迁移中 `data_json` 使用 `jsonb_path_ops`。这个索引适合 containment 和 JSONPath 类查询，但如果 API 明确支持:

```sql
data_json ? 'TOTAL_ASSETS'
```

需要确认执行计划。如果 key-exists 查询是核心能力，建议增加:

```sql
CREATE INDEX idx_fs_data_gin_ops
ON financial_statement USING GIN (data_json jsonb_ops);
```

或针对高频字段建立表达式索引:

```sql
CREATE INDEX idx_fs_total_assets
ON financial_statement (((data_json->>'TOTAL_ASSETS')::numeric))
WHERE statement_type = 'balance_sheet' AND data_json ? 'TOTAL_ASSETS';
```

### 9.2 核心字段视图

为因子引擎、BI、外部服务提供稳定视图，避免每个调用方都写 JSONB cast。

```sql
CREATE VIEW v_financial_balance_sheet_core AS
SELECT
    source,
    symbol,
    market,
    reporting_period,
    report_type,
    statement_code,
    ann_date,
    actual_ann_date,
    comp_type_code,
    (data_json->>'TOTAL_ASSETS')::numeric AS total_assets,
    (data_json->>'TOTAL_LIAB')::numeric AS total_liab,
    (data_json->>'TOT_SHARE_EQUITY_EXCL_MIN_INT')::numeric AS equity_parent
FROM financial_statement
WHERE statement_type = 'balance_sheet';
```

同理可建立:

| 视图 | 用途 |
|-----|------|
| `v_financial_balance_sheet_core` | 资产负债核心字段 |
| `v_financial_income_core` | 利润核心字段 |
| `v_financial_cashflow_core` | 现金流核心字段 |
| `v_financial_profit_express_core` | 快报核心字段 |
| `v_financial_profit_notice_core` | 预告核心字段 |
| `v_corporate_dividend_core` | 分红核心字段 |
| `v_corporate_right_issue_core` | 配股核心字段 |
| `v_equity_structure_core` | 股本结构核心字段 |

视图字段名使用 `canonical_field`，但 API 仍可通过字典返回 raw field 和 canonical field 的映射。

## 10. 落地步骤

### Phase 0: 修正当前风险

1. 写入边界保证 `data_json` 是 JSON object，不是 JSON string。
2. 修正 `fields` 投影实现: 字段必须从字典解析，不能直接拼接用户输入。
3. 统一日期和证券代码格式，输出固定为 `YYYY-MM-DD` 和 `symbol + market`。
4. 明确 `jsonb_path_ops` 与 `?` 查询的索引能力，必要时补 `jsonb_ops` 或表达式索引。

### Phase 1: 建立 AmazingData 字段字典

1. 从 SDK 3.5.5、3.5.6.3、3.5.7 抽取字段。
2. 人工校对 PDF 断行造成的字段名污染。
3. 补全中文含义、类型、单位、枚举、适用公司类型、核心字段标记。
4. 建立 `REPORT_TYPE`、`STATEMENT_TYPE`、`DIV_PROGRESS`、`PROGRESS`、`COMP_TYPE_CODE` 枚举字典。

### Phase 2: 暴露发现 API

1. 新增 `/api/v2/catalog/datasets`。
2. 新增或改造 `/api/v2/catalog/datasets/{dataset}/fields`。
3. 新增 `/api/v2/catalog/enums/{enum_name}`。
4. `catalog/data-dictionary` 聚合字段字典和实际观测统计。

### Phase 3: 改造查询 API

1. `fields` 支持 raw field 和 canonical field。
2. 支持 `format=flat|nested`。
3. 支持字段不存在时返回建议。
4. 根据字段字典生成安全 SQL 投影、cast 和过滤。

### Phase 4: 核心视图和文档生成

1. 为高频字段建立 core views。
2. 由字段字典生成 Markdown 表说明和 OpenAPI 补充描述。
3. 增加字段覆盖率观测任务，发现 SDK 新字段时自动告警或进入待确认列表。

## 11. 判断标准

这套设计完成后，应满足以下使用场景:

1. 外部服务不知道资产负债表字段名，只搜索“资产总计”，能得到 `TOTAL_ASSETS`、单位、含义、查询名。
2. 外部服务不知道现金流字段精确拼写，只搜索“经营活动现金流”，能得到正确字段和别名提示。
3. 外部服务查询 `TOTAL_ASSETS,TOTAL_LIAB` 时，不需要知道这些字段存储在 JSONB 里。
4. 外部服务看到 `TOT_SHARE` 时，能区分资产负债表的股和股本结构的万股。
5. SDK 新增字段后，PhoenixA 能保存数据，并把未登记字段暴露为待治理项，而不是静默丢失。
6. Markdown 文档、OpenAPI、Catalog、查询校验都来自同一份字段字典，不再各自维护。

## 12. 最终建议

保留现有 `financial_statement.data_json` 和 `corporate_action.data_json` 的大方向，但不要把它们当成外部服务直接依赖的接口。下一步最值得做的不是马上拆宽表，而是把 AmazingData SDK 字段沉淀成机器可读字段字典，并围绕它实现字段发现、枚举发现、安全字段投影和核心字段视图。

对 PhoenixA 这种数据中台来说，字段可发现性和字段含义稳定性比物理表是否 JSONB 更关键。只要字段字典成为单一事实源，JSONB 的灵活性和外部服务的易用性可以同时成立。
