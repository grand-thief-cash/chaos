# 2026-05-08 因子化财务数据引擎设计

> 更新日期：2026-05-08 (rev.2 — 修正/优化/扩展)  
> 关联文档：`2026-04-26 FINANCIAL_DATA_FIELDS.md`, `2026-05-07 FINANCIAL_DATA_PG_MIGRATION.md`  
> 影响范围：Artemis (Python), PhoenixA (Go), PostgreSQL

---

## 一、背景与目标

### 1.1 为什么需要因子化？

原始财务报表（资产负债表/利润表/现金流量表）存储的是绝对数值，无法直接用于量化策略：

- **不可比性**：茅台 ROE 31% vs 银行 ROE 12%，单看净利润无意义
- **量纲差异**：营收亿级 vs EPS 几元，不做标准化无法跨指标组合
- **时序变化**：策略关注的是"变化趋势"而非"绝对水平"

因子化的核心是：**从原始三表 + 行情数据中，派生出可量化、可比较、可排序的标准化指标**。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **存原始，算因子** | 因子是从原始数据实时/批量计算的产物，不替代原始数据 |
| **因子可重算** | 算法迭代后可全量重新计算，不依赖历史因子快照 |
| **行业标准化** | 跨行业比较必须做 z-score，否则金融 vs 科技无法排序 |
| **时间对齐** | 财务数据有滞后性（Q1 报告 4 月才出），必须用 point-in-time 避免未来函数 |
| **增量计算** | 日常只计算新发布报表涉及的股票，全量重算仅做定期校验 |
| **字段命名单一事实来源** | 因子计算统一直接使用 PhoenixA canonical 字段名，不再在 Artemis 内部维持历史字段别名 |

---

### 1.3 因子目录与治理（2026-05-14 补充）

因子引擎除了“能算”，还必须可治理、可追溯、可在 Cthulhu 清晰展示。因此新增一个静态结构化因子目录作为 P0 起点：

```text
app/projects/artemis/config/factor_catalog/
├── manifest.yaml
└── factors/
    └── governance_seed.yaml
```

该目录当前优先记录治理风险最高的因子（股息、市值、金融行业排除相关），字段包括：

- 因子解释描述
- LaTeX 公式
- PhoenixA 查询接口
- 查询参数
- 使用字段
- dividend / market-cap 口径治理说明
- financial policy（标准定义 / 金融专用定义待补 / 排除）

实现推进后，catalog 已扩展为覆盖全部 39 个已注册因子，并补充静态 availability 信息：

- `availability.expected`
- `availability.requirements`
- `availability.runtime_state`

与之对应，运行态 snapshot `meta` 负责记录：

- `reporting_period`
- `latest_ann_date`
- `freshness`
- `company_kind`
- `missing_reasons`

因此当前设计已经明确分层：

1. **静态 catalog**：定义、公式、数据来源、治理规则、理论可用条件
2. **运行态 snapshot meta**：本次计算的数据时效、新鲜度、未算出原因

在此基础上，又补充了第三层：

3. **独立 availability 接口**：聚合 factor catalog 与 PhoenixA `/api/v2/catalog/capabilities`，输出 factor-level provenance、required fields、required data sources、source availability、availability status

因此因子管理链路现在已经形成：

- `/factors/meta` → 静态定义与治理
- `/factors/availability` → 平台级可用性与数据供给状态
- `/factors/snapshot` → 单标的、单日期运行态结果与 missing_reason

后续 P1/P2 再把全部 39 个因子迁移到 catalog，并把 coverage / freshness / missing_reason 接入运行态管理。

---

## 二、因子体系设计

### 2.1 因子分类总览

```
Fundamental Factors
├── 1. 盈利能力 (Profitability)
│   ├── ROE (净资产收益率)
│   ├── ROA (总资产收益率)
│   ├── Gross Margin (毛利率)
│   ├── Operating Margin (营业利润率)
│   ├── Net Margin (净利率)
│   └── ROIC (投入资本回报率)
│
├── 2. 成长性 (Growth)
│   ├── Revenue Growth YoY (营收同比增长)
│   ├── Net Income Growth YoY (净利润同比增长)
│   ├── Revenue CAGR 3Y (3 年营收复合增长)
│   ├── Net Income CAGR 3Y (3 年净利润复合增长)
│   ├── Operating Cash Flow Growth (经营现金流增长)
│   └── EPS Growth (每股收益增长)
│
├── 3. 质量 (Quality)
│   ├── Accrual Ratio (应计比率)
│   ├── Cash Conversion (现金转换率)
│   ├── FCF/Net Income (自由现金流/净利润)
│   ├── Earnings Stability (盈利稳定性)
│   ├── Revenue Concentration (营收集中度 - 如有分部数据)
│   └── Goodwill/Assets (商誉占比)
│
├── 4. 偿债能力 (Solvency)
│   ├── Debt/Equity (资产负债率)
│   ├── Current Ratio (流动比率)
│   ├── Quick Ratio (速动比率)
│   ├── Interest Coverage (利息保障倍数)
│   ├── Net Debt/EBITDA (净负债/EBITDA)
│   └── Cash/Short-term Debt (现金/短期有息负债)
│
├── 5. 估值 (Valuation) — 需要行情数据联动
│   ├── PE_TTM (市盈率 TTM)
│   ├── PB (市净率)
│   ├── PS_TTM (市销率 TTM)
│   ├── PEG (市盈率/增长率)
│   ├── EV/EBITDA (企业价值/EBITDA)
│   ├── PCF (市现率)
│   └── Dividend Yield (股息率)
│
├── 6. 营运效率 (Efficiency)
│   ├── Asset Turnover (总资产周转率)
│   ├── Inventory Turnover (存货周转率)
│   ├── Receivable Turnover (应收账款周转率)
│   ├── Cash Cycle (现金循环天数)
│   └── Capex/Revenue (资本支出/营收)
│
└── 7. 每股指标 (Per Share)
    ├── EPS_TTM (每股收益 TTM)
    ├── BPS (每股净资产)
    ├── CFPS (每股经营现金流)
    ├── FCF Per Share (每股自由现金流)
    └── DPS (每股股利)
```

### 2.2 因子计算公式

#### 2.2.1 盈利能力

| 因子 | 公式 | 数据来源 |
|------|------|---------|
| **ROE** | `NI_TTM / avg(TOT_SHARE_EQUITY_EXCL_MIN_INT)` | income + balance_sheet |
| **ROA** | `NI_TTM / avg(TOTAL_ASSETS)` | income + balance_sheet |
| **Gross Margin** | `(OPERA_REV_TTM - LESS_OPERA_COST_TTM) / OPERA_REV_TTM` | income |
| **Operating Margin** | `OPERA_PROFIT_TTM / OPERA_REV_TTM` | income |
| **Net Margin** | `NI_TTM / OPERA_REV_TTM` | income |
| **ROIC** | `NOPAT_TTM / Invested_Capital_avg` | income + balance_sheet |

> **NI** = `NET_PRO_EXCL_MIN_INT_INC`（归母净利润）
> **NOPAT** = `OPERA_PROFIT_TTM × (1 - effective_tax_rate)`，其中 `effective_tax_rate = INCOME_TAX / TOTAL_PROFIT`（取最近年报的实际税率）
> **Invested_Capital** = `TOT_SHARE_EQUITY_EXCL_MIN_INT + ST_BORROWING + LT_LOAN + BONDS_PAYABLE - CURRENCY_CAP`（股东权益 + 有息负债 - 现金）
> 
> **TTM 处理**：利润表/现金流量表使用 TTM 转换（详见第四章）；资产负债表使用期初期末均值。
> 
> ⚠️ **金融行业（银行/保险/证券）**：ROIC 不适用（有息负债不是"投入资本"而是"经营负债"），设为 NaN。详见第十一章。

#### 2.2.2 成长性

| 因子 | 公式 | 说明 |
|------|------|------|
| **Revenue Growth YoY** | `REV_single_Q(t) / REV_single_Q(t-4Q) - 1` | 单季度同比，避免季节性 |
| **Net Income Growth YoY** | `NI_single_Q(t) / NI_single_Q(t-4Q) - 1` | 单季度同比 |
| **Revenue CAGR 3Y** | `(REV_TTM(t) / REV_TTM(t-12Q))^(1/3) - 1` | 3 年复合（用 TTM 消除季节性） |
| **Net Income CAGR 3Y** | `(NI_TTM(t) / NI_TTM(t-12Q))^(1/3) - 1` | 3 年复合 |
| **OCF Growth** | `OCF_TTM(t) / OCF_TTM(t-4Q) - 1` | 经营现金流增长 |

> ⚠️ **关键区分**：
> - **单季度同比**：比较的是"本季度 vs 去年同季度"的单季度值（从累计值推导，见第四章）
> - **CAGR**：比较的是 TTM（最近 12 个月）vs N 年前的 TTM
> 
> **边界处理**：
> - 分母为零：返回 NaN
> - 分母为负（去年亏损，今年盈利）：使用特殊处理 `(NI_now - NI_prev) / abs(NI_prev)`，结果 > 1 表示扭亏为盈
> - 分子分母均为负（连续亏损）：比较亏损缩窄/扩大，`1 - NI_now/NI_prev`
> - 上市不满 4 季度：返回 NaN

#### 2.2.3 质量

| 因子 | 公式 | 说明 |
|------|------|------|
| **Accrual Ratio** | `(NI_TTM - OCF_TTM) / avg(TOTAL_ASSETS)` | 越低越好，说明利润有现金支撑 |
| **Cash Conversion** | `OCF_TTM / NI_TTM` | 经营现金流 / 净利润，> 1 为佳 |
| **FCF Quality** | `FREE_CASH_FLOW_TTM / NI_TTM` | 自由现金流覆盖率 |
| **Earnings Stability** | 见下方 | 盈利稳定性，越低越稳定 |
| **Goodwill Ratio** | `GOODWILL / TOTAL_ASSETS` | 商誉占比，过高有减值风险 |

> **Earnings Stability 特殊处理**：
> 
> 原版公式 `std(NI, 8Q) / mean(NI, 8Q)` 即变异系数（CV），但当 mean 趋近 0 时 CV 发散到无穷大，失去意义。
> 
> 修正方案：
> ```python
> def earnings_stability(ni_quarterly: pd.Series) -> float:
>     """
>     使用 "标准差 / 均值绝对值" 作为稳定性度量
>     当 abs(mean) < threshold 时，退化为纯标准差的排名
>     """
>     mean_ni = ni_quarterly.mean()
>     std_ni = ni_quarterly.std()
>     
>     if abs(mean_ni) < 1e-8:  # 均值趋近零
>         # 用标准差的行业内排名替代（越小越稳定）
>         return std_ni  # 后续 Z-Score 时自然处理
>     
>     return std_ni / abs(mean_ni)  # 使用绝对值，处理持续亏损公司
> ```
> 
> **Window 选择**：使用最近 8 个单季度（2 年），而非 8 个累计期。需要先从累计值推导单季度值。

#### 2.2.4 偿债能力

| 因子 | 公式 | 说明 |
|------|------|------|
| **Debt Ratio** | `TOTAL_LIAB / TOTAL_ASSETS` | 资产负债率 |
| **Current Ratio** | `TOTAL_CUR_ASSETS / TOTAL_CUR_LIAB` | 流动比率 |
| **Quick Ratio** | `(TOTAL_CUR_ASSETS - INV) / TOTAL_CUR_LIAB` | 速动比率 |
| **Interest Coverage** | `EBIT_TTM / LESS_FIN_EXP_TTM` | 利息保障倍数 |
| **Net Debt/EBITDA** | `(ST_BORROWING + LT_LOAN - CURRENCY_CAP) / EBITDA_TTM` | 净负债 / EBITDA |
| **Cash/ST Debt** | `CURRENCY_CAP / (ST_BORROWING + NONCUR_LIAB_DUE_WITHIN_1Y)` | 现金覆盖短债 |

#### 2.2.5 估值（需要行情数据）

| 因子 | 公式 | 数据来源 |
|------|------|---------|
| **PE_TTM** | `market_cap / NI_TTM` | 行情（收盘价×总股本）+ income |
| **PB** | `market_cap / TOT_SHARE_EQUITY_EXCL_MIN_INT` | 行情 + balance_sheet |
| **PS_TTM** | `market_cap / REV_TTM` | 行情 + income |
| **PEG** | `PE_TTM / (NI_Growth_YoY × 100)` | PE + 增长率 |
| **EV/EBITDA** | `(market_cap + net_debt) / EBITDA_TTM` | 行情 + balance_sheet + income |
| **PCF** | `market_cap / OCF_TTM` | 行情 + cashflow |
| **Dividend Yield** | `DVD_PER_SHARE_PRE_TAX_CASH / close_price` | corporate_action + 行情 |

> ⚠️ **市值计算说明**：
> - `market_cap = close_price × total_shares`（总股本，非流通股本）
> - `total_shares` 当前统一来源：PhoenixA `financial/balance_sheet.data_json.TOT_SHARE`
> - A 股有 "总股本" vs "流通A股" vs "自由流通股本"，**估值因子统一使用总股本**（与行业惯例一致）
> - 如果 `total_shares` 数据有变动（增发/回购），需使用**当日有效的总股本**（PIT 对齐）

> ⚠️ **股息口径治理说明**：
> - `Dividend Yield` / `DPS` 当前统一使用 `corporate_action/dividend.data_json.DVD_PER_SHARE_PRE_TAX_CASH`
> - 查询时优先 `progress_code=3`（已实施）；若无实施方案，则回退到 `as_of_date` 前最新可用公告，并在 catalog / 管理页明确标记 fallback
> - 当前不纳入送股/转增，也不切换税后口径
> 
> **EV（企业价值）详细定义**：
> ```
> EV = market_cap + 有息负债 - 现金及现金等价物
>    = close × total_shares + ST_BORROWING + LT_LOAN + BONDS_PAYABLE 
>      - CURRENCY_CAP - TRADABLE_FIN_ASSETS(短期理财)
> ```
> 
> **PEG 特殊处理**：
> - NI_Growth_YoY ≤ 0 时，PEG 无意义，设为 NaN
> - PE_TTM < 0（亏损）时，PEG 无意义，设为 NaN
> - 通常 PEG < 1 被认为低估

#### 2.2.6 营运效率

| 因子 | 公式 | 说明 |
|------|------|------|
| **Asset Turnover** | `REV_TTM / avg(TOTAL_ASSETS)` | 总资产周转率 |
| **Inventory Turnover** | `LESS_OPERA_COST_TTM / avg(INV)` | 存货周转率 |
| **Receivable Turnover** | `OPERA_REV_TTM / avg(ACCT_RECEIVABLE)` | 应收周转率 |
| **Cash Cycle** | `DSO + DIO - DPO` | 现金循环天数 |
| **Capex/Revenue** | `CASH_PAID_PUR_CONST_FIOLTA_TTM / REV_TTM` | 资本密集度 |

---

## 三、行业标准化（Z-Score）

### 3.1 为什么必须标准化？

| 行业 | ROE 均值 | 标准差 | 茅台 ROE=31% 的含义 |
|------|---------|--------|-------------------|
| 白酒 | 25% | 8% | z = +0.75（行业内中上） |
| 银行 | 12% | 3% | z = +6.3（如果是银行就逆天了） |

不做标准化，跨行业排序毫无意义。

### 3.2 标准化流程

```
原始因子值
    │
    ▼
┌─────────────────────────────────┐
│ Step 1: 去极值 (Winsorize)       │
│   MAD 法：中位数 ± 5×MAD        │
│   或 percentile: clip(1%, 99%)  │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Step 2: 行业内 Z-Score           │
│   z = (x - μ_industry) / σ_ind  │
│   使用 申万一级行业 分组          │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Step 3: 市值中性化 (可选)         │
│   对 ln(market_cap) 回归取残差    │
│   消除大小盘偏差                  │
└────────────────┬────────────────┘
                 │
                 ▼
标准化因子值 (可跨行业比较/排序)
```

### 3.3 行业分类数据源

使用 PhoenixA 中已有的 `taxonomy_category` + `taxonomy_security_map` 表：
- 行业体系：申万一级（31 个行业）
- 将每只股票映射到所在一级行业
- 因子标准化时按行业分组

### 3.4 标准化参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 去极值方法 | MAD | 比 percentile 对极端值更鲁棒 |
| MAD 倍数 | 5 | 超过中位数 ± 5×MAD 的值被 clip |
| Z-Score 分组 | 申万一级行业 | 31 个行业 |
| 最小样本量 | 10 | 行业内股票数 < 10 时不做标准化，保留原始值 |
| 市值中性化 | 可选开关 | 估值因子通常不做，盈利因子可做 |

> ⚠️ **MAD = 0 退化处理**：
> 当行业内某因子所有值相同（或大部分相同）时，MAD = 0，此时：
> - 不做 winsorize（全体相同无需去极值）
> - Z-Score 时如果 std = 0，该行业所有股票的标准化值设为 0.0（无区分度）
>
> ⚠️ **MAD 倍数选择**：
> 学术常用 3×MAD（≈2σ），但 A 股因子分布往往重尾（例如亏损公司的 PE 极端值）。
> 选 5×MAD 是为了保留更多信息避免过度截断，后续可根据 IC 分析下调到 3-4。

---

## 四、TTM 与 Point-in-Time 处理

### 4.1 中国财报的累计值特性（核心前提）

> ⚠️ **这是中国财报与欧美财报最大的不同，也是很多因子计算出错的根源。**

中国上市公司的利润表和现金流量表报告的是**年初至期末的累计值**，而非单季度值：

```
Q1 报告:  Jan-Mar 累计
Q2 报告:  Jan-Jun 累计（半年报）
Q3 报告:  Jan-Sep 累计（三季报）
Q4 报告:  Jan-Dec 累计（年报）

因此:
  单季度 Q2 = Q2累计 - Q1累计
  单季度 Q3 = Q3累计 - Q2累计
  单季度 Q4 = Q4累计(年报) - Q3累计
  单季度 Q1 = Q1累计本身
```

资产负债表则是**时点数据**（报告期末的余额），不需要做累计/单季度转换。

### 4.2 TTM（Trailing Twelve Months）计算

TTM = 最近 12 个月的合计值，消除季节性。

```python
def compute_ttm(symbol: str, field: str, as_of_report: str, 
                all_reports: pd.DataFrame) -> Optional[float]:
    """
    TTM 计算
    
    公式（核心）:
      TTM = 当期累计值 + 上年年报 - 上年同期累计值
    
    示例:
      2025Q3 的 TTM营收
      = 2025前三季度累计营收 + 2024全年营收 - 2024前三季度累计营收
      = (Jan-Sep 2025) + (Jan-Dec 2024) - (Jan-Sep 2024)
      = Oct2024-Sep2025 的合计（即最近12个月）
    
    特殊情况:
      - 当期是年报 (Q4): TTM = 年报值本身
      - 缺少上年年报或上年同期: 返回 NaN
      - 刚上市不满1年: 返回 NaN
    
    参数:
      as_of_report: 当前最新报告期, e.g. "20250930" (Q3)
      all_reports: 该股票所有已披露的报表数据
    """
    quarter = get_quarter(as_of_report)  # 1/2/3/4
    year = get_year(as_of_report)        # 2025
    
    if quarter == 4:
        # 年报本身就是全年数据
        return get_value(all_reports, as_of_report, field)
    
    # 当期累计值
    current_cumulative = get_value(all_reports, as_of_report, field)
    # 上年年报
    prev_annual = get_value(all_reports, f"{year-1}1231", field)
    # 上年同期累计值
    prev_same_period = get_value(all_reports, f"{year-1}{as_of_report[4:]}", field)
    
    if any_none(current_cumulative, prev_annual, prev_same_period):
        return None
    
    return current_cumulative + prev_annual - prev_same_period
```

### 4.3 单季度值推导

成长因子的 YoY 比较需要**单季度值**：

```python
def compute_single_quarter(symbol: str, field: str, report_period: str,
                           all_reports: pd.DataFrame) -> Optional[float]:
    """
    从累计值推导单季度值
    
    逻辑:
      Q1: 单季度 = Q1累计值（本身就是单季度）
      Q2: 单季度 = Q2累计 - Q1累计
      Q3: 单季度 = Q3累计 - Q2累计
      Q4: 单季度 = Q4累计(年报) - Q3累计
    """
    quarter = get_quarter(report_period)
    year = get_year(report_period)
    
    current_cumulative = get_value(all_reports, report_period, field)
    if current_cumulative is None:
        return None
    
    if quarter == 1:
        return current_cumulative
    
    # 上一期的累计值
    prev_period = get_prev_period(year, quarter)  # e.g. Q3 → Q2: "20250630"
    prev_cumulative = get_value(all_reports, prev_period, field)
    
    if prev_cumulative is None:
        return None
    
    return current_cumulative - prev_cumulative
```

### 4.4 Point-in-Time（避免未来函数）

```
时间线:
  2025-03-31  Q1 季报截止日
  2025-04-20  某公司实际披露 Q1 报告 (ann_date)
  
  如果在 2025-04-15 做回测:
    ❌ 不能使用 Q1 数据（还未披露）
    ✅ 只能使用最新已披露的数据（2024 年报）
```

**实现方式**：

```python
def get_latest_available_reports(symbol: str, as_of_date: str) -> pd.DataFrame:
    """
    获取截至某日期已公开披露的所有报表
    
    核心逻辑:
      1. 查 financial_statement WHERE symbol=? AND ann_date <= as_of_date
      2. ⚠️ 按 (reporting_period, ann_date) 去重 —— 同一期可能有多次披露:
         - 业绩预告 → 业绩快报 → 正式报表 → 报表修订
         - 取每个 reporting_period 中 ann_date 最大（最新修订版本）的那条
      3. 排除掉 ann_date > as_of_date 的记录（即未来数据）
    
    ⚠️ 边缘情况:
      - 公司延迟披露 Q2（Q3 先出）：以各自的 ann_date 为准，不假设顺序
      - 报表重述：同一 reporting_period 可能有多个 ann_date，取最新
      - 业绩快报 vs 正式报表：如果正式报表未出，可选是否采纳快报
    
    SQL 示例:
      SELECT DISTINCT ON (reporting_period, statement_type)
             *
      FROM financial_statement
      WHERE symbol = $1 AND ann_date <= $2
      ORDER BY reporting_period DESC, statement_type, ann_date DESC;
    """
```

使用 `ann_date`（实际公告日期）而非 `reporting_period`（报告期）作为时间标尺。

### 4.5 数据新鲜度（Staleness）

> **新增**：因子值的可靠性随时间衰减。

```python
@dataclass
class FactorFreshness:
    """因子数据新鲜度评估"""
    latest_reporting_period: str      # 最新可用报告期 e.g. "20250630"
    latest_ann_date: str              # 最新披露日期
    as_of_date: str                   # 因子计算基准日
    staleness_days: int               # = as_of_date - latest_ann_date
    staleness_quarters: int           # 当前日期距离理论最新季报的季度数
    
    @property
    def freshness_score(self) -> float:
        """
        新鲜度评分 (0.0 - 1.0)
        
        - 1.0: 刚披露的报表（< 30天）
        - 0.8: 1个季度前的报表（正常）
        - 0.5: 2个季度前（有点旧了）
        - 0.3: 3个季度以上（很可能有问题）
        
        用途: 
          - 策略层可以按 freshness_score 过滤
          - 综合评分时作为权重衰减因子
        """
        if self.staleness_days <= 30:
            return 1.0
        elif self.staleness_days <= 120:
            return 0.8
        elif self.staleness_days <= 210:
            return 0.5
        else:
            return 0.3
```

> **meta JSONB 中存储**：`{"freshness_score": 0.8, "staleness_days": 85, "latest_report": "20250630"}`

---

## 五、架构设计

### 5.1 模块结构

```
artemis/
├── engines/
│   └── factor_engine/                    ← 新增：因子引擎
│       ├── __init__.py
│       ├── registry.py                   # 因子注册表（所有因子的元数据）
│       ├── pipeline.py                   # 因子计算 Pipeline 协调器
│       ├── ttm.py                        # TTM 计算器
│       ├── normalizer.py                 # 标准化/去极值/Z-Score
│       ├── point_in_time.py              # PIT 时间对齐
│       │
│       ├── factors/                      # 各类因子计算实现
│       │   ├── __init__.py
│       │   ├── base.py                   # BaseFactor 抽象类
│       │   ├── profitability.py          # 盈利能力因子组
│       │   ├── growth.py                 # 成长性因子组
│       │   ├── quality.py                # 质量因子组
│       │   ├── solvency.py              # 偿债能力因子组
│       │   ├── valuation.py             # 估值因子组（需行情数据）
│       │   ├── efficiency.py            # 营运效率因子组
│       │   └── per_share.py             # 每股指标因子组
│       │
│       └── storage/                      # 因子存储（对接 PhoenixA）
│           ├── __init__.py
│           └── factor_store.py           # 因子读写 Client
│
├── services/
│   └── factor_service.py                 # 因子计算服务（暴露 API）
│
└── api/
    └── factor_api.py                     # HTTP 路由（Trigger 计算 / 查询因子）
```

### 5.2 核心类设计

```python
# ─── registry.py ───────────────────────────────────────────

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class FactorCategory(Enum):
    PROFITABILITY = "profitability"
    GROWTH = "growth"
    QUALITY = "quality"
    SOLVENCY = "solvency"
    VALUATION = "valuation"
    EFFICIENCY = "efficiency"
    PER_SHARE = "per_share"

@dataclass
class FactorMeta:
    """因子元数据"""
    name: str                          # 英文标识 e.g. "roe"
    cn_name: str                       # 中文名 e.g. "净资产收益率"
    category: FactorCategory           # 分类
    formula: str                       # 公式描述
    data_sources: List[str]            # 依赖数据源 ["income", "balance_sheet"]
    requires_market_data: bool = False # 是否需要行情数据
    higher_is_better: bool = True      # 排序方向（用于因子评分）
    ttm_required: bool = False         # 利润表/现金流类是否需要 TTM
    unit: str = ""                     # 单位 "%", "倍", "天"
    exclude_financial: bool = False    # 是否排除金融行业（ROIC/存货周转等）
    min_history_quarters: int = 4      # 计算所需最少历史季报数（如 CAGR 3Y 需 12）

FACTOR_REGISTRY: Dict[str, FactorMeta] = {}

def register_factor(meta: FactorMeta):
    """注册因子到全局注册表"""
    FACTOR_REGISTRY[meta.name] = meta
```

```python
# ─── factors/base.py ───────────────────────────────────────

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Optional

class BaseFactor(ABC):
    """所有因子组的基类"""
    
    @abstractmethod
    def compute(
        self,
        symbol: str,
        financial_data: Dict[str, pd.DataFrame],  # {statement_type: DataFrame}
        market_data: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Optional[float]]:
        """
        计算一只股票在最新披露期的所有因子值
        
        Returns:
            {"roe": 0.31, "roa": 0.15, ...}
            值为 None 表示无法计算（数据缺失）
        """
        pass
    
    @abstractmethod
    def compute_batch(
        self,
        symbols: List[str],
        as_of_date: str,
        financial_data: Dict[str, Dict[str, pd.DataFrame]],
        market_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """
        批量计算多只股票的因子
        
        Returns:
            DataFrame with columns = factor names, index = symbols
        """
        pass
```

```python
# ─── factors/profitability.py ──────────────────────────────

class ProfitabilityFactors(BaseFactor):
    """盈利能力因子组"""
    
    FACTORS = [
        FactorMeta(name="roe", cn_name="净资产收益率", ...),
        FactorMeta(name="roa", cn_name="总资产收益率", ...),
        FactorMeta(name="gross_margin", cn_name="毛利率", ...),
        FactorMeta(name="operating_margin", cn_name="营业利润率", ...),
        FactorMeta(name="net_margin", cn_name="净利率", ...),
        FactorMeta(name="roic", cn_name="投入资本回报率", ...),
    ]
    
    def compute(self, symbol, financial_data, market_data=None):
        income = financial_data.get("income")
        balance = financial_data.get("balance_sheet")
        
        # TTM 净利润
        ni_ttm = self._ttm(income, "NET_PRO_EXCL_MIN_INT_INC")
        # 期初期末平均股东权益
        equity_avg = self._avg_balance(balance, "TOT_SHARE_EQUITY_EXCL_MIN_INT")
        
        roe = safe_div(ni_ttm, equity_avg)
        # ... 其他因子
        
        return {"roe": roe, "roa": roa, ...}
```

```python
# ─── normalizer.py ─────────────────────────────────────────

class FactorNormalizer:
    """因子标准化处理器"""
    
    def winsorize_mad(self, series: pd.Series, n: float = 5.0) -> pd.Series:
        """
        MAD 去极值
        
        ⚠️ 退化处理: MAD = 0 时（所有值相同或集中在中位数），不做截断
        """
        valid = series.dropna()
        if len(valid) < 3:
            return series
        
        median = valid.median()
        mad = (valid - median).abs().median()
        
        if mad < 1e-10:  # MAD ≈ 0，几乎所有值相同
            return series  # 不截断
        
        # MAD 转换为等效标准差: σ ≈ 1.4826 × MAD
        mad_scaled = 1.4826 * mad
        upper = median + n * mad_scaled
        lower = median - n * mad_scaled
        return series.clip(lower, upper)
    
    def zscore_by_industry(
        self,
        factor_df: pd.DataFrame,     # index=symbol, columns=factors
        industry_map: Dict[str, str], # symbol -> industry_code
        min_samples: int = 10,
    ) -> pd.DataFrame:
        """
        按行业做 Z-Score 标准化
        
        ⚠️ 改进:
          - std = 0 时返回 0.0（全行业一致，无区分度）
          - NaN 不参与均值/标准差计算
          - 存储行业统计量供增量计算使用
        """
        factor_df = factor_df.copy()
        factor_df["_industry"] = factor_df.index.map(industry_map)
        
        result = pd.DataFrame(index=factor_df.index)
        self._industry_stats = {}  # 存储行业统计量（增量计算用）
        
        for col in factor_df.columns:
            if col == "_industry":
                continue
            
            stats = {}
            z_values = pd.Series(index=factor_df.index, dtype=float)
            
            for industry, group in factor_df.groupby("_industry")[col]:
                valid = group.dropna()
                
                if len(valid) < min_samples:
                    # 样本太少，保留原始值（不做行业内标准化）
                    z_values.loc[group.index] = group
                    stats[industry] = {"mean": None, "std": None, "n": len(valid)}
                    continue
                
                mean = valid.mean()
                std = valid.std()
                stats[industry] = {"mean": mean, "std": std, "n": len(valid)}
                
                if std < 1e-10:  # std ≈ 0，全行业一致
                    z_values.loc[group.index] = 0.0
                else:
                    z_values.loc[group.index] = (group - mean) / std
            
            result[col] = z_values
            self._industry_stats[col] = stats
        
        return result
    
    def get_industry_stats(self) -> Dict:
        """获取最近一次全量计算的行业统计量（增量计算时复用）"""
        return self._industry_stats
    
    def zscore_incremental(
        self,
        factor_values: Dict[str, float],  # 单只股票的因子值
        industry_code: str,
        stored_stats: Dict,               # 上次全量计算的行业统计量
    ) -> Dict[str, float]:
        """
        增量标准化：用存储的行业均值/标准差对单只股票做标准化
        
        注意: 增量标准化有偏差（因为行业均值是上次全量的），
              每周全量重算时会修正。
        """
        result = {}
        for factor_name, raw_value in factor_values.items():
            if raw_value is None:
                result[factor_name] = None
                continue
            
            stats = stored_stats.get(factor_name, {}).get(industry_code)
            if stats is None or stats["mean"] is None:
                result[factor_name] = raw_value
                continue
            
            if stats["std"] < 1e-10:
                result[factor_name] = 0.0
            else:
                result[factor_name] = (raw_value - stats["mean"]) / stats["std"]
        
        return result
    
    def market_cap_neutralize(
        self,
        factor_series: pd.Series,
        log_market_cap: pd.Series,
    ) -> pd.Series:
        """市值中性化：对 ln(market_cap) 回归取残差"""
        import statsmodels.api as sm
        
        valid = factor_series.dropna().index.intersection(log_market_cap.dropna().index)
        if len(valid) < 30:  # 样本太少，不做中性化
            return factor_series
        
        X = sm.add_constant(log_market_cap.loc[valid])
        y = factor_series.loc[valid]
        model = sm.OLS(y, X).fit()
        residual = model.resid
        return residual
```

```python
# ─── pipeline.py ───────────────────────────────────────────

class FactorPipeline:
    """因子计算 Pipeline 协调器"""
    
    def __init__(self, phoenixa_client, factor_store):
        self.client = phoenixa_client
        self.store = factor_store
        self.normalizer = FactorNormalizer()
        
        # 注册所有因子组
        self.factor_groups = [
            ProfitabilityFactors(),
            GrowthFactors(),
            QualityFactors(),
            SolvencyFactors(),
            ValuationFactors(),
            EfficiencyFactors(),
            PerShareFactors(),
        ]
    
    async def run_full(self, as_of_date: str, market: str = "zh_a"):
        """全量因子计算 Pipeline"""
        
        # 1. 获取所有活跃股票
        symbols = await self.client.get_active_symbols(market)
        
        # 2. 获取行业映射
        industry_map = await self.client.get_industry_map(taxonomy="sw_l1")
        
        # 3. 批量拉取财务数据（PIT 对齐）
        financial_data = await self._fetch_financial_pit(symbols, as_of_date)
        
        # 4. 批量拉取行情数据（估值因子需要）
        market_data = await self._fetch_market_data(symbols, as_of_date)
        
        # 5. 计算原始因子
        raw_factors = pd.DataFrame(index=symbols)
        for group in self.factor_groups:
            group_result = group.compute_batch(
                symbols, as_of_date, financial_data, market_data
            )
            raw_factors = raw_factors.join(group_result)
        
        # 6. 去极值
        winsorized = raw_factors.apply(self.normalizer.winsorize_mad)
        
        # 7. 行业 Z-Score 标准化
        normalized = self.normalizer.zscore_by_industry(
            winsorized, industry_map
        )
        
        # 8. 存储因子快照
        await self.store.save_factor_snapshot(
            as_of_date=as_of_date,
            market=market,
            raw_factors=raw_factors,
            normalized_factors=normalized,
        )
        
        # 9. 存储行业统计量（供增量计算复用）
        await self.store.save_industry_stats(
            as_of_date=as_of_date,
            market=market,
            stats=self.normalizer.get_industry_stats(),
        )
        
        return normalized
    
    async def run_incremental(self, symbols: List[str], as_of_date: str):
        """
        增量计算（仅新披露报表的股票）
        
        策略:
          1. 算原始因子值（只算指定股票）
          2. 用最近一次全量计算存储的行业均值/标准差做标准化
          3. 标记 meta.incremental=true，下次全量时会覆盖
          
        局限性:
          - 增量标准化有微小偏差（行业均值没更新）
          - 每周六全量重算时自动修正
        """
        # 1. 加载上次全量计算的行业统计量
        industry_stats = await self.store.load_industry_stats(as_of_date)
        if industry_stats is None:
            # 没有历史统计量，降级为全量计算
            return await self.run_full(as_of_date)
        
        # 2. 拉取指定股票的财务+行情数据
        financial_data = await self._fetch_financial_pit(symbols, as_of_date)
        market_data = await self._fetch_market_data(symbols, as_of_date)
        industry_map = await self.client.get_industry_map(taxonomy="sw_l1")
        
        # 3. 计算原始因子
        for symbol in symbols:
            raw = {}
            for group in self.factor_groups:
                raw.update(group.compute(symbol, financial_data[symbol], market_data.get(symbol)))
            
            # 4. 用存储的行业统计量做增量标准化
            industry_code = industry_map.get(symbol, "unknown")
            normalized = self.normalizer.zscore_incremental(raw, industry_code, industry_stats)
            
            # 5. 存储（带增量标记）
            await self.store.save_single_factor(
                symbol=symbol,
                as_of_date=as_of_date,
                raw_factors=raw,
                norm_factors=normalized,
                meta={"incremental": True, "industry_code": industry_code},
            )
```

### 5.3 数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        因子计算数据流                                        │
│                                                                             │
│  ┌───────────┐     HTTP      ┌───────────┐                                 │
│  │ PhoenixA  │◄─────────────►│  Artemis   │                                │
│  │ (数据网关) │               │ (因子引擎) │                                │
│  └─────┬─────┘               └─────┬─────┘                                │
│        │                           │                                        │
│        │ SQL                       │ Pipeline                               │
│        ▼                           ▼                                        │
│  ┌───────────┐         ┌─────────────────────────┐                         │
│  │PostgreSQL │         │ Factor Computation       │                         │
│  │           │         │                          │                         │
│  │ financial_│────────►│ 1. Fetch (PIT aligned)   │                         │
│  │ statement │         │ 2. TTM computation       │                         │
│  │           │         │ 3. Factor formulas       │                         │
│  │ bars_*    │────────►│ 4. Winsorize             │                         │
│  │ (行情)    │         │ 5. Industry Z-Score      │                         │
│  │           │         │ 6. Store results         │                         │
│  │ taxonomy_ │────────►│                          │                         │
│  │ (行业)    │         └────────────┬────────────┘                         │
│  │           │                      │                                       │
│  │ factor_   │◄─────────────────────┘                                       │
│  │ snapshot  │   存储因子快照                                                │
│  └───────────┘                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、存储设计

### 6.1 因子快照表（PhoenixA / PostgreSQL）

```sql
-- 因子快照表：存储每次全量计算的结果
-- 存储位置：NVMe（默认表空间），预计 30-80 GB（5000股 × 40+因子 × 10年）
CREATE TABLE factor_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,         -- 证券代码
    market          VARCHAR(16) NOT NULL,         -- zh_a / hk / us
    as_of_date      DATE NOT NULL,                -- 因子计算基准日
    category        VARCHAR(32) NOT NULL,         -- profitability/growth/...
    factor_name     VARCHAR(64) NOT NULL,         -- roe/roa/...
    raw_value       DOUBLE PRECISION,             -- 原始因子值
    normalized_value DOUBLE PRECISION,            -- 标准化后因子值 (z-score)
    industry_code   VARCHAR(16),                  -- 申万一级行业代码
    reporting_period VARCHAR(10),                 -- 所用报表的报告期
    ann_date        VARCHAR(10),                  -- 所用报表的公告日期
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- 唯一约束：同一股票同一基准日同一因子只有一条
    CONSTRAINT uq_factor_snapshot 
        UNIQUE (symbol, market, as_of_date, factor_name)
);

-- 索引
CREATE INDEX idx_fs_symbol_date ON factor_snapshot (symbol, as_of_date DESC);
CREATE INDEX idx_fs_date_category ON factor_snapshot (as_of_date, category);
CREATE INDEX idx_fs_industry ON factor_snapshot (industry_code, as_of_date, factor_name);

-- 按日期分区（可选，数据量大时启用）
-- CREATE TABLE factor_snapshot (...) PARTITION BY RANGE (as_of_date);
```

### 6.2 替代方案：宽表 + JSONB

```sql
-- 替代方案：每只股票每天一行，所有因子存 JSONB
-- 优点：行数少（5000股 × 250天/年 = 125万行/年）
-- 缺点：不便于单因子排序查询
CREATE TABLE factor_snapshot_wide (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,
    market          VARCHAR(16) NOT NULL,
    as_of_date      DATE NOT NULL,
    industry_code   VARCHAR(16),
    raw_factors     JSONB,              -- {"roe": 0.31, "roa": 0.15, ...}
    norm_factors    JSONB,              -- {"roe": 1.2, "roa": 0.8, ...}
    meta            JSONB,              -- {"reporting_period": "20250331", ...}
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uq_fsw UNIQUE (symbol, market, as_of_date)
);

CREATE INDEX idx_fsw_factors_gin ON factor_snapshot_wide USING GIN (norm_factors jsonb_path_ops);
```

### 6.3 推荐方案

**采用宽表 (factor_snapshot_wide)**：

| 考量 | 宽表 | 长表 |
|------|------|------|
| 行数 | 125 万/年 | 5000 万/年（40因子） |
| 单股时序查询 | 快（一行出全部因子） | 需 40 次或 pivot |
| 全市场单因子排序 | `norm_factors->>'roe'` + GIN | 快（直接 WHERE + ORDER） |
| 存储空间 | 小（JSONB 压缩） | 大（重复 symbol/date） |
| 扩展性 | 加因子无需改表 | 加因子无需改表 |

→ 选宽表。全市场排序场景用 Generated Column 或物化视图解决。

---

## 七、计算调度

### 7.1 调度策略

| 场景 | 触发方式 | 频率 | 说明 |
|------|---------|------|------|
| **日频估值因子** | cronjob 触发 | 每交易日收盘后 | PE/PB/PS 等需要当日行情 |
| **财报发布增量** | 事件触发 | 财报季密集 | 新报表发布后重算相关股票 |
| **全量重算** | 手动/周末 | 每周六 | 校验 + 更新行业分组变化 |
| **历史回填** | 手动 | 一次性 | 初始化历史因子数据（回测需要） |

### 7.2 调度时间线

```
交易日:
  15:00  A 股收盘
  15:30  行情数据入库完毕（bars_* 更新）
  16:00  估值因子计算（PE/PB/PS/PEG/EV-EBITDA/PCF/DY）
  16:30  完成，结果写入 factor_snapshot_wide

财报季 (4月/8月/10月):
  每日:  检查新披露报表（ann_date = today）
         增量重算涉及股票的全部因子
  周末:  全量重算 + Z-Score 刷新

每周六:
  06:00-07:00  财务数据同步（已有调度）
  10:00        全量因子重算
  11:00        完成
```

### 7.3 API 设计

```python
# ─── factor_api.py ─────────────────────────────────────────

@router.post("/factors/compute/full")
async def compute_factors_full(
    market: str = "zh_a",
    as_of_date: Optional[str] = None,  # 默认今天
):
    """触发全量因子计算"""
    pass

@router.post("/factors/compute/incremental")
async def compute_factors_incremental(
    symbols: List[str],
    as_of_date: Optional[str] = None,
):
    """增量因子计算（指定股票）"""
    pass

@router.get("/factors/snapshot")
async def get_factor_snapshot(
    symbol: str,
    market: str = "zh_a",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    categories: Optional[List[str]] = None,
):
    """查询单股因子时序"""
    pass

@router.get("/factors/rank")
async def get_factor_ranking(
    factor_name: str,
    as_of_date: str,
    market: str = "zh_a",
    industry: Optional[str] = None,  # 可选按行业筛选
    top_n: int = 50,
):
    """全市场因子排名"""
    pass

@router.get("/factors/composite")
async def get_composite_score(
    symbol: str,
    as_of_date: str,
    weights: Optional[Dict[str, float]] = None,
):
    """综合评分（加权多因子）"""
    pass

@router.get("/factors/meta")
async def get_factor_meta():
    """获取所有因子元数据（名称/公式/分类）"""
    pass
```

---

## 八、与策略引擎的集成

### 8.1 回测中使用因子

```python
# 在策略中使用因子数据
class FactorStrategy(BaseStrategy):
    """多因子选股策略示例"""
    
    def __init__(self):
        self.factor_weights = {
            "roe": 0.2,
            "revenue_growth_yoy": 0.15,
            "cash_conversion": 0.15,
            "current_ratio": 0.1,
            "pe_ttm": -0.2,        # 负权重：PE 越低越好
            "dividend_yield": 0.1,
            "asset_turnover": 0.1,
        }
    
    def select_stocks(self, as_of_date: str) -> List[str]:
        """基于多因子综合评分选股"""
        # 获取全市场因子快照
        snapshot = self.factor_store.get_normalized_snapshot(as_of_date)
        
        # 加权求和
        composite = pd.Series(0.0, index=snapshot.index)
        for factor, weight in self.factor_weights.items():
            if factor in snapshot.columns:
                composite += weight * snapshot[factor].fillna(0)
        
        # 取 top N
        return composite.nlargest(30).index.tolist()
```

### 8.2 因子 IC 分析（因子有效性检验）

```python
class FactorICAnalyzer:
    """因子 IC (Information Coefficient) 分析"""
    
    def compute_ic(
        self,
        factor_values: pd.Series,    # 某因子在 t 时刻的值
        future_returns: pd.Series,   # t+n 时刻的收益率
    ) -> float:
        """计算 Rank IC (Spearman 秩相关)"""
        # 只用有效数据对计算
        valid = factor_values.dropna().index.intersection(future_returns.dropna().index)
        if len(valid) < 30:
            return np.nan
        return factor_values.loc[valid].corr(future_returns.loc[valid], method="spearman")
    
    def ic_summary(self, factor_name: str, lookback_days: int = 250,
                   holding_period: int = 20):
        """
        因子 IC 汇总:
          - IC Mean (均值 > 0.03 有效)
          - IC Std
          - ICIR = IC_mean / IC_std (> 0.5 较好, > 1.0 很强)
          - IC > 0 比例 (> 50% 方向正确)
          - t-stat (是否统计显著)
        
        holding_period: 预测期（因子今日值 vs N 日后收益率）
          - 基本面因子通常用 20d (月频)
          - 估值因子可以用 60d (季频)
        """
        pass
    
    def ic_decay(self, factor_name: str, periods: List[int] = [5, 10, 20, 40, 60]):
        """
        IC 衰减分析:
          计算同一因子在不同 holding period 下的 IC
          判断因子是短期有效还是长期有效
          
        典型结果:
          momentum 因子: 5d IC 最高，20d 衰减
          质量因子: 20d IC 较低但 60d 依然稳定
        """
        pass

### 8.3 因子相关性与多重共线性

> **新增**：多因子组合时必须处理相关性问题。

```python
class FactorCorrelationAnalyzer:
    """
    因子相关性分析
    
    问题: 
      ROE 和 ROA 的相关系数可能 > 0.85
      如果组合评分同时给 ROE 权重 0.2 + ROA 权重 0.2
      实际上"盈利能力"维度被给了 0.4 的权重 → 过度暴露
    
    解决方案:
      1. 分析因子相关矩阵
      2. 同类高相关因子只保留 IC 最高的一个（特征选择）
      3. 或者用 PCA/正交化处理
    """
    
    def correlation_matrix(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算因子间相关系数矩阵
        
        输出:
                     roe    roa    gross_margin  pe_ttm
          roe       1.00   0.87   0.45          -0.12
          roa       0.87   1.00   0.52          -0.15
          gross_m   0.45   0.52   1.00          -0.08
          pe_ttm   -0.12  -0.15  -0.08          1.00
        
        判定:
          |corr| > 0.7 → 高度相关，不应同时使用
          |corr| > 0.5 → 中度相关，注意权重分配
        """
        return factor_df.corr(method="spearman")
    
    def select_representative_factors(
        self,
        factor_df: pd.DataFrame,
        ic_scores: Dict[str, float],
        max_corr: float = 0.7,
    ) -> List[str]:
        """
        在每组高相关因子中，选择 IC 最高的作为代表
        
        算法:
          1. 构建相关系数矩阵
          2. 聚类: 将 |corr| > max_corr 的因子归为一组
          3. 每组中选 IC 最高的因子
        """
        pass
    
    def orthogonalize(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """
        因子正交化 (Symmetric Orthogonalization)
        
        将高相关因子转化为不相关的"纯因子":
          1. 对因子矩阵做 SVD: F = UΣV^T
          2. 正交化: F_orth = U × V^T
          3. 结果: 因子间相关系数 ≈ 0，但保留原始含义的投影
        
        适用: 当需要所有因子都保留但消除共线性时
        不适用: 当因子个数 > 样本数时
        """
        from numpy.linalg import svd
        
        # 去均值
        centered = factor_df - factor_df.mean()
        
        # SVD
        U, S, Vt = svd(centered.values, full_matrices=False)
        
        # 对称正交化
        orth = pd.DataFrame(
            U @ Vt,
            index=factor_df.index,
            columns=factor_df.columns,
        )
        return orth
```

> **MVP 建议**：Phase 5 先做相关矩阵分析，识别高相关对（ROE↔ROA, Current↔Quick），
> 在综合评分时手动避免同类因子重复。正交化留到有实际 IC 数据后再做。

---

## 九、实施路线

| 阶段 | 时间 | 内容 | 依赖 |
|------|------|------|------|
| **Phase 1** | Week 1-2 | 基础框架搭建 | — |
| | | - `BaseFactor` 抽象类 + 注册表 | |
| | | - TTM 计算器 | |
| | | - PIT 时间对齐逻辑 | |
| | | - PhoenixA `factor_snapshot_wide` 建表 migration | |
| **Phase 2** | Week 3-4 | 核心因子实现 | Phase 1 |
| | | - 盈利能力因子组 (ROE/ROA/Margin...) | |
| | | - 成长性因子组 (Growth YoY/CAGR...) | |
| | | - 偿债能力因子组 (Debt/Current/Quick...) | |
| | | - 营运效率因子组 (Turnover/CashCycle...) | |
| **Phase 3** | Week 5 | 标准化 + 估值因子 | Phase 2 |
| | | - 去极值 (MAD) | |
| | | - 行业 Z-Score | |
| | | - 估值因子（需行情数据联动）| |
| **Phase 4** | Week 6 | 调度 + API + 集成 | Phase 3 |
| | | - 因子计算调度接入 cronjob | |
| | | - REST API 暴露 | |
| | | - 历史回填脚本 | |
| **Phase 5** | Week 7-8 | 验证 + 策略集成 | Phase 4 |
| | | - IC 分析工具 | |
| | | - 与回测引擎集成 | |
| | | - 多因子选股策略 demo | |
| | | - cthulhu 前端因子可视化（可选） | |

---

## 十、PhoenixA 侧变更

### 10.1 新增 Migration

```sql
-- migrations/postgresql/security/0003_factor_snapshot.sql

CREATE TABLE IF NOT EXISTS factor_snapshot_wide (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,
    market          VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    as_of_date      DATE NOT NULL,
    industry_code   VARCHAR(16),
    raw_factors     JSONB NOT NULL DEFAULT '{}',
    norm_factors    JSONB NOT NULL DEFAULT '{}',
    meta            JSONB NOT NULL DEFAULT '{}',
    -- meta 包含: version, freshness_score, staleness_days, latest_report,
    --           incremental(bool), computed_at, source_reports
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_factor_snapshot_wide UNIQUE (symbol, market, as_of_date)
);

-- 索引
CREATE INDEX idx_fsw_date ON factor_snapshot_wide (as_of_date DESC);
CREATE INDEX idx_fsw_symbol_date ON factor_snapshot_wide (symbol, as_of_date DESC);
CREATE INDEX idx_fsw_industry_date ON factor_snapshot_wide (industry_code, as_of_date DESC);
CREATE INDEX idx_fsw_norm_gin ON factor_snapshot_wide USING GIN (norm_factors jsonb_path_ops);

-- 常用估值因子：Generated Columns（加速排序查询）
ALTER TABLE factor_snapshot_wide
    ADD COLUMN roe_norm DOUBLE PRECISION 
        GENERATED ALWAYS AS ((norm_factors->>'roe')::double precision) STORED;
ALTER TABLE factor_snapshot_wide
    ADD COLUMN pe_ttm_raw DOUBLE PRECISION 
        GENERATED ALWAYS AS ((raw_factors->>'pe_ttm')::double precision) STORED;

CREATE INDEX idx_fsw_roe_norm ON factor_snapshot_wide (as_of_date, roe_norm DESC NULLS LAST);
CREATE INDEX idx_fsw_pe_ttm ON factor_snapshot_wide (as_of_date, pe_ttm_raw ASC NULLS LAST);

-- ─── 新增: 行业统计量表（增量标准化依据）──────────────────────────
-- 每次全量计算时存储行业均值/标准差，增量计算时复用
CREATE TABLE IF NOT EXISTS factor_industry_stats (
    id              BIGSERIAL PRIMARY KEY,
    as_of_date      DATE NOT NULL,
    market          VARCHAR(16) NOT NULL DEFAULT 'zh_a',
    industry_code   VARCHAR(16) NOT NULL,
    factor_name     VARCHAR(64) NOT NULL,
    mean_value      DOUBLE PRECISION,
    std_value       DOUBLE PRECISION,
    sample_count    INTEGER,
    version         VARCHAR(16) NOT NULL DEFAULT 'v1.0',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_fis UNIQUE (as_of_date, market, industry_code, factor_name)
);

CREATE INDEX idx_fis_date ON factor_industry_stats (as_of_date DESC, market);

COMMENT ON TABLE factor_snapshot_wide IS '因子化财务数据快照（宽表），每只股票每天一行';
COMMENT ON TABLE factor_industry_stats IS '因子行业统计量（增量标准化依据），每次全量计算时更新';
```

### 10.2 新增 API (PhoenixA)

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v2/factor/snapshot` | 批量写入因子快照 |
| GET | `/api/v2/factor/snapshot` | 查询因子快照 (by symbol/date/industry) |
| GET | `/api/v2/factor/rank` | 全市场因子排名 |
| DELETE | `/api/v2/factor/snapshot` | 删除指定日期快照（重算前清理） |

---

## 十一、边界情况处理

### 11.1 通用边界情况

| 场景 | 处理方式 |
|------|---------|
| 上市不满 1 年（无 YoY 数据） | 成长性因子 = NaN，不参与排序 |
| 上市不满 2 年（CAGR 需 3年） | CAGR 因子 = NaN |
| ST / *ST 股票 | 正常计算，但打标 `is_st=true`，策略层决定是否过滤 |
| 财务数据缺失（未按时披露） | 该因子 = NaN，不参与标准化。标记 staleness |
| 行业内样本太少 (< 10) | 不做 Z-Score，保留原始值 |
| 分母为零 | 返回 NaN |
| 分母为负（如负净利时算 PE） | 返回 NaN 或特殊标记 |
| 业绩快报 vs 正式报表 | 优先正式报表；未出正式报表时用快报补充，meta 标记 `source: "express"` |
| 报表重述/更正 | 同一 reporting_period 取 ann_date 最大（最新修订版本） |
| 回测中的已退市股票 | **必须包含**（见 11.3 存活偏差处理） |

### 11.2 金融行业特殊处理（关键）

> 银行/保险/证券的商业模式与普通工商企业完全不同，很多因子要么公式不同，要么完全不适用。

#### 11.2.1 分类标准

通过 `industry_code` 识别金融子行业：
- 申万一级 `490000`：银行
- 申万一级 `510000`：非银金融（含保险、证券、信托、多元金融）

或者通过 PhoenixA `security_registry` 中的 `comp_type_code` 字段：
- `1` = 一般工商业
- `2` = 银行
- `3` = 保险
- `4` = 证券
- `5` = 信托
- 只有 `comp_type_code = 1` 的公司使用标准因子公式

#### 11.2.2 银行业因子调整

| 标准因子 | 银行业处理 | 原因 |
|---------|-----------|------|
| **Gross Margin** | ❌ 不适用 | 银行无"营业成本"概念，用"净息差(NIM)"替代 |
| **ROIC** | ❌ 不适用 | 银行的"有息负债"（存款）是经营负债，不是投入资本 |
| **Inventory Turnover** | ❌ 不适用 | 银行无存货 |
| **Current/Quick Ratio** | ❌ 不适用 | 流动性监管用 LCR/NSFR (巴塞尔III)，非传统流动比 |
| **Debt Ratio** | ⚠️ 需重新定义 | 银行负债率 ~90% 是正常的（客户存款），不可跨行业比 |
| **ROE** | ✅ 可用但要注意 | 银行 ROE 普遍 10-15%，必须在银行业内部做 Z-Score |
| **PE/PB** | ✅ 可用 | 但 PB < 1 在银行是常态（不一定代表低估） |

**银行业替代因子（后续扩展）**：

| 替代因子 | 公式 | 说明 |
|---------|------|------|
| Net Interest Margin | 净利息收入 / avg(生息资产) | 银行核心盈利能力 |
| Cost-Income Ratio | 业务及管理费 / 营业收入 | 运营效率 |
| NPL Ratio | 不良贷款 / 贷款总额 | 资产质量 |
| Provision Coverage | 拨备 / 不良贷款 | 拨备充足度 |
| CAR | 资本充足率 | 安全边际 |

> **MVP 实施建议**：Phase 1-4 先对金融行业使用通用可计算的因子（ROE/ROA/PE/PB/NI Growth），
> 不适用的因子设为 NaN。银行/保险/证券的专属因子列入后续扩展。

#### 11.2.3 标准化时的处理

金融行业的 Z-Score **仅在金融行业内部做**。由于申万一级中银行(490000)和非银金融(510000)是独立行业，
自然符合"行业内 Z-Score"的逻辑——银行只和银行比，证券只和证券比。

**注意**：不可将银行的 Debt Ratio (90%) 和制造业的 Debt Ratio (50%) 做全市场排名，即使做了 Z-Score 也没有意义，
因为银行的"负债"含义完全不同。对于这类因子，需要在 `FactorMeta` 中标记 `exclude_financial=True`。

### 11.3 存活偏差（Survivorship Bias）处理

> **回测中最常见的偏差来源之一。**

```
问题:
  2020年 有 A 股 4000 只
  2025年 有 A 股 5200 只
  
  如果你只用"当前A股列表"回测 2020 年的因子策略:
    - 遗漏了 2020-2025 年间退市的 ~200 只股票
    - 这些退市股往往是亏损/ST/暴雷 → 你的回测回避了地雷
    - 回测收益虚高
    
修正:
  回测时的 "活跃股票列表" 必须用 as_of_date 当天的列表
  退市股票在退市前应该正常参与因子计算和选股
```

**实现**：

```python
async def get_active_symbols(self, market: str, as_of_date: str) -> List[str]:
    """
    获取指定日期的活跃股票列表（含后来退市的）
    
    逻辑:
      SELECT symbol FROM security_registry
      WHERE market = $1
        AND list_date <= $2            -- 已上市
        AND (delist_date IS NULL OR delist_date > $2)  -- 未退市
        AND NOT is_suspended(symbol, $2)  -- 未停牌（可选）
    """
```

### 11.4 因子版本控制

```python
# 因子公式可能随迭代更新，需要追踪版本

FACTOR_VERSION = "v1.0"  # 全局因子版本号

# 在 factor_snapshot_wide.meta 中存储:
# {"version": "v1.0", "computed_at": "2026-05-08T16:30:00", ...}

# 当公式重大变更时:
#   1. 升级 FACTOR_VERSION → "v1.1"
#   2. 全量重算历史数据
#   3. meta.version 标记新版本
#   4. 旧版本数据可选保留或清理
```

---

## 十二、性能估算

| 指标 | 预估 |
|------|------|
| 全市场全因子计算 (5000 股 × 40 因子) | ~2-5 分钟（含数据拉取） |
| 单股增量计算 | < 1 秒 |
| 因子快照存储 (1年) | ~125 万行 ≈ 0.5-1 GB（JSONB 压缩后） |
| 10 年历史因子 | ~5-10 GB |
| 全市场排序查询 (单因子) | < 100ms（Generated Column + B-tree） |
| 全市场多因子综合评分 | < 500ms（GIN 索引 + 应用层计算） |

---

## 附录 A：因子命名规范

```
{category}_{factor_name}

示例:
  profitability_roe
  profitability_gross_margin
  growth_revenue_yoy
  growth_ni_cagr_3y
  quality_accrual_ratio
  solvency_debt_ratio
  valuation_pe_ttm
  efficiency_asset_turnover
  per_share_eps_ttm
```

## 附录 B：依赖安装

```bash
# Artemis requirements.txt 新增
pandas>=2.0
numpy>=1.24
statsmodels>=0.14    # 市值中性化回归用
scipy>=1.10          # 统计函数 (winsorize 可选)
```

## 附录 C：与 Market Regime Engine 的关系

因子引擎产出的因子值是**静态横截面数据**（某一天全市场的快照）。

后续 **Market Regime Engine**（市场状态引擎）会决定：
- 当前市场环境下，哪些因子有效（如牛市偏成长、熊市偏质量/红利）
- 动态调整因子权重
- 结合技术面信号（momentum/volatility regime）做因子择时

因子引擎是 Regime Engine 的**输入层**，两者是上下游关系。

```
Factor Engine (本文档)
    │
    │ 输出: 标准化因子值
    ▼
Market Regime Engine (后续设计)
    │
    │ 输出: 当期最优因子权重
    ▼
Strategy Engine (已有)
    │
    │ 输出: 买卖信号
    ▼
Execution / Backtest
```

## 附录 D：rev.2 修订记录

| 修订点 | 原版问题 | 修正内容 |
|--------|---------|---------|
| **TTM/单季度** | 未说明中国报表累计值特性 | 新增 4.1 累计值说明 + 4.3 单季度推导 |
| **成长因子** | 公式用 `OPERA_REV(t)` 含义不清 | 明确用单季度同比 `REV_single_Q(t) / REV_single_Q(t-4Q)` |
| **ROIC** | 税率来源不明、有息负债定义模糊 | 明确 effective_tax_rate 和 Invested_Capital 定义 |
| **Earnings Stability** | `mean(NI)` 趋近 0 时 CV 发散 | 改用 `std/abs(mean)` + 退化处理 |
| **MAD 去极值** | 未处理 MAD=0 退化 | 加入 MAD=0 检测 + 1.4826 缩放因子 |
| **Z-Score** | std=0 时除零 | 加入 std<ε 检测，返回 0.0 |
| **增量计算** | 只有 `pass` | 完整实现：存储行业统计量 + 增量标准化逻辑 |
| **金融行业** | 一句话带过 | 新增 11.2 完整金融行业处理方案 |
| **存活偏差** | 未提及 | 新增 11.3 回测中必须包含退市股 |
| **估值因子市值** | 未说明用总股本还是流通股本 | 明确使用总股本 + PIT 对齐 + EV 详细定义 |
| **因子相关性** | 未考虑 | 新增 8.3 因子相关矩阵 + 正交化 + 特征选择 |
| **数据新鲜度** | 未考虑 | 新增 4.5 Freshness Score 机制 |
| **PIT 边缘情况** | 简单描述 | 扩展：报表修订、延迟披露、快报优先级 |
| **因子版本控制** | 未考虑 | 新增 11.4 版本号追踪 |
| **行业统计量存储** | 无 | 新增 `factor_industry_stats` 表 |
| **FactorMeta** | 字段不够 | 新增 `exclude_financial` + `min_history_quarters` |
| **IC 分析** | 过于简略 | 扩展：有效样本量检查 + IC 衰减 + holding_period |
| **负增长率处理** | "设为 NaN" | 细化：亏转盈/持续亏损的分别处理 |

