# 因子引擎数据供给设计 — 需求/供应 Gap 分析

## 背景

Artemis factor_engine 计算 7 类 36 个因子（盈利、成长、质量、偿债、估值、效率、每股）。
因子计算需要从 PhoenixA 获取财务报表、行情、行业分类数据。
本文档分析数据需求 vs 当前 API 供给的 gap，以及 LLM function calling 的集成路径。

---

## 1. 因子引擎数据需求清单

### 1.1 FactorDataProvider 接口

```python
class FactorDataProvider(Protocol):
    def get_active_symbols(market, as_of_date) -> List[str]
    def get_industry_map(taxonomy, market) -> Dict[str, str]
    def get_financial_data(symbol, as_of_date) -> Dict[str, pd.DataFrame]
    def get_market_data(symbol, as_of_date) -> Optional[pd.DataFrame]
    def get_current_period(symbol, as_of_date) -> Optional[str]
```

### 1.2 各接口需要的数据字段

**get_financial_data** — 需要返回 `{statement_type: DataFrame}`：
- `balance_sheet`: TOTAL_ASSETS, TOTAL_LIAB, TOT_SHARE_EQUITY_EXCL_MIN_INT, CUR_ASSETS, CUR_LIAB, INV, ACCT_RECEIVABLE, ACCT_PAYABLE, CURRENCY_CAP, ST_BORROWING, LT_LOAN, BONDS_PAYABLE, GOODWILL 等 47 个字段
- `income`: OPERA_REV, LESS_OPERA_COST, OPERA_PROFIT, NET_PRO_EXCL_MIN_INT_INC, LESS_FIN_EXP, INC_TAX 等 39 个字段
- `cashflow`: NET_CASH_FLOWS_OPER_ACT, CASH_PAID_PUR_CONST_FIOLTA 等 36 个字段

**get_market_data** — 需要返回行情 DataFrame：
- close（收盘价）、volume、market_cap（市值）、total_share（总股本）

**get_industry_map** — 需要返回 `{symbol: industry_code}`：
- 申万一级分类映射

**get_active_symbols** — 当前上市证券列表

**get_current_period** — 某股票某日期的最新报告期

### 1.3 特殊需求

- **TTM 计算**: 需要**多个报告期**的历史数据（当前期 + 上年年报 + 上年同期），至少 5 个季度
- **PIT (Point-in-Time)**: 需要按 ann_date（披露日期）过滤，避免未来数据
- **单季度推导**: 从累计值推导单季度值（Q2累计 - Q1累计 = Q2单季）

---

## 2. 当前 PhoenixA API 供给

### 2.1 已有 API 能力

| API | 端点 | 能力 | 因子引擎可用性 |
|-----|------|------|-------------|
| 财务报表查询 | `GET /api/v2/financial/{source}/{statement_type}?symbol=&page=&page_size=` | 按类型查询单个股票 | ✅ 可用 |
| 行情查询 | `GET /api/v2/bars/{asset_type}/{market}?symbol=&start_date=&end_date=` | 日K线 OHLCV | ✅ 可用 |
| 证券列表 | `GET /api/v2/securities?market=` | 证券基础信息 | ✅ 可用 |
| 行业映射 | `GET /api/v2/taxonomy/by_security/{symbol}` | 证券→行业映射 | ✅ 可用 |
| 行业分类 | `GET /api/v2/taxonomy/{source}/{taxonomy}/{market}/categories` | 行业分类列表 | ✅ 可用 |
| Schema 发现 | `GET /api/v2/schema/fields?domain=&type=` | JSONB 字段列表 | ✅ 可用 |
| Data Dictionary | `GET /api/v2/catalog/data-dictionary` | 完整数据元数据 | ✅ LLM 可用 |

### 2.2 字段覆盖验证

balance_sheet 的 47 个字段全部在 `data_json` JSONB 列中，PhoenixA API 通过 `/api/v2/financial/amazing_data/balance_sheet?symbol=000001` 可查到完整数据。

income 的 39 个字段和 cashflow 的 36 个字段同理。

---

## 3. Gap 分析

### 3.1 已满足的需求 ✅

| 需求 | 对应 API | 状态 |
|------|---------|------|
| 财务报表查询（按类型、按股票） | `GET /api/v2/financial/{source}/{type}` | ✅ 完全满足 |
| 日K线行情 | `GET /api/v2/bars/stock/zh_a` | ✅ 完全满足 |
| 证券列表 | `GET /api/v2/securities` | ✅ 完全满足 |
| 行业映射 | `GET /api/v2/taxonomy/by_security/{symbol}` | ✅ 完全满足 |
| JSONB 字段发现 | `GET /api/v2/schema/fields` | ✅ 完全满足 |
| 数据元数据（LLM 用） | `GET /api/v2/catalog/data-dictionary` | ✅ 完全满足 |

### 3.2 部分满足的需求 ⚠️

| 需求 | 当前能力 | Gap |
|------|---------|-----|
| 多报告期历史数据 | API 支持分页查询，但需要多次请求 | 缺少 `reporting_periods` 批量查询参数 |
| PIT 过滤 | `ann_date` 列存在于数据中，但 API 不支持按 ann_date 过滤 | API 缺少 `ann_date_before` 参数 |
| 市值数据 | bars 表只有 OHLCV，没有 market_cap | 缺少市值数据源 |
| 总股本 | securities 表可能有但未确认字段 | 需验证 security_registry 是否有 total_share |

### 3.3 未满足的需求 ❌

| 需求 | 说明 | 优先级 |
|------|------|--------|
| **PIT 查询参数** | `ann_date_before` 过滤，避免未来数据穿透 | **高** |
| **多报告期批量查询** | 一次请求获取多个 period 的数据用于 TTM | **高** |
| **市值数据** | 因子计算（PE/PB/PS/EV）需要当日市值 | **高** |
| **最新报告期查询** | `get_current_period` 按股票+日期返回最新报告期 | **中** |
| **总股本/流通股** | 每股指标计算需要 | **中** |

---

## 4. LLM Function Calling 集成路径

### 4.1 数据字典 API → LLM 工具注册

`GET /api/v2/catalog/data-dictionary` 返回完整的表结构、字段、JSONB 键、API 端点。
LLM 可以通过此 API 理解：
- 哪些表存在、字段含义
- 如何构造查询（API 端点 + 参数）
- 表之间的关联关系

### 4.2 方案选择：Skill 文件 vs 设计文档

| 维度 | Skill 文件 | 设计文档 |
|------|-----------|---------|
| 目的 | 指导 LLM 行为 | 指导开发者实现 |
| 因子计算 | ❌ 太复杂，不适合纯 prompt | ✅ 需要代码逻辑 |
| 数据查询 | ✅ 适合告诉 LLM 怎么查数据 | — |
| 结论 | 适合**数据访问层** | 适合**因子计算层** |

**建议**: 两者都做
1. **设计文档**（本文档）— 指导 PhoenixA API 扩展和 Artemis factor_engine 的数据对接
2. **Skill 文件**（`app/tools/py/skills/`）— 当因子计算中需要 LLM 辅助时（如定性分析、异常检测），提供数据查询能力

### 4.3 当前阶段不需要 Skill

因子计算是纯数值计算（TTM、比率、Z-Score），不涉及自然语言处理。
LLM Function Calling 适用于：
- **未来**: 定性因子（管理层质量、ESG 分析）需要 LLM 读财报文本
- **当前**: 数据字典 API 帮助**开发者**理解数据结构，而非直接让 LLM 做因子计算

---

## 5. 推荐实施路径

### Phase 1 — API 扩展（高优先）

1. **财务报表 API 增加 PIT 支持**:
   - `GET /api/v2/financial/{source}/{type}?symbol=000001&ann_date_before=20250101`
   - 过滤 `ann_date <= ann_date_before`，避免未来数据穿透
   - 文件: `internal/dao/financial_statement_dao.go`

2. **财务报表 API 增加多报告期查询**:
   - `GET /api/v2/financial/{source}/{type}?symbol=000001&periods=20240930,20240630,20231231`
   - 批量返回多个 period 的数据，减少 HTTP 请求次数

3. **市值数据写入和查询**:
   - 新增 `security_dev.daily_valuation` 表或扩展现有 bars 表
   - 包含: symbol, trade_date, market_cap, total_share, float_share
   - API: `GET /api/v2/bars/stock/zh_a?symbol=000001&fields=close,market_cap,total_share`

### Phase 2 — Data Provider 实现（中优先）

4. **Artemis PhoenixADataProvider**:
   - 实现 `FactorDataProvider` 接口
   - 通过 HTTP 调用 PhoenixA API 获取数据
   - 文件: `artemis/engines/factor_engine/data_provider.py`

5. **FactorStore 切换到 PhoenixA**:
   - 替换内存存储为 HTTP 调用
   - API: `POST /api/v2/factor/snapshot/upsert`

### Phase 3 — LLM 集成（低优先，按需）

6. **Skill 文件**:
   - 当需要 LLM 参与因子计算时（定性因子），创建数据查询 skill
   - 利用 data-dictionary API 注册工具

---

## 6. 因子覆盖度矩阵

### 盈利能力 (Profitability) — 6 因子

| 因子 | 需要数据 | 数据源 | 状态 |
|------|---------|--------|------|
| roe | NI_TTM, equity | balance_sheet + income | ✅ 数据充足 |
| roa | NI_TTM, total_assets | balance_sheet + income | ✅ 数据充足 |
| gross_margin | REV_TTM, COST_TTM | income | ✅ 数据充足 |
| operating_margin | OPERA_PROFIT_TTM, REV_TTM | income | ✅ 数据充足 |
| net_margin | NI_TTM, REV_TTM | income | ✅ 数据充足 |
| roic | NOPAT, invested_capital | balance_sheet + income | ✅ 数据充足 |

### 估值 (Valuation) — 7 因子

| 因子 | 需要数据 | 数据源 | 状态 |
|------|---------|--------|------|
| pe_ttm | market_cap, NI_TTM | **行情+income** | ⚠️ 缺市值数据 |
| pb | market_cap, equity | **行情+balance_sheet** | ⚠️ 缺市值数据 |
| ps_ttm | market_cap, REV_TTM | **行情+income** | ⚠️ 缺市值数据 |
| peg | pe, growth | 上述 | ⚠️ 依赖 pe |
| ev_to_ebitda | EV, EBITDA | **行情+income+balance_sheet** | ⚠️ 缺 EV 数据 |
| pcf | market_cap, OCF_TTM | **行情+cashflow** | ⚠️ 缺市值数据 |
| dividend_yield | DPS, close | **行情+corporate_action** | ✅ 有 close，DPS 需确认 |

### 每股指标 (Per Share) — 5 因子

| 因子 | 需要数据 | 数据源 | 状态 |
|------|---------|--------|------|
| eps_ttm | NI_TTM, total_share | income + **行情** | ⚠️ 缺总股本 |
| bps | equity, total_share | balance_sheet + **行情** | ⚠️ 缺总股本 |
| cfps | OCF_TTM, total_share | cashflow + **行情** | ⚠️ 缺总股本 |
| fcf_per_share | FCF_TTM, total_share | cashflow + **行情** | ⚠️ 缺总股本 |
| dps | dividends, total_share | corporate_action + **行情** | ⚠️ 缺总股本 |

### 其他 4 类 — 18 因子

成长、质量、偿债、效率类因子主要依赖财务报表历史数据（多期），
**数据充足**但需要 PIT 过滤和多期批量查询能力。

---

## 7. 总结

### ~~最大 Gap~~: 市值 + 总股本数据 — 已解决 ✅

**总股本**: balance_sheet.data_json 中已有 `TOT_SHARE` 字段（如 000001 = 19,406,000,000）。
无需额外数据源。

**市值**: 可通过 `close_price × TOT_SHARE` 计算。close 来自 bars_daily，TOT_SHARE 来自 balance_sheet。
因子引擎在运行时组合这两个数据即可，不需要 PhoenixA 额外存储。

**备选数据源**（如需独立市值数据）:
- AmazingData `get_equity_structure` 提供完整的股本结构（总股本、流通A股、限售股等）
- akshare `stock_zh_scale_comparison_em` 提供总市值、流通市值（但不是按日时序）
- 推荐：因子引擎用 `close × TOT_SHARE` 计算每日市值，最准确

### ~~第二 Gap~~: PIT 查询 — 已解决 ✅

已为 financial_statement 和 corporate_action API 新增 `ann_date_before` 参数。
用法: `GET /api/v2/financial/amazing_data/balance_sheet?symbol=000001&ann_date_before=2025-06-30`

### ~~第三 Gap~~: 多期批量查询 — 已解决 ✅

已为 financial_statement API 新增 `reporting_periods` 参数。
用法: `GET /api/v2/financial/amazing_data/balance_sheet?symbol=000001&reporting_periods=2024-12-31,2024-09-30,2024-06-30`

### 新增 API 参数总结

因子计算的 Point-in-Time 正确性需要 `ann_date_before` 过滤。
当前 API 不支持，会导致**未来数据穿透**（look-ahead bias）。

### 第三 Gap: 多期批量查询

TTM 计算需要 5+ 个季度的历史数据。当前 API 一次只返回一个结果集，
需要分页多次请求，效率低。

### 数据字典 API 评估

✅ **对 LLM function calling 可用**：结构完整、字段描述清晰、包含 API 端点映射。
✅ **对开发者有用**：可直接用于理解数据结构、构建查询。
⚠️ **当前不急需 Skill 文件**：因子计算是数值计算，不需要 LLM 参与。
