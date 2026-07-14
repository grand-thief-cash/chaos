# Factor Engine × PhoenixA 集成复核与因子管理设计

> **Status: Superseded（2026-07-14）**
>
> 本文仅保留作历史记录，已由 `docs/system_design/2026-07-14 FEATURE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md` 替代，不得再作为新开发或验收依据。

日期：2026-05-14

范围：
- `app/projects/artemis/artemis/engines/factor_engine/`
- `app/projects/artemis/artemis/services/factor_service.py`
- `app/projects/phoenixA/docs/api_biz_data_description/`
- `app/projects/phoenixA/internal/controller/`
- `app/projects/cthulhu/src/app/features/workbench/`

---

## 1. 结论摘要

本次 review 的核心结论：

1. **PhoenixA 接口大方向是可接入的**，但 Artemis 当前 factor engine 与 PhoenixA 的**日期格式、财报期字段、股息来源、市值/股本来源、排序方向**存在数个关键 contract drift。
2. **已修正的代码问题**主要集中在：
   - `YYYYMMDD` vs `YYYY-MM-DD` 的日期/报告期不一致
   - `reporting_period` / `report_period` 混用
   - `get_bars()` 默认字段归一化与 provider 侧取 `trade_date` 的冲突
   - `DPS` 被错误地从 `balance_sheet` 读取，实际上应来自 `corporate_action/dividend`
   - `PEG` 原先未实现
   - ranking 忽略 `higher_is_better`
   - `exclude_financial=True` 的因子未真正执行行业/公司类型过滤
3. **当前已可满足计算的因子**：绝大多数财务型因子已经可以算；估值/每股类因子在修复股本与股息来源后也基本能算。
4. **仍然缺少的不是“能不能算”，而是“治理与可追溯性”**：
   - 因子定义
   - PhoenixA 查询链路
   - 字段映射
   - PIT/TTM 规则
   - 使用了哪个底层表/API
   - 当前数据覆盖度/缺口
   - Cthulhu 端的透明展示

因此推荐：**采用“静态结构化因子目录 + 运行态结果/覆盖度落 PhoenixA/DB + Cthulhu 展示”的混合方案**。

当前已落地的第一步（P0 seed）：

- 新增 `app/projects/artemis/config/factor_catalog/manifest.yaml`
- 新增 `app/projects/artemis/config/factor_catalog/factors/governance_seed.yaml`
- 先对治理风险最高的因子补 catalog 元数据：
  - `dividend_yield`
  - `dps`
  - `pe_ttm` / `pb` / `ps_ttm` / `pcf` / `ev_to_ebitda`
  - `roic`
  - `current_ratio` / `quick_ratio`
  - `asset_turnover` / `inventory_turnover` / `receivable_turnover` / `cash_cycle`
- `/factors/meta` 现在已经可输出这些因子的：
  - 描述
  - LaTeX 公式
  - PhoenixA 查询链路
  - 关键 source fields
  - dividend / market-cap governance
  - financial policy

本轮继续扩展后，catalog 已覆盖全部 39 个已注册因子，并增加：

- `availability.expected`
- `availability.requirements`
- `availability.runtime_state`

同时，运行态 snapshot `meta` 已开始输出：

- `reporting_period`
- `latest_ann_date`
- `freshness`
- `company_kind`
- `missing_reasons`

这样静态 catalog 用来回答“这个因子理论上需要什么、应当如何治理”，而 snapshot `meta` 用来回答“这次为什么算出来/没算出来、数据新鲜度如何”。

进一步地，本轮新增了独立的 `GET /factors/availability` 接口：

- 输入：`refresh`（是否刷新 PhoenixA capabilities）
- 输出：
  - factor-level provenance
  - factor-level required fields
  - required data sources
  - PhoenixA source availability
  - availability status（`available / partial / missing / unknown`）

这使得因子管理不再只依赖静态 `/factors/meta` 或单股 snapshot，而是可以独立查看“当前 PhoenixA 数据供给是否足够支撑该因子”。

---

## 2. 本次核对的 PhoenixA 数据接入结果

### 2.1 API / 参数使用是否正确

#### A. `GET /api/v2/securities`

用途：`get_active_symbols()`

当前 Artemis 使用：
- `asset_type=stock`
- `market=zh_a`
- `limit=10000`

结论：**正确**。

参考：
- `phoenixA/docs/api_biz_data_description/securities.md`
- `artemis/core/clients/phoenixA_client.py#get_securities`

---

#### B. `GET /api/v2/taxonomy/by_security/{symbol}`

用途：`get_industry_map()`

结论：**接口选型正确，但原实现匹配规则不够稳**。

问题：
- PhoenixA 文档里 `taxonomy` 可能是 `sw_l1/sw_l2/...`
- 也可能通过 `source=sw/citics` 表示体系来源
- 原实现几乎只按 `source == sw` 且 `taxonomy == industry` 取值，过于死板

本次修正：
- 同时兼容 `taxonomy` 与 `source`
- 对 `sw_*` 与 `citics_*` 做更稳健匹配

结论：**现在可用，但长期建议 PhoenixA 输出一个更明确的“标准化行业层级字段”**。

建议 PhoenixA 在 `GET /api/v2/taxonomy/by_security/{symbol}` 的响应中，新增一组 future-proof 的标准化字段（Artemis 当前实现已经预留兼容读取逻辑）：

- `canonical_source`
- `canonical_taxonomy`
- `canonical_level`
- `canonical_category_code`
- `canonical_category_name`
- `canonical_parent_code`
- `canonical_index_code`
- `derived_flags`

推荐规则：

1. `canonical_source` 只表达分类体系提供方，例如 `sw`、`citics`
2. `canonical_taxonomy` 只表达统一后的体系根，例如 `sw` / `citics`
3. `canonical_level` 明确表达层级（1/2/3），而不是要求调用方从 `sw_l1/sw_l2` 字符串中二次解析
4. `canonical_category_code` / `canonical_parent_code` / `canonical_index_code` 直接给出当前层级所需主键链路
5. `derived_flags.financial_sector` 直接给出金融行业布尔值，避免 Artemis 继续依赖 `comp_type_code + category_code 前缀` 的启发式判断

这样 Artemis / Cthulhu / 其他策略侧都可以统一围绕 `canonical_*` 字段构建行业标准化、行业排除、金融专用因子切换逻辑，而不是各自维护一套 taxonomy 匹配规则。

---

#### C. `GET /api/v2/financial/{source}/{statement_type}`

用途：
- `get_financial_data()`
- `get_current_period()`

结论：**接口选型正确，参数使用基本正确，但需注意文档与实际 controller 存在命名漂移**。

核对结果：
- Artemis 使用了 `ann_date_before`
- PhoenixA `controller` 与 `dao` 实际支持 `ann_date_before`
- Artemis 使用 `page_size`
- PhoenixA controller 实际支持 `period_start` / `period_end`
- PhoenixA controller 实际支持 `reporting_period`
- PhoenixA 实际支持 `reporting_periods`
- PhoenixA controller 的实体字段是 `reporting_period`
- 但业务文档里对象字段部分写成了 `report_period`
- 文档示例曾写成 `start_date/end_date/limit/offset`

结论：
- **代码接实际 controller 是对的**
- **PhoenixA 文档需要修正**：
  - 查询参数统一写为 `period_start` / `period_end` / `page` / `page_size`
  - 财务报表对象字段统一写为 `reporting_period`
  - 文档示例响应统一写为 `{ "data": [...], "total": ... }`
- Artemis `PhoenixAClient.query_financial_statements()` 已同步补齐 `symbols` / `market` / `reporting_period` / `fields` 参数，避免 client contract 再次落后于 controller contract

---

#### D. `GET /api/v2/bars/{asset_type}/{market}`

用途：`get_market_data()`

问题：
- 原 provider 调用 client 的 `get_bars()` 时没有关闭 `normalize_for_cache`
- client 默认会把 `trade_date -> date`、`symbol -> code`
- provider 却继续按 `trade_date` 字段取值，导致 contract 错位

本次修正：
- 显式 `normalize_for_cache=False`
- 显式请求字段 `trade_date,symbol,open,high,low,close,volume,amount`

结论：**现已正确**。

---

#### E. `GET /api/v2/corporate-action/{source}/{action_type}`

用途：
- 股息率 `dividend_yield`
- 每股股利 `dps`

结论：**原本 Artemis 没有正确接入；现在已改为从 dividend corporate action 获取。**

原问题：
- 原实现把 `DPS` 当成 `balance_sheet` 字段读取
- 但 PhoenixA 文档显示每股现金分红字段在：
  - `corporate_action/dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH`

本次修正：
- 扩展 `PhoenixAClient.query_corporate_actions()` 支持：
  - `ann_date_before`
  - `progress_code`
  - `report_period`
  - `fields`
  - `symbols`
- provider 优先查询 `action_type=dividend` 的 `DVD_PER_SHARE_PRE_TAX_CASH`

结论：**股息相关字段来源已经纠正**。

---

## 3. 字段取值与计算方式复核

### 3.1 已确认正确或修正后正确的字段

#### 盈利/成长/质量/偿债/效率主链路

以下字段当前可直接来自 PhoenixA 财务三表：
- `TOTAL_ASSETS`
- `TOTAL_LIAB`
- `TOTAL_CUR_ASSETS`
- `TOTAL_CUR_LIAB`
- `TOT_SHARE_EQUITY_EXCL_MIN_INT`
- `INV`
- `ACCT_RECEIVABLE`
- `ACCT_PAYABLE`
- `CURRENCY_CAP`
- `ST_BORROWING`
- `LT_LOAN`
- `BONDS_PAYABLE`
- `GOODWILL`
- `OPERA_REV`
- `LESS_OPERA_COST`
- `OPERA_PROFIT`
- `NET_PRO_EXCL_MIN_INT_INC`
- `LESS_FIN_EXP`
- `EBITDA`
- `TOTAL_PROFIT`
- `INCOME_TAX`
- `NET_CASH_FLOW_OPERA_ACT`
- `CASH_PAID_PUR_CONST_FIOLTA`

本轮进一步调整为：**Artemis 因子公式直接使用 PhoenixA 标准字段名，不再依赖别名兼容层**。

统一后的关键字段：
- `INCOME_TAX`
- `TOTAL_PROFIT`
- `NET_CASH_FLOW_OPERA_ACT`

原因：

1. PhoenixA 已经形成自己的 canonical data dictionary
2. 因子公式、catalog、Cthulhu 展示、availability 检查都应围绕 canonical name 维护
3. 继续保留别名兼容会让 lineage、字段审计和问题定位越来越模糊

结论：**以 PhoenixA 字段名为单一事实来源更好**，除非未来 PhoenixA 自身发布正式字段迁移计划，否则 Artemis 不再新增历史别名。

---

### 3.2 原本错误、现已修正的字段用法

#### A. `market_cap`

原逻辑：
- 想从 bars DataFrame 里直接拿 `market_cap` 或 `close * total_share`
- 但 provider 没有把 `total_share` 放进 market_data

修正后：
- `close` 来自 bars
- `TOT_SHARE` 来自最新可用资产负债表
- `market_cap = close * TOT_SHARE`

结论：**现已正确**。

---

#### B. `dividend_yield`

原逻辑：
- 从 `balance_sheet.DPS` 读取，错误

修正后：
- 从 `corporate_action(dividend).data_json.DVD_PER_SHARE_PRE_TAX_CASH` 读取
- 再除以 `close`

结论：**现已正确**。

---

#### C. `dps`

原逻辑：
- 从 `balance_sheet.DPS` 读取，错误

修正后：
- 与 `dividend_yield` 一样，来自 dividend corporate action

结论：**现已正确**。

---

#### D. `PEG`

原逻辑：
- 直接返回 `None`

修正后：
- 在 `valuation.py` 内部基于 `PE / 净利润同比增速` 直接计算

说明：
- 这里采用的是 `ni_growth_yoy` 同口径近似
- 若未来要支持多个 growth 定义（营收 PEG、EPS PEG、分析师预期 PEG），应在因子目录里显式区分

结论：**现已可算，但定义需在目录中写明**。

---

#### E. 排名方向

原逻辑：
- `get_ranking()` 永远 `ascending=False`
- 导致像 `pe_ttm/pb/debt_ratio/cash_cycle` 这类“越低越好”的因子排名方向错误

修正后：
- 按 `FactorMeta.higher_is_better` 自动决定排序方向

结论：**现已正确**。

---

#### F. 金融行业排除

原逻辑：
- `FactorMeta.exclude_financial=True` 只是元数据，没有实际执行

修正后：
- 在 `pipeline.py` 里根据：
  - `comp_type_code in {2,3,4}`
  - 或行业代码前缀
- 对标记 `exclude_financial=True` 的因子强制置空

结论：**现已真正生效**。

---

## 4. 哪些 factor 已经能满足计算，哪些还缺

### 4.1 已能稳定计算（修正后）

#### Profitability
- `roe`
- `roa`
- `gross_margin`
- `operating_margin`
- `net_margin`
- `roic`（非金融）

#### Growth
- `revenue_growth_yoy`
- `ni_growth_yoy`
- `revenue_cagr_3y`
- `ni_cagr_3y`
- `ocf_growth`

#### Quality
- `accrual_ratio`
- `cash_conversion`
- `fcf_quality`
- `earnings_stability`
- `goodwill_ratio`

#### Solvency
- `debt_ratio`
- `current_ratio`（非金融）
- `quick_ratio`（非金融）
- `interest_coverage`
- `net_debt_to_ebitda`
- `cash_to_st_debt`

#### Efficiency
- `asset_turnover`（非金融）
- `inventory_turnover`（非金融）
- `receivable_turnover`（非金融）
- `cash_cycle`（非金融）
- `capex_to_revenue`

#### Valuation
- `pe_ttm`
- `pb`
- `ps_ttm`
- `peg`
- `ev_to_ebitda`
- `pcf`
- `dividend_yield`

#### Per Share
- `eps_ttm`
- `bps`
- `cfps`
- `fcf_per_share`
- `dps`

结论：**39 个因子在 PhoenixA 现有数据域下都具备计算基础**。

---

### 4.2 仍然存在的不确定性 / 风险点

这些不是“完全不能算”，而是“定义层面还需要治理”。

#### A. 金融行业专用定义缺失

现在对很多因子采取了“金融行业不算”的处理，这是合理的第一步。

但如果未来希望覆盖银行/保险/券商，需要单独定义：
- 银行版 ROA / ROE / NIM
- 保险版偿付能力、综合成本率
- 券商版资本杠杆与风控指标

#### B. 股息字段的口径治理

当前采用：
- `DVD_PER_SHARE_PRE_TAX_CASH`

仍需明确：
- 税前 / 税后 哪个作为标准口径
- 是否只取实施完成方案（`progress_code=3`）
- 多次方案变更时取哪个版本
- 当年 vs 最近一次已实施分红

#### C. 市值口径治理

当前采用：
- `close * TOT_SHARE`

仍需明确：
- 是总市值还是流通市值
- 使用哪一日 close（自然日 / 最近交易日 / 基准日严格对齐）

#### D. TTM 所需历史覆盖度

公式已支持，但若个股历史期数不足：
- 新股
- 刚上市不足 1 年/3 年
- 财务数据缺失

则会得到 `None`

这不是 bug，而是**覆盖度问题**，需要在因子目录与 UI 中展示“为何无法计算”。

---

## 5. 建议的因子管理设计

这是本次 review 最重要的设计输出。

### 5.1 设计目标

我们需要管理的不是“因子值”本身，而是一个完整链路：

1. 因子定义是什么
2. 因子公式是什么
3. 参数/口径是什么
4. 因子依赖哪些 PhoenixA API
5. PhoenixA API 用了哪些参数
6. 最终用了哪些字段
7. 字段来自哪个 domain/table/source
8. PIT/TTM/行业过滤规则是什么
9. 这个因子当前是否可算，为什么可算/不可算
10. Cthulhu 上如何可视化给人看

---

### 5.2 推荐方案：静态目录 + 运行态数据的 Hybrid

#### 结论

**不要只靠 DB，也不要只靠散落在代码里的 dataclass。**

推荐采用：

- **静态结构化目录（Artemis 仓库）**：维护“定义、公式、参数、数据血缘”
- **运行态状态（PhoenixA / DB）**：维护“覆盖率、最近成功计算、缺失原因、快照产物”
- **Cthulhu**：读取两者聚合后的视图，展示给用户

---

### 5.3 静态目录建议格式

推荐 `YAML`，原因：
- 比 JSON 更适合人工维护
- 比 XML/TOML 更适合嵌套说明、数组、长公式、备注
- Git diff 友好
- 适合作为仓库内 source of truth

建议目录：

```text
app/projects/artemis/config/factor_catalog/
  manifest.yaml                  # 总索引
  factors/
    profitability/roe.yaml
    profitability/roa.yaml
    valuation/pe_ttm.yaml
    valuation/dividend_yield.yaml
    per_share/dps.yaml
```

单因子文件建议字段：

```yaml
name: dividend_yield
cn_name: 股息率
category: valuation
status: active
version: v1
formula:
  text: DPS / Close
  latex: "\\frac{DPS}{P}"
  description: 使用最近一次已实施现金分红（税前）除以基准日收盘价
parameters:
  dividend_progress_code:
    type: string
    default: "3"
    meaning: 仅取实施完成分红方案
  price_date_policy:
    type: string
    default: exact_or_previous_trade_date
    meaning: 基准日停牌时回退至最近交易日
computation:
  pit_required: true
  ttm_required: false
  exclude_financial: false
  min_history_quarters: 0
phoenixA_contract:
  apis:
    - endpoint: /api/v2/corporate-action/amazing_data/dividend
      params:
        symbol: "{symbol}"
        ann_date_before: "{as_of_date}"
        progress_code: "3"
      fields:
        - ann_date
        - report_period
        - data_json.DVD_PER_SHARE_PRE_TAX_CASH
    - endpoint: /api/v2/bars/stock/zh_a
      params:
        symbol: "{symbol}"
        start_date: "{as_of_date}"
        end_date: "{as_of_date}"
        period: daily
        adjust: nf
      fields:
        - trade_date
        - close
lineage:
  source_domains:
    - corporate_action.dividend
    - bars.daily
  source_fields:
    - corporate_action.data_json.DVD_PER_SHARE_PRE_TAX_CASH
    - bars.close
availability:
  expected: calculable
  risks:
    - no_dividend_history
    - suspended_on_as_of_date
output:
  unit: ratio
  higher_is_better: true
```

---

### 5.4 为什么不是“接口 + DB 全托管”

如果把“因子定义本身”也完全放进 DB：

优点：
- 可动态增改
- UI 改起来灵活

缺点：
- 公式/血缘/规则变更不再走 code review
- 难与实际计算代码保持版本一致
- 容易出现“DB 配置写的是 A，代码算的是 B”

所以：
- **定义层**（formula/description/lineage/contract）最好静态化、版本化
- **运行层**（覆盖率/最新结果/失败原因）适合进 DB

这就是 hybrid 方案优于纯 DB 的原因。

---

### 5.5 参考 `factors.directory` 的组织方式

你提到的 `app/tools/py/crawler/factors_directory/data.min.json` 很有参考价值。

该数据结构的关键点：
- `title`
- `explanation`
- `description`
- `tags`
- `formulas`
- `formulaExplanation`
- `references`
- `related`

建议 Artemis 的因子目录也吸收这些维度，但**不要直接照搬**，而要补上与 PhoenixA 深度绑定的技术字段：

新增维度：
- `phoenixA_contract`
- `source_domains`
- `source_fields`
- `pit_required`
- `ttm_required`
- `data_quality_rules`
- `availability_requirements`
- `validation_cases`

这才是适合你们项目的 factor catalog。

---

## 6. Cthulhu 侧展示建议

### 6.1 不要只做一个“Factor Registry 表格”

当前页面仅展示：
- 名称
- 分类
- 公式
- 是否需要行情

这远远不够。

建议拆成 4 个视图：

#### A. 因子目录页（Catalog）
展示：
- name / cn_name / category
- 简短定义
- 公式（支持 LaTeX 渲染）
- higher_is_better
- unit
- 是否 PIT / TTM
- 是否排除金融
- 当前状态：active / draft / deprecated

#### B. 数据血缘页（Lineage）
展示：
- 这个因子调用了哪些 PhoenixA API
- 每个 API 用了什么参数
- 取了哪些字段
- 字段分别来自哪个 domain/table/source
- PIT / TTM / 行业过滤规则

建议做成可展开的 DAG / step list。

#### C. 覆盖率页（Availability）
展示：
- 当前哪些市场可算
- 哪些 symbol 可算比例
- 最近一次全量计算成功率
- 缺失最多的字段是什么
- 新股/金融行业/分红缺失导致的不可算比例

#### D. 结果页（Snapshot / Ranking）
保留当前已有能力，但增加：
- 因子值说明
- 当前使用的 reporting_period
- ann_date
- 数据新鲜度
- 因子缺失原因

---

### 6.2 UI 字段建议

Cthulhu 的 `FactorMeta` 建议最终包含：
- `name`
- `cn_name`
- `category`
- `formula`
- `latex_formula`
- `description`
- `data_sources`
- `source_fields`
- `requires_market_data`
- `ttm_required`
- `min_history_quarters`
- `exclude_financial`
- `higher_is_better`
- `status`
- `coverage_status`
- `last_verified_at`

本次代码里已先把 `data_sources / ttm_required / min_history_quarters` 暴露到 registry payload，作为后续 UI 扩展起点。

---

## 7. PhoenixA / Artemis 后续建议

### 7.1 建议 PhoenixA 文档修订

需要修正文档与实际 controller 不一致的问题：

#### 财务报表文档
- 文档对象字段处写成了 `report_period`
- 实际返回/模型字段是 `reporting_period`

建议统一为：
- 财务报表：`reporting_period`
- 公司行为：`report_period`

#### 响应示例
部分示例直接返回数组，但 controller 实际是：
```json
{"data": [...], "total": N}
```
建议统一示例。

---

### 7.2 建议 Artemis 下一阶段实现

1. 引入 `factor catalog` 静态 YAML 目录
2. 在 `registry.py` 中支持从静态 catalog 装载补充元数据
3. 新增 `factor lineage / availability` service
4. 让 `scripts/check_factor_availability.py` 读取 catalog，而不是手写 requirements
5. 将“无法计算原因”一起写入 factor snapshot meta

---

## 8. 本次代码改动对应的 review 结论

本次已落地修正：

- `ttm.py`
  - 增加日期/报告期标准化
  - 增加 PhoenixA 字段 alias 兼容
  - 支持从 index/`report_period` 读取 period

- `phoenixA_client.py`
  - 扩展 corporate action 查询参数，支持股息因子

- `providers/phoenixa_provider.py`
  - 修复 bars 字段归一化 contract drift
  - 财报 period/date 统一规范化
  - 从 `TOT_SHARE` 补 `total_share`
  - 从 dividend corporate action 补 `dps`
  - 补 `market_cap`

- `factors/valuation.py`
  - 实现 `PEG`
  - `dividend_yield` 改为用 dividend 数据
  - `EV/EBITDA` 优先使用 PhoenixA `EBITDA`

- `factors/per_share.py`
  - `shares` 改为优先 `market_data.total_share`，回退 `balance_sheet.TOT_SHARE`
  - `dps` 改为 dividend 数据

- `pipeline.py`
  - 让 `exclude_financial=True` 真正生效

- `services/factor_service.py`
  - 统一 `as_of_date` 格式
  - ranking 支持按因子元数据决定排序方向

- `registry.py`
  - 暴露更丰富的元数据字段

- `cthulhu`
  - 同步元数据类型
  - 修正实际分类色彩映射

- `tests/`
  - 增加针对 period normalization、field alias、PEG、股本/股息来源、provider enrichment 的测试

---

## 9. 最终建议

### 推荐最终架构

**A. Artemis 仓库内静态 YAML 因子目录**
- 维护定义、公式、参数、字段来源、PhoenixA contract、validation case

**B. PhoenixA / DB 维护运行态状态**
- 因子快照
- 因子覆盖率
- 缺失原因
- 最新计算时间
- 最新验证状态

**C. Cthulhu 展示管理视图**
- Catalog
- Lineage
- Availability
- Snapshot/Ranking

这是最适合你们当前项目阶段的方案：
- 可审计
- 可 code review
- 可演进
- 可视化清楚
- 不会把 definition 和 runtime state 混在一起

---

## 10. 待办清单

建议下一阶段按优先级执行：

### P0
- [ ] 新建 `factor_catalog` YAML 目录
- [ ] 将 39 个因子的 PhoenixA contract 和字段血缘补齐
- [ ] 给 snapshot 增加 `reporting_period/ann_date/missing_reason/freshness`

### P1
- [ ] 给 Cthulhu 增加 Catalog / Lineage / Availability 三个视图
- [ ] 让 availability checker 从 catalog 自动生成检查逻辑

### P2
- [ ] 为金融行业补充专用 fundamental factors
- [ ] 增加 LaTeX 公式渲染与 references 展示
- [ ] 将 factor definition version 与 snapshot version 绑定

---

如需下一步继续，我建议直接进入 **“P0：落地 factor_catalog YAML 目录 + registry loader + Cthulhu catalog 页面扩展”**。
