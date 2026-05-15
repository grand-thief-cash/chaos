学习计划：财务因子与因子工程入门（基于仓库中的 `fundamental_core.yaml` 与 `governance_seed.yaml`）

概述
- 目标：帮助没有财务背景的开发者/工程师系统、按步骤地掌握常见财务因子（盈利、现金流、偿债、效率、估值、每股类与治理相关因子），并能在项目中根据 `fundamental_core.yaml` 与 `governance_seed.yaml` 的 `source_fields` 实际计算与验证这些因子。
- 范围：从最基础的报表理解到进阶估值与治理规则，兼顾实操练习与工程实现要点。
- 参考文件（仓库）：
  - `app/projects/artemis/config/factor_catalog/factors/fundamental_core.yaml`
  - `app/projects/artemis/config/factor_catalog/factors/governance_seed.yaml`

学习清单（Checklist）
- [ ] 理解三张财务报表（损益表 / 资产负债表 / 现金流量表）与 PIT/TTM、单季度 vs 同期（YoY）概念
- [ ] 掌握基础盈利能力指标：margin、ROE、ROA、ROIC（非金融公司）
- [ ] 掌握现金流相关指标：OCF、FCF、cash conversion、fcf_quality
- [ ] 掌握偿债/流动性指标：debt ratio、interest coverage、net_debt_to_ebitda、current/quick ratio
- [ ] 掌握效率类指标：turnover、cash cycle（DSO/DIO/DPO）
- [ ] 掌握成长类指标：YoY、CAGR（3y）
- [ ] 掌握估值类指标：PE, PB, PS, EV/EBITDA, PEG, PCF, dividend_yield
- [ ] 掌握每股类指标与 market_adjust_policy 的含义：EPS, BPS, CFPS, FCF per share, DPS
- [ ] 实战：用一家公司跑一遍关键因子并对照 `source_fields` 与 `availability.requirements`
- [ ] 深化治理：理解 `governance_seed.yaml` 的特殊规则（例如 PEG 的 corner cases、金融行业的排除）

学习路线（按顺序）
1) 报表与基础概念（前置）
   - 目标：能区分三张报表的用途；理解 TTM（Trailing Twelve Months）、PIT（point-in-time）、单季度 vs TTM；理解复权口径对市值/每股因子的影响；能够把仓库中的 `source_fields` 映射到报表科目并实际取数。
   - 要点：
     - 在 `fundamental_core.yaml` 中查找并熟悉 `financial.income.data_json.*`、`financial.balance_sheet.data_json.*`、`financial.cashflow.data_json.*` 常用字段（如 OPERA_REV, NET_PRO_EXCL_MIN_INT_INC, TOTAL_ASSETS, NET_CASH_FLOW_OPERA_ACT, TOT_SHARE 等）。
     - 理解 TTM：用最近 4 个可用季度的数值求和（或在年报/季报混合时用差分法谨慎处理）。
     - 理解 PIT 对齐：价格使用 as_of_date 的 Close，股本/财务数据使用 as_of_date 之前最近可用的公告（见 `governance_seed.yaml` 的 pit_alignment 说明）。
     - 理解复权口径（前复权/后复权/不复权）对市值与每股指标的影响；注意仓库中若有 `market_adjust_policy.adjust: nf` 要采用不复权口径。

   - 推荐学习材料与工具（快速列表）：
     - 入门课程：Coursera 或 edX 上的 "Introduction to Financial Accounting" / "Financial Accounting Fundamentals"（系统理解三表）
     - 书籍：Kieso 等《会计原理/Intermediate Accounting》（了解科目定义）；Penman 的《Financial Statement Analysis》与 Damodaran 的《Investment Valuation》用于估值与比率分析进阶。
     - 在线参考：Investopedia（快速查公式与直觉）
     - 数据/工具：Python + pandas；数据源例如 TuShare（A 股）、yfinance（美股）或公司内部 PhoenixA API（参见 `phoenix_queries`）。

   - 分阶段学习与实践步骤（建议进度）
     - 阶段 A（理解与阅读，2–4 天）
       1. 学完入门课或读入门章节，掌握三张表分别回答的问题（盈利能力/财务结构/现金流）。
       2. 在 `fundamental_core.yaml` 中列出常见字段并在真实季报中定位对应项目。
     - 阶段 B（手工练习与 TTM，3–7 天）
       1. 选择一家公司，获取连续 4 个季度的 income/balance_sheet/cashflow（CSV 或 API）。
       2. 用 Excel 或 pandas 手工合并为 TTM：TTM = sum(last 4 quarters)。若使用年报+季报混合，按注释谨慎差分计算。
       3. 练习计算：OPERA_REV_TTM、NET_PRO_TTM、NET_CASH_FLOW_OPERA_ACT_TTM、EPS_TTM、PE_TTM、gross_margin。
     - 阶段 C（PIT 对齐、复权口径与工程实现，约 1 周）
       1. 明确两类时间点：price_as_of_date（收盘价）与 financial_ann_date_before（财报/股本公告日期）。
       2. 在实现中写工具函数：get_last_n_quarters(symbol, as_of_date, n)、sum_to_ttm(series)、get_pit_share_count(as_of_date)。

   - 常见陷阱与注意事项（实践中必须记录）
     - 季度口径可能有偏移（公司财年不同），使用 reporting_period 字段严格对齐。
     - 股本（TOT_SHARE）在增发/回购期间变化大，市值计算需取 as_of_date 前最近公告的股本。
     - 去年同期为 0 或负值时，YoY / PEG 计算需按照治理规则处理（例如设为 NaN 或用 abs(去年) 作为分母的特殊处理）。
     - 复权口径混用会导致历史序列不一致，务必在项目层面统一口径并记录。

   - 练习任务（由简到难）
     1. 最小可复现练习（1–2 小时）：用 pandas 从 CSV 读取 4 个季度的三表并计算 NET_PRO_TTM、OPERA_REV_TTM、NET_CASH_FLOW_OPERA_ACT_TTM，计算 EPS_TTM 和 PE_TTM（给定 Close 与 TOT_SHARE）。
     2. 进阶练习（半天）：实现 compute_ttm(symbol, as_of_date) 函数，返回常用基础因子并输出一份对照表（因子 → source_fields）。
     3. 验证练习（1–2 天）：选 3 家不同行业公司，对比单季度 vs TTM 的差异并写短结论，标注数据异常与处理方法。

   - 小示例（便于记忆的数字演示）
     - 单季度净利（M）：Q1=10, Q2=12, Q3=8, Q4=15 → NET_PRO_TTM = 10+12+8+15 = 45
     - 如果 as_of_date Close = 20 元，TOT_SHARE = 1000M → 市值 = 20 × 1000 = 20000 M；PE_TTM = 20000 / 45 ≈ 444.44；EPS_TTM = 45 / 1000 = 0.045 元。

   - 我可以帮你的后续工作（任选）
     - 生成一个 Jupyter notebook：从示例 CSV（或 TuShare/yfinance）读取 4 季度数据，演示合并为 TTM 并计算 EPS_TTM / PE_TTM / OCF_TTM / gross_margin，输出对照表。
     - 或者为 `app/projects/phoenixA` 写一个小工具模块（Python），包含 TTM 合并、YoY、PE/EV 的 compute 函数和 README 示例。


2) 营收与净利增长（基础）
   - 相关因子：`revenue_growth_yoy`, `ni_growth_yoy`（见 `fundamental_core.yaml`）
   - 要点：理解单季度同比（YoY）的计算与意义；如何从季度数据得到 YoY 与 TTM 值。
   - 练习：计算某公司最近 4 个季度的单季度 YoY 与 TTM 营收/净利。

3) 毛利/经营/净利率（率类入门）
   - 相关因子：`gross_margin`, `operating_margin`, `net_margin`
   - 要点：理解不同利润口径（营业收入 vs 营业成本 vs 营业利润 vs 归母净利）。
   - 练习：计算并与同行比较。

4) 每股指标与基础估值（先学 EPS / BPS / PE / PB）
   - 相关因子：`eps_ttm`, `bps`, `pe_ttm`, `pb`（查看 `governance_seed.yaml` 中关于 market_cap 的说明：市值=Close × TOT_SHARE）
   - 要点：理解 TOT_SHARE（总股本）作为市值基数、`market_adjust_policy.adjust: nf`（不复权）对计算口径的影响。
   - 练习：使用某日 Close 与最新公告 TOT_SHARE 计算 PE/PB。

5) 现金流与质量（中级）
   - 相关因子：`ocf_growth`, `cash_conversion`, `fcf_quality`, `fcf_per_share`, `cfps`
   - 要点：经营现金流 vs 净利润；自由现金流计算：通常为经营现金流 - 资本支出（注意 `CASH_PAID_PUR_CONST_FIOLTA` 字段的意义和数据口径）。
   - 练习：计算 TTM OCF、FCF、现金转换率（OCF_TTM / NetProfit_TTM）。

6) 应计与盈利稳定性（中级）
   - 相关因子：`accrual_ratio`, `earnings_stability`, `goodwill_ratio`
   - 要点：识别会影响盈利可持续性的会计项目（应计、一次性项目、商誉减值风险）。
   - 练习：计算过去 8 个季度净利的波动度（标准差或变异系数）；计算 accrual_ratio = (NetProfit_TTM - OCF_TTM) / AvgTotalAssets。

7) 偿债能力与流动性（重要）
   - 相关因子：`debt_ratio`, `interest_coverage`, `net_debt_to_ebitda`, `cash_to_st_debt`, `current_ratio`, `quick_ratio`
   - 要点：Interest coverage = EBIT_TTM / FinanceExpense_TTM；NetDebt = ST_BORROWING + LT_LOAN + BONDS_PAYABLE - CASH；注意金融行业（银行/保险/券商）通常要排除或另定义（见 `governance_seed.yaml` 的 financial_policy）。
   - 练习：计算净债、Interest coverage、NetDebt/EBITDA 并写出判定偿债压力的简单规则（如 Interest coverage < 2 为风险提示）。

8) 效率与营运周期（应用）
   - 相关因子：`asset_turnover`, `inventory_turnover`, `receivable_turnover`, `cash_cycle`
   - 要点：现金循环天数 = DSO + DIO - DPO；这些指标多适用于非金融公司（`financial_policy` 有注解）。
   - 练习：计算 DSO、DIO、DPO 的估算并给出行业对比。

9) 成长度量（略高阶）
   - 相关因子：`revenue_cagr_3y`, `ni_cagr_3y`, `ocf_growth`
   - 要点：CAGR 的计算（(Vt / V0)^(1/n) - 1），注意数据可用性（需要 >= 12 quarters）。
   - 练习：计算 3 年 CAGR 并对比最近单季 YoY，讨论差异和数据噪音。

10) 高级估值与治理（进阶）
    - 相关因子：`ev_to_ebitda`, `peg`, `ps_ttm`, `pcf`, `dividend_yield`
    - 要点：
      - EV = Close × TOT_SHARE + InterestBearingDebt - Cash；EBITDA 优先使用 `financial.income.data_json.EBITDA`，若缺失可用 OPERA_PROFIT + LESS_FIN_EXP 近似（`governance_seed.yaml` 提示）。
      - PEG：PE / NI_Growth_YoY，只在 PE > 0 且 Growth > 0 时有效；处理 corner cases（去年同期为 0 或为负）见 `governance_seed.yaml`。
      - Dividend yield：需要 corporate_action.dividend（优先 progress_code=3 已实施方案），并用 as_of_date 收盘价计算（见 `governance_seed.yaml`）。
    - 练习：实现 EV/EBITDA 与 PEG 的计算，并写出所有数据有效性判断逻辑（PE>0，Growth>0，去年同期 !=0 等）。

11) 每股类与 market snapshot / 调整口径（实务细节）
    - 相关因子：`eps_ttm`, `bps`, `cfps`, `fcf_per_share`, `dps`
    - 要点：确认 shares 的口径（TOT_SHARE）与 bars 的复权口径（`adjust: nf` 表示不复权）；这会影响历史回测与因子可比性。
    - 练习：比较用不复权与复权收盘价计算的 PE 在历史上的偏差（可选）。

12) 行业与治理例外（最终）
    - 要点：阅读 `governance_seed.yaml` 中对金融行业的排除项，理解哪些因子需要行业特化或直接不输出。
    - 练习：在你的 Universe 中筛选出金融类标的，列出哪些因子会被排除或需要特殊口径。

实战作业（逐步练习）
1) 选择标的：选一家公司（例如示例：600519.SH / 000001.SZ 或你熟悉的公司）。
2) 数据准备：从你的数据源（或公开数据）获取最近至少 4 个季度的 income、balance_sheet、cashflow，以及 as_of_date 的 daily close 与最新公告的 TOT_SHARE。
3) 计算清单（按优先级）
   - 基础：OPERA_REV_TTM、NET_PRO_TTM、TOT_SHARE（市值=Close × TOT_SHARE）
   - 率类：gross_margin, operating_margin, net_margin
   - 每股/估值：eps_ttm, pe_ttm, pb
   - 现金流相关：OCF_TTM、cash_conversion、fcf_per_share
   - 偿债：NetDebt、net_debt_to_ebitda、interest_coverage
   - 高级（可选）：ev_to_ebitda、peg（处理 corner cases）
4) 输出与比对：把计算结果和 `fundamental_core.yaml` / `governance_seed.yaml` 的 `source_fields` 做映射，确认字段名对应并记录任何缺失与处理策略（例如缺 EBITDA 回退至 OPERA_PROFIT+LESS_FIN_EXP）。

示例伪代码片段（Python-like，便于实现）

- 合并季度为 TTM（伪代码）：
  1. 读取最近 4 个可用季度的 income/cashflow
  2. TTM_value = sum(last_4_quarters.values)

- 单季度 YoY（伪代码）：
  ni_growth_yoy = (ni_this_quarter - ni_same_quarter_last_year) / abs(ni_same_quarter_last_year)
  - 若去年同期为 0：标记为 NaN
  - 若去年同期为 负且当前为正：按治理用 abs(去年) 做分母

- PEG 有效性判断（伪代码）：
  if pe_ttm > 0 and ni_growth_yoy > 0:
      peg = pe_ttm / ni_growth_yoy
  else:
      peg = NaN

工程与实现建议
- 每个因子用独立函数实现，函数签名包含：as_of_date、symbol、必要的历史窗口；函数内部负责 PIT 对齐与缺失值处理。
- 在函数 docstring 中注明对应 YAML 中的 `source_fields` 以便追溯数据来源。
- 对于重要的治理规则（如 PEG 的 corner cases、EV 的债务定义、dividend 的 progress_code 策略）在实现层写单元测试以保证行为可追溯与可审计。
- 将常用数据准备（合并 TTM、计算 rolling windows、PIT 对齐）写到公共模块中供所有因子复用。

时间计划（建议）
- 周 1：掌握三表、TTM、基础率类（margin、YoY）并完成第 1 次练习
- 周 2：每股与估值（PE/PB/EPS/BPS）与市值口径一致性确认
- 周 3：现金流、FCF、accrual 与稳定性分析
- 周 4：偿债/流动性与效率类（turnover、cash cycle）
- 周 5：进阶估值（EV/EBITDA、PEG）与治理细节实现
- 周 6：整合并完成一家公司从数据拉取到因子计算的端到端示例，写入 README 或 notebook

下一步（可选，由我来完成）
- 我可以为你生成：
  - A) 一份 Jupyter notebook（或 Python 脚本），演示完整的数据拉取（假设数据以 CSV/JSON 可拿到）到因子计算的流程，并输出对照表；或
  - B) 把常用计算函数（合并 TTM、YoY、PE、EV/EBITDA、PEG 的实现）写成一套小模块（带简单单元测试），放到 `app/projects/phoenixA` 下的某个 utils 包中；或
  - C) 按你的 Universe（你给一个 sample ticker 列表），为每只股票跑一轮因子并生成 CSV 报表。

请告诉我你希望我继续做哪一项（A/B/C），或是否直接把此文档保存到你指定位置（我已保存到：
`app/projects/phoenixA/docs/study/study_plan.md`）。

