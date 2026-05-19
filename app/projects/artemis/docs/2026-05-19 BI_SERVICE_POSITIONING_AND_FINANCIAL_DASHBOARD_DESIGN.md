# BI 服务落位建议与财务看板设计（Artemis Phase 1）
> 日期：2026-05-19  
> 状态：Proposal  
> 影响项目：Artemis、PhoenixA、Cthulhu、Atlas（可选集成）  
> 结论摘要：**当前阶段不建议新建独立 BI 后端服务；优先在 `Artemis` 内新增独立的 `BI` 能力层实现首期财务看板，并在 `Cthulhu` 中新增顶层 `BI` 模块。`PhoenixA` 保持数据中台职责，只补齐通用读接口与数据契约，不承载 BI 聚合/看板编排逻辑。**
---
## 0. 执行摘要
针对当前 Chaos 平台的架构边界、机器资源、服务职责和你的首期需求（杜邦分析、经营利润、现金流量、资产周转、资产负债、财报数智化分析），我的建议是：
### 0.1 结论
- **不放在 PhoenixA 里做 BI**：PhoenixA 的职责是统一数据中台、CRUD 网关、数据目录与供给契约，不应继续承接面向页面的分析聚合逻辑。
- **当前阶段优先放在 Artemis 内实现**：Artemis 已经具备 Python 分析能力、PhoenixA HTTP Client、factor/workbench 经验，最适合先做首期财务 BI。
- **但前端不要挂到 Workbench 心智里**：虽然后端落在 Artemis，但 `Cthulhu` 应新增顶层 `BI` 菜单组，而不是把财务看板塞进 `Workbench`。
- **为未来独立服务预留边界**：在 Artemis 中新增 `bi_engine` / `bi_routes` / `bi_service`，按“可拆分架构”设计；当 BI 能力跨出财务分析、出现独立扩容/权限/发布节奏时，再从 Artemis 中抽离成独立 BI 服务。
### 0.2 一句话判断
> **现在最优解是：`Artemis 内建 BI 子域`，而不是 `新建 BI 服务`；但接口、模块与前端入口按“未来可独立”的方式设计。**

### 0.3 当前文档范围说明
> **本次文档与实现只聚焦 `BI` 本身，不讨论 `Atlas` 集成。**
>
> - 首期只做 `PhoenixA -> Artemis BI -> Cthulhu BI` 这条主链路
> - 所有 `Atlas / LLM / 财报原文 / narrative` 内容统一视为后续扩展，不进入本次 MVP 设计与实现范围
---
## 1. 背景与问题定义
## 1.1 当前平台职责
根据平台总体设计：
- `PhoenixA`：数据中台，负责统一 DB CRUD 网关，向其他服务提供结构化数据访问。
- `Artemis`：行情拉取、回测、因子、研究工作台，本质上是**分析计算型服务**。
- `Atlas`：知识图谱、事件影响、LLM 驱动的投资洞察。
- `Cthulhu`：统一前端入口。
当前你的新需求并不是“单一财务 API”，而是一个**面向业务使用者的 BI 能力层**，首期从财务看板切入，但未来可能扩展到：
- 多维经营看板
- 行业对比/公司对比
- 因子与财务联动分析
- 财报数智化分析
- 事件/图谱/财务联动洞察
- 其他非财务类 BI 场景
这意味着我们做的不是一个简单 endpoint，而是一个新的**分析展示域（analysis-serving / read-model serving）**。
## 1.2 这类 BI 需求的本质
BI 看板与 PhoenixA 的原子数据接口有本质区别：
| 维度 | PhoenixA | BI 看板 |
|------|----------|---------|
| 目标 | 提供原子数据访问 | 提供可直接展示/解释的聚合结果 |
| 输出 | 行/表/API 记录 | 卡片、趋势、拆解、评分、洞察 |
| 粒度 | 通用数据域 | 页面/业务域导向 |
| 复用方式 | 被多个服务调用 | 直接服务前端页面 |
| 数据组织 | 按表/领域组织 | 按问题/看板组织 |
| 典型逻辑 | CRUD / filter / pagination | 指标计算 / 同比环比 / 归因拆解 / narrative |
所以这个能力不应继续放在 PhoenixA 内部演化成“面向页面的胖 API”。
---
## 2. 对现有服务的适配性评估
## 2.1 PhoenixA 适合做什么，不适合做什么
### 适合
- 财务报表、行情、分类、公司行为等原始数据查询
- Point-in-Time 查询（`ann_date_before`）
- 多期财报数据供给
- 数据目录、能力声明、数据血缘说明
- 统一字段命名与数据契约
### 不适合
- 杜邦分析、经营质量评分、现金流健康度等派生分析
- 面向看板的聚合 read model
- 财报 narrative、异常解释、同业对比摘要
- 直接跟前端页面结构强绑定的接口
### 原因
PhoenixA 的定位已经很明确：**数据中台而不是分析中台**。如果把 BI 放进去，会出现三个问题：
1. `PhoenixA` 由“数据网关”膨胀成“数据 + 业务分析 + 页面适配”混合服务。
2. 数据域接口与页面展示逻辑耦合，后续前端一变就会牵动中台。
3. 未来任何分析需求都会继续往 PhoenixA 堆，最终变成职责失控的超级服务。
**结论**：PhoenixA 只做 BI 的数据提供者，不做 BI 的承载者。
## 2.2 Artemis 为什么适合当前阶段承接 BI
从现状看，Artemis 已经具备以下基础：
- 已有 `PhoenixAClient`，可以直接消费 `financial / bars / taxonomy / securities / corporate-action` 等 API。
- 已有 `workbench`、`factor_service`、`regime` 这类“分析后返回前端读模型”的实现经验。
- 使用 Python，天然适合做：
  - pandas / 指标计算
  - 财务公式编排
  - 同比环比处理
  - TTM / PIT / 多期拼装
  - 后续接 LLM / 文本摘要 / anomaly detection
- 当前团队和资源下，复用 Artemis 的开发/部署链路，成本最低。
更关键的是：
> **财务 BI 首期并不是“报表仓库产品”，而是“金融分析能力产品”。这和 Artemis 当前的分析引擎定位是一致的。**
## 2.3 为什么现在不建议立即新建独立 BI 服务
新建服务的优点确实存在：职责纯粹、边界清晰、未来扩展更舒服。
但在当前阶段，这样做的代价偏大：
- 新服务需要新的项目骨架、部署、监控、配置、日志、文档、测试、前后端联调链路。
- 首期需求仍高度依赖 PhoenixA，数据编排来源并不复杂。
- 目前 BI 还处于“从财务看板起步”的探索阶段，指标体系、页面形式、缓存策略都还会快速迭代。
- 过早拆服务，会把本该用来验证业务价值的精力消耗在基础设施和服务治理上。
### 当前阶段的核心矛盾不是“服务不够多”，而是：
- 指标口径要先定义清楚
- 看板 read model 要先跑通
- Cthulhu 的页面体验要先成型
- PhoenixA 和 Artemis 的数据契约要先稳定
因此**先在 Artemis 内部落一个清晰子域**，是更符合当前资源条件的方案。
---
## 3. 候选方案比较
## 3.1 方案 A：继续在 Artemis 中扩展 BI 能力（推荐）
### 方案描述
在 `Artemis` 内新增独立的 `BI` 子域，不与现有 workbench/factor/regime 混写：
- `artemis/api/http_gateway/bi_routes.py`
- `artemis/services/bi_service.py`
- `artemis/engines/bi_engine/...`
- `artemis/models/bi.py`
### 优势
- 最大化复用现有 Python 分析栈
- 直接复用 PhoenixAClient
- 交付速度快，适合首期验证
- 与“因子、研究、分析”定位一致
- 后续可以自然衔接财务因子、估值、行业比较
### 风险
- 如果不做边界治理，Artemis 容易逐步变成“什么分析都往里加”的综合服务
- 若未来 BI 需求大幅跨域，可能需要拆分
### 控制手段
- 明确只新增 `BI 子域`，不把接口继续堆到 `workbench`
- 约束 PhoenixA 为数据源，不做页面聚合 API
- 文档中预设拆分阈值和演进路线
## 3.2 方案 B：新建独立 BI 服务
### 方案描述
新建一个独立后端项目，例如未来可以命名为 `insight` / `bi-hub` / `apollo-bi` 一类的服务，专门负责：
- Dashboard read model
- 多源数据编排
- narrative/LLM orchestration
- dashboard cache / snapshot
- 通用 BI API
### 优势
- 职责最清晰
- 与 Artemis 的回测/任务/因子完全解耦
- 更利于未来非财务 BI、组织级 dashboard、权限治理
### 劣势
- 当前阶段工程成本偏高
- 首期财务 BI 仍然大量依赖 PhoenixA 原始接口
- 会增加部署、配置、联调、监控、文档成本
- 指标体系尚未稳定前，过早拆服务收益不高
## 3.3 方案 C：直接放到 PhoenixA（不推荐）
### 不推荐原因
- 违背 PhoenixA 数据中台定位
- 数据域 API 与页面展示逻辑耦合
- 后续所有 dashboard 都会堆入中台
- PhoenixA 会变成难维护的“大杂烩”
---
## 4. 决策矩阵
| 维度 | Artemis 扩展 BI | 新建 BI 服务 | PhoenixA 内实现 |
|------|-----------------|--------------|-----------------|
| 与现有职责一致性 | 高 | 中 | 低 |
| 首期交付速度 | **最高** | 低 | 中 |
| 复用现有代码 | **最高** | 低 | 中 |
| 对数据契约复用 | 高 | 高 | 高 |
| 对未来 BI 扩展性 | 中高 | **最高** | 低 |
| 部署/运维成本 | **最低** | 高 | 中 |
| 前端接入清晰度 | 高 | 高 | 中 |
| 风险可控性 | 高（前提是做子域隔离） | 中 | 低 |
| 当前阶段综合性价比 | **最高** | 中 | 低 |
**最终选择：方案 A。**
---
## 5. 推荐落位方案
## 5.1 总体建议
### 后端
- **落位在 Artemis**，但不是继续扩写 `workbench`，而是新增 `BI 子域`。
- 新能力以 `bi_engine` 为核心组织，而不是散落在 `factor_service` 或 `workbench_routes` 中。
### 前端
- **落位在 Cthulhu 新增顶层 `BI` 菜单组**。
- 不建议放在 `Workbench` 下，因为：
  - Workbench 是研究/试验/交互式分析心智
  - BI 是面向消费/阅读/看板/洞察心智
  - 两者用户路径不同
### 数据源
- `PhoenixA` 继续作为首期唯一主数据源，BI 首期范围严格收敛到 **PhoenixA 已有且文档已确认的数据能力**。
- `Atlas` 不进入首期 MVP 关键路径；**当前文档实现范围内一律不考虑 Atlas 集成**。
## 5.2 推荐架构图
```text
┌───────────────────────────────────────────────────────────────┐
│ Cthulhu                                                      │
│ ├─ Workbench（研究）                                         │
│ ├─ Atlas（图谱/事件）                                        │
│ └─ BI（新模块）                                              │
│    ├─ BI Landing / 财务入口                                   │
│    ├─ 公司财务总览                                            │
│    ├─ 杜邦分析                                                │
│    ├─ 经营质量 / 现金流 / 周转 / 偿债                          │
│    ├─ 同业对比（Phase 1.5）                                   │
│    └─ 财报数智化分析（Phase 2+）                              │
└───────────────────────┬───────────────────────────────────────┘
                        │ HTTP
                        ▼
┌───────────────────────────────────────────────────────────────┐
│ Artemis                                                       │
│ └─ BI Engine                                                  │
│    ├─ PhoenixAProvider                                        │
│    ├─ FinancialMetricEngine                                   │
│    ├─ DashboardAssembler                                      │
│    ├─ NarrativeAdapter（Phase 2+，可选接 Atlas）              │
│    └─ Snapshot/Cache                                          │
└───────────────┬───────────────────────┬───────────────────────┘
                │                       │
                │ HTTP                  │ HTTP / Optional
                ▼                       ▼
        ┌───────────────┐       ┌────────────────┐
        │ PhoenixA      │       │ Atlas          │
        │ 财务/行情/分类 │       │ 文档/图谱/LLM   │
        └───────────────┘       └────────────────┘
```
---
## 6. Artemis 内部目标设计
## 6.1 设计原则
1. **BI 是独立子域，不挂靠 Workbench 内部实现。**
2. **PhoenixA 提供原始/标准化数据，Artemis 负责派生分析。**
3. **返回结果按页面 read model 组织，而不是直接透传 PhoenixA 响应。**
4. **公式与口径版本化。**
5. **支持 Point-in-Time 分析。**
6. **结构化分析与 narrative 分层。**
7. **未来可拆服务。**
## 6.2 建议模块结构
```text
artemis/
├─ api/http_gateway/
│  └─ bi_routes.py
├─ models/
│  └─ bi.py
├─ services/
│  └─ bi_service.py
└─ engines/
   └─ bi_engine/
      ├─ providers/
      │  ├─ phoenixA_provider.py
      │  └─ atlas_provider.py              # optional
      ├─ financial/
      │  ├─ formulas.py                    # 杜邦/现金流/偿债/周转公式注册
      │  ├─ normalizer.py                  # 原始字段 → 统一业务字段
      │  ├─ calculator.py                  # 指标计算器
      │  ├─ comparator.py                  # 同比/环比/行业对比
      │  └─ dashboard_builder.py           # 页面读模型装配
      ├─ narrative/
      │  ├─ rule_based.py                  # Phase 2：结构化摘要
      │  └─ atlas_adapter.py               # Phase 3：optional
      ├─ cache/
      │  └─ snapshot_cache.py
      └─ contracts/
         └─ metric_definitions.py          # 指标定义、口径、版本
```
## 6.3 分层职责
### Provider 层
负责跟外部服务交互：
- 从 PhoenixA 拉：
  - `securities`
  - `financial statements`
  - `bars`
  - `taxonomy`
  - `corporate action`
- 从 Atlas 拉（可选）：
  - 财报摘要
  - 文档标签
  - 风险事件补充
  - 产业链背景
### Normalizer 层
负责把 PhoenixA 的原始字段映射成 BI 统一语义字段，例如：
- `TOT_OPERA_REV` → `revenue_total`
- `OPERA_PROFIT` → `operating_profit`
- `NET_PRO_EXCL_MIN_INT_INC` → `net_profit_parent`
- `TOTAL_ASSETS` → `total_assets`
- `TOT_SHARE_EQUITY_EXCL_MIN_INT` → `equity_parent`
- `NET_CASH_FLOW_OPERA_ACT` → `operating_cashflow`
> 这层非常关键。不要让前端或页面逻辑直接依赖 `data_json` 原始字段名。
### Calculator 层
负责所有派生指标计算：
- 杜邦分析
- 偿债能力
- 现金流质量
- 营运能力
- 成长性
- 简单评分/预警
### Dashboard Builder 层
负责把多个指标组装成页面需要的 read model，例如：
- `CompanyFinancialDashboard`
- `DupontBreakdown`
- `CashflowQualityPanel`
- `BalanceHealthPanel`
- `PeerComparisonTable`（Phase 1.5）
### Narrative 层
负责“财报数智化分析”的文字化解释：
- Phase 2：先做结构化规则摘要
- Phase 3：再接入 Atlas/LLM 做文本摘要与风险解释
---
## 7. 首期财务 BI 范围设计（按 PhoenixA 已确认数据收敛）
## 7.1 首期范围重排
结合 PhoenixA 当前已文档化的数据能力，首期不建议再把范围定义成“4 个页面 + 财报数智化分析一起上”。更稳妥的做法是：

| 页面/能力 | 阶段 | 目标 | 是否首期必做 |
|-----------|------|------|--------------|
| `BI Landing / 财务入口` | Phase 1 | 提供公司检索、最近访问、使用说明、入口导航 | 是 |
| `公司财务总览 Dashboard` | Phase 1 | 用结构化财务指标快速看公司当前财务状态 | 是 |
| `杜邦分析` | Phase 1 | 对 ROE 做三层拆解并展示同比变化 | 是 |
| `经营质量 / 现金流 / 周转 / 偿债` | Phase 1 | 用 4 个 panel 看质量、现金、效率、杠杆 | 是 |
| `同业对比` | Phase 1.5 | 基于行业映射和给定指标做 peer comparison | 否 |
| `财报数智化分析` | Phase 2+ | 先结构化摘要，再考虑 Atlas/LLM 文本洞察 | 否 |

> **首期 MVP 聚焦 3 个结构化财务看板 + 1 个入口页，不把财报数智化分析放进 Phase 1 必选范围。**

> **实现状态更新（2026-05-19）**：当前代码已在 MVP 基础上前推：
> - 已补 `同行对比` 初版（Phase 1.5 starter）
> - 已补 `结构化摘要` 初版（Phase 2 starter）
> - 已把趋势区从表格升级为图表展示
> - 已补远程证券搜索体验
> - 仍然 **不包含 Atlas / LLM / 财报原文**

## 7.2 页面 0：BI Landing / 财务入口
目标：给用户一个进入 BI 的稳定入口，而不是让用户直接记住某个深层公司页面。

### 页面内容分层
1. **顶部说明区**
   - BI 模块定位：财务看板 / 财务比较 / 后续财报洞察
   - 数据说明：当前数据来自 `PhoenixA`
   - 覆盖范围提示：首期优先覆盖 `comp_type_code = 1` 的非金融公司
2. **公司检索区**
   - 股票代码搜索
   - 证券名称搜索（基于 PhoenixA `securities` 数据过滤）
   - 最近访问公司快捷入口
3. **功能入口卡片**
   - 公司财务总览
   - 杜邦分析
   - 经营质量
   - 同业对比（当前已实现初版）
4. **数据口径提示区**
   - `as_of_date` 的含义
   - PIT 查询基于 `ann_date_before`
   - 指标支持“当前值 / 去年同期值 / 同比变动额 / 同比增长”展示规则
5. **适用范围提示区**
   - 非金融公司：完整展示
   - 银行/保险/券商：首期仅展示有限指标或提示“暂未完整适配”

## 7.3 页面 1：公司财务总览 Dashboard
目标：在一个页面里快速回答“这家公司当前财务体质如何、同比变化如何、有哪些异常信号”。

### 页面结构
#### A. 顶部上下文条（Context Bar）
- 证券名称 + 代码
- 市场 / 交易所
- 行业（来自 `taxonomy/by_security` 的 `canonical_category_name`）
- 公司类型（`comp_type_code`）
- `as_of_date`
- 最新可用报告期 `latest_period`
- 数据来源标记：`PhoenixA / amazing_data`

#### B. 核心 KPI 卡片区（首屏）
建议首期固定 8 张卡，每张卡统一展示：
- 当前值
- 去年同期值
- 同比变动额（YoY Delta）
- 同比增长率（YoY Growth，若适用）
- 单位
- 报告期

| 卡片 | 主要字段/公式 | 展示说明 |
|------|---------------|----------|
| 营业总收入 | `TOT_OPERA_REV` | 展示当前值、去年同期值、同比增幅 |
| 营业利润 | `OPERA_PROFIT` | 展示当前值、同比变动额、同比增幅 |
| 归母净利润 | `NET_PRO_EXCL_MIN_INT_INC` | 展示当前值、同比变动额、同比增幅 |
| 经营现金流净额 | `NET_CASH_FLOW_OPERA_ACT` | 展示当前值、同比变动额、同比增幅 |
| 总资产 | `TOTAL_ASSETS` | 展示当前值、去年同期值、同比变动额 |
| 资产负债率 | `TOTAL_LIAB / TOTAL_ASSETS` | 展示当前值、去年同期值、同比变动（百分点） |
| ROE | `NET_PRO_EXCL_MIN_INT_INC / AVG(EQUITY)` | 展示当前值、去年同期值、同比变动（百分点） |
| ROA | `NET_PRO_EXCL_MIN_INT_INC / AVG(TOTAL_ASSETS)` | 展示当前值、去年同期值、同比变动（百分点） |

#### C. 趋势图区
首期建议 3 张图，按 4~8 个报告期展示：
1. **收入 / 营业利润 / 归母净利润多期趋势**
   - 用多折线或柱线组合
   - 默认按报告期排序
2. **经营现金流 vs 归母净利润对比图**
   - 用双柱对比现金与利润
   - 强化“利润现金含量”观察
3. **总资产 / 总负债 / 归母权益结构趋势**
   - 用堆叠柱或面积图
   - 帮助看资产扩张与杠杆变化

#### D. 财务结构摘要区
建议做 3 个摘要卡：
1. **盈利摘要**
   - 营业总收入同比
   - 营业利润同比
   - 归母净利润同比
2. **现金摘要**
   - 经营现金流同比
   - `OCF / 净利润`
3. **资产负债摘要**
   - 资产负债率
   - 流动比率
   - 总资产同比变动

#### E. 预警区（Warning List）
首期预警全部基于结构化规则，不做文本生成。建议规则：
- `经营现金流 < 归母净利润` → 现金转化偏弱
- `经营现金流同比下降且净利润同比上升` → 利润与现金背离
- `资产负债率同比上升` → 杠杆抬升
- `流动比率低于阈值` → 短期偿债压力
- `总资产周转率同比下降` → 经营效率走弱

#### F. 页面底部数据来源说明
- 指出各卡片对应字段来源：`income / balance_sheet / cashflow`
- 提醒“同比值来自去年同期报告期比较，不是环比”
- 对不适用公司类型给出降级提示

## 7.4 页面 2：杜邦分析
目标：把 `ROE` 拆开，让用户知道它到底是“利润率驱动”“周转驱动”还是“杠杆驱动”。

### 首期仅做三层杜邦
```text
ROE = 净利率 × 总资产周转率 × 权益乘数
```

### 页面结构
#### A. 顶部说明区
- 当前公司 / 行业 / 报告期
- 三层杜邦说明
- 数据口径说明：平均总资产、平均归母权益

#### B. 杜邦拆解主图
建议使用树图或横向拆解卡：
- `ROE`
  - `净利率`
  - `总资产周转率`
  - `权益乘数`

每个节点展示：
- 当前值
- 去年同期值
- 同比变动值
- 变化方向（↑ / ↓）

#### C. 驱动解释区
按结构化模板输出，而不是自由文本：
- 若 `净利率` 上升最大，则标记“利润率贡献为主要正向驱动”
- 若 `总资产周转率` 下降最大，则标记“资产使用效率拖累 ROE”
- 若 `权益乘数` 上升，则标记“杠杆因素对 ROE 有放大作用”

#### D. 多期趋势区
建议拆成 4 张小图：
1. `ROE` 多期趋势
2. `净利率` 多期趋势
3. `总资产周转率` 多期趋势
4. `权益乘数` 多期趋势

#### E. 对比表区
表格字段建议：
- 报告期
- ROE
- 净利率
- 总资产周转率
- 权益乘数
- 各指标同比变动

#### F. 首期范围约束
- 五层杜邦后置
- 税负率 / 利息负担 / EBIT Margin 虽然部分字段已有，但首期不建议先做，以免口径解释过重
- 同行业百分位建议放到 Phase 1.5，避免首期引入大规模横向预计算

## 7.5 页面 3：经营质量 / 现金流 / 周转 / 偿债
目标：把“财务总览里的一屏摘要”展开成更可读、更可比的四个专题 panel。

### Panel A：经营利润质量
#### 指标
- 营业利润率 = `OPERA_PROFIT / TOT_OPERA_REV`
- 净利率 = `NET_PRO_EXCL_MIN_INT_INC / TOT_OPERA_REV`
- 期间费用率 = `(LESS_SELLING_EXP + LESS_ADMIN_EXP + LESS_FIN_EXP) / TOT_OPERA_REV`（仅在字段完整时显示）
- 研发费用率 = `RD_EXP / TOT_OPERA_REV`（若字段存在则显示）
- 利润现金含量 = `NET_CASH_FLOW_OPERA_ACT / NET_PRO_EXCL_MIN_INT_INC`

#### 展示模块
- 质量指标卡片：当前值 + 去年同期值 + 同比变动
- 利润率趋势图：营业利润率 / 净利率
- 费用率拆解条形图：销售 / 管理 / 财务 / 研发
- 规则提醒：费用率上升、利润率下降、利润现金含量偏弱

### Panel B：现金流质量
#### 指标
- 经营现金流净额 = `NET_CASH_FLOW_OPERA_ACT`
- 投资现金流净额 = `NET_CASH_FLOW_INV_ACT`
- 筹资现金流净额 = `NET_CASH_FLOW_FIN_ACT`
- `OCF / 净利润`
- `OCF / 营业收入`
- FCF（简版）优先使用 `FREE_CASH_FLOW`；若口径不可稳定，再回退为不展示
- 资本开支近似值 = `CASH_PAID_PUR_CONST_FIOLTA`（如字段可取）

#### 展示模块
- 现金流三分区卡片：经营 / 投资 / 筹资
- 现金利润对比图：OCF vs 净利润
- 现金流结构图：三类现金流净额
- 风险提示：OCF 连续弱于净利润、投资现金流大幅流出、筹资依赖提升

### Panel C：资产周转
#### 指标
- 总资产周转率 = `TOT_OPERA_REV / AVG(TOTAL_ASSETS)`
- 应收账款周转率 = `TOT_OPERA_REV / AVG(ACCT_RECEIVABLE)`
- 存货周转率 = `LESS_OPERA_COST / AVG(INV)`

#### 展示模块
- 3 张效率指标卡
- 多期趋势图
- 当前期 vs 去年同期对比表

#### 范围说明
- 若 `ACCT_RECEIVABLE` 或 `INV` 缺失，则相应卡片降级为“不展示”而不是补空值硬算

### Panel D：资产负债 / 偿债
#### 指标
- 资产负债率 = `TOTAL_LIAB / TOTAL_ASSETS`
- 流动比率 = `TOTAL_CUR_ASSETS / TOTAL_CUR_LIAB`
- 速动比率 = `(TOTAL_CUR_ASSETS - INV) / TOTAL_CUR_LIAB`
- 货币资金 = `CURRENCY_CAP`
- 短期借款 = `ST_BORROWING`
- 长期借款 = `LT_LOAN`
- 应付债券 = `BONDS_PAYABLE`

#### 展示模块
- 杠杆与流动性卡片区
- 资产负债结构对比图
- 短债 / 长债 / 货币资金观察区
- 预警区：资产负债率走高、流动性指标走弱、短债压力抬升

### 页面公共设计要求
- 每个 panel 的卡片统一支持同比值和同比增长/同比变动展示
- 每个 panel 底部都附“数据字段来源说明”
- 首期不做 narrative 段落，只做结构化卡片、图表、表格、规则预警

## 7.6 首期不纳入范围的内容
以下能力明确后置，避免首期范围膨胀：
- 财报数智化分析单独页面
- Atlas / LLM 文本摘要
- 财报原文引用与证据链
- 跨全市场大规模 percentile 排名
- 金融行业（银行/保险/券商）完整专属口径适配

## 7.7 MVP 指标矩阵表（页面 -> 模块 -> 指标 -> PhoenixA 字段 -> 是否首期）

> 说明：
> - `是否首期` 只表示是否进入当前 MVP 开发范围
> - `字段` 列只写 PhoenixA 已确认字段，不写 Atlas / 文本 / 外部数据
> - `派生公式` 为 Artemis BI 层计算逻辑，不要求 PhoenixA 直接返回

| 页面 | 模块 | 指标 | PhoenixA 字段 | 派生公式/说明 | 是否首期 |
|------|------|------|---------------|---------------|----------|
| BI Landing | 公司检索区 | 证券代码 | `securities.symbol` | 搜索输入主键 | 是 |
| BI Landing | 公司检索区 | 公司名称 | `securities.name` | 名称模糊搜索 | 是 |
| BI Landing | 公司检索区 | 市场/交易所 | `securities.market` / `securities.exchange` | 展示上下文 | 是 |
| BI Landing | 适用范围提示 | 行业标签 | `taxonomy.canonical_category_name` | 仅作入口信息 | 是 |
| 公司财务总览 | Context Bar | 公司类型 | `financial.comp_type_code` / `taxonomy.derived_flags.financial_sector` | 用于金融/非金融分流 | 是 |
| 公司财务总览 | KPI 卡 | 营业总收入 | `income.TOT_OPERA_REV` | 金额类，同比展示 | 是 |
| 公司财务总览 | KPI 卡 | 营业利润 | `income.OPERA_PROFIT` | 金额类，同比展示 | 是 |
| 公司财务总览 | KPI 卡 | 归母净利润 | `income.NET_PRO_EXCL_MIN_INT_INC` | 金额类，同比展示 | 是 |
| 公司财务总览 | KPI 卡 | 经营现金流净额 | `cashflow.NET_CASH_FLOW_OPERA_ACT` | 金额类，同比展示 | 是 |
| 公司财务总览 | KPI 卡 | 总资产 | `balance_sheet.TOTAL_ASSETS` | 金额类，同比展示 | 是 |
| 公司财务总览 | KPI 卡 | 资产负债率 | `balance_sheet.TOTAL_LIAB` + `balance_sheet.TOTAL_ASSETS` | `TOTAL_LIAB / TOTAL_ASSETS` | 是 |
| 公司财务总览 | KPI 卡 | ROE | `income.NET_PRO_EXCL_MIN_INT_INC` + `balance_sheet.TOT_SHARE_EQUITY_EXCL_MIN_INT` | `NP / AVG(EQUITY)` | 是 |
| 公司财务总览 | KPI 卡 | ROA | `income.NET_PRO_EXCL_MIN_INT_INC` + `balance_sheet.TOTAL_ASSETS` | `NP / AVG(ASSETS)` | 是 |
| 公司财务总览 | 趋势图 | 收入趋势 | `income.TOT_OPERA_REV` | 多报告期趋势 | 是 |
| 公司财务总览 | 趋势图 | 利润趋势 | `income.OPERA_PROFIT` / `income.NET_PRO_EXCL_MIN_INT_INC` | 多报告期趋势 | 是 |
| 公司财务总览 | 趋势图 | 现金流趋势 | `cashflow.NET_CASH_FLOW_OPERA_ACT` | 多报告期趋势 | 是 |
| 公司财务总览 | 趋势图 | 资产/负债/权益结构 | `balance_sheet.TOTAL_ASSETS` / `TOTAL_LIAB` / `TOT_SHARE_EQUITY_EXCL_MIN_INT` | 结构趋势 | 是 |
| 公司财务总览 | 预警 | 现金弱于利润 | `cashflow.NET_CASH_FLOW_OPERA_ACT` + `income.NET_PRO_EXCL_MIN_INT_INC` | 规则判断 | 是 |
| 公司财务总览 | 预警 | 杠杆抬升 | `balance_sheet.TOTAL_LIAB` + `TOTAL_ASSETS` | 资产负债率同比 | 是 |
| 杜邦分析 | 主指标 | ROE | `income.NET_PRO_EXCL_MIN_INT_INC` + `balance_sheet.TOT_SHARE_EQUITY_EXCL_MIN_INT` | 三层杜邦总指标 | 是 |
| 杜邦分析 | 子指标 | 净利率 | `income.NET_PRO_EXCL_MIN_INT_INC` + `income.TOT_OPERA_REV` | `NP / Revenue` | 是 |
| 杜邦分析 | 子指标 | 总资产周转率 | `income.TOT_OPERA_REV` + `balance_sheet.TOTAL_ASSETS` | `Revenue / AVG(Assets)` | 是 |
| 杜邦分析 | 子指标 | 权益乘数 | `balance_sheet.TOTAL_ASSETS` + `TOT_SHARE_EQUITY_EXCL_MIN_INT` | `AVG(Assets) / AVG(Equity)` | 是 |
| 杜邦分析 | 驱动解释 | 主要驱动方向 | 同上三项 | 规则模板输出 | 是 |
| 经营质量 | 质量卡片 | 营业利润率 | `income.OPERA_PROFIT` + `income.TOT_OPERA_REV` | `OP / Revenue` | 是 |
| 经营质量 | 质量卡片 | 净利率 | `income.NET_PRO_EXCL_MIN_INT_INC` + `income.TOT_OPERA_REV` | `NP / Revenue` | 是 |
| 经营质量 | 质量卡片 | 期间费用率 | `income.LESS_SELLING_EXP` + `LESS_ADMIN_EXP` + `LESS_FIN_EXP` + `TOT_OPERA_REV` | 条件展示 | 是 |
| 经营质量 | 质量卡片 | 研发费用率 | `income.RD_EXP` + `income.TOT_OPERA_REV` | 条件展示 | 是 |
| 经营质量 | 质量卡片 | 利润现金含量 | `cashflow.NET_CASH_FLOW_OPERA_ACT` + `income.NET_PRO_EXCL_MIN_INT_INC` | `OCF / NP` | 是 |
| 现金流质量 | 现金卡片 | 投资现金流净额 | `cashflow.NET_CASH_FLOW_INV_ACT` | 现金流结构 | 是 |
| 现金流质量 | 现金卡片 | 筹资现金流净额 | `cashflow.NET_CASH_FLOW_FIN_ACT` | 现金流结构 | 是 |
| 现金流质量 | 现金卡片 | OCF/营业收入 | `cashflow.NET_CASH_FLOW_OPERA_ACT` + `income.TOT_OPERA_REV` | `OCF / Revenue` | 是 |
| 现金流质量 | 现金卡片 | FCF（简版） | `cashflow.FREE_CASH_FLOW` | 字段有则展示 | 是 |
| 现金流质量 | 资本开支观察 | 资本开支近似值 | `cashflow.CASH_PAID_PUR_CONST_FIOLTA` | 条件展示 | 是 |
| 资产周转 | 效率卡片 | 应收账款周转率 | `income.TOT_OPERA_REV` + `balance_sheet.ACCT_RECEIVABLE` | 字段齐备时展示 | 是 |
| 资产周转 | 效率卡片 | 存货周转率 | `income.LESS_OPERA_COST` + `balance_sheet.INV` | 字段齐备时展示 | 是 |
| 偿债与杠杆 | 杠杆卡片 | 流动比率 | `balance_sheet.TOTAL_CUR_ASSETS` + `TOTAL_CUR_LIAB` | `CA / CL` | 是 |
| 偿债与杠杆 | 杠杆卡片 | 速动比率 | `balance_sheet.TOTAL_CUR_ASSETS` + `TOTAL_CUR_LIAB` + `INV` | `(CA - INV) / CL` | 是 |
| 偿债与杠杆 | 观察项 | 货币资金 | `balance_sheet.CURRENCY_CAP` | 流动性观察 | 是 |
| 偿债与杠杆 | 观察项 | 短期借款 | `balance_sheet.ST_BORROWING` | 债务结构观察 | 是 |
| 偿债与杠杆 | 观察项 | 长期借款 | `balance_sheet.LT_LOAN` | 债务结构观察 | 是 |
| 偿债与杠杆 | 观察项 | 应付债券 | `balance_sheet.BONDS_PAYABLE` | 债务结构观察 | 是 |
| 同业对比 | 比较表 | 行业成分股列表 | `taxonomy industry constituents` | 构造 peer set | 否（Phase 1.5） |
| 同业对比 | 比较表 | 指标排序/百分位 | 同上 + 财务指标字段 | 横截面对比 | 否（Phase 1.5） |
| 数智分析 | 摘要 | 结构化 highlights | 财务指标组合 | 规则摘要 | 否（Phase 2） |
| 数智分析 | 文本洞察 | narrative / LLM | 不在当前 BI 范围 | 本次不做 | 否 |

---
## 8. 财务指标口径与同比展示设计
## 8.1 基础原则
1. 所有看板必须支持 `as_of_date`
2. 所有财务数据默认基于 `ann_date_before` 做 PIT 过滤
3. 涉及资产/权益/库存/应收等存量指标，优先使用平均值口径
4. 口径定义要版本化，不允许散落在多个页面组件里
5. 页面指标默认优先展示 **当前值 + 去年同期值 + 同比变动额 + 同比增长/同比变动**
6. 首期优先覆盖 `comp_type_code = 1` 非金融公司

## 8.2 同比展示统一规则
### A. 绝对值指标（金额类）
适用于：收入、利润、现金流、总资产、总负债等。

统一返回：
- `value`：当前值
- `same_period_last_year`：去年同期值
- `yoy_delta`：`value - same_period_last_year`
- `yoy_growth`：`(value - same_period_last_year) / abs(same_period_last_year)`

### B. 比率类指标
适用于：ROE、ROA、资产负债率、流动比率、净利率等。

统一返回：
- `value`
- `same_period_last_year`
- `yoy_delta`：展示为百分点变化或绝对比率差
- `yoy_growth`：**默认不强制展示**，只在业务上有解释价值时显示

> 这样既满足“页面上增加同比值和同比增长”的需求，又避免对比率类指标强行展示误导性增长率。

## 8.3 首期核心指标定义（只列首期真正使用）
| 指标 | 公式建议 | 主要数据来源 | 展示规则 |
|------|----------|--------------|----------|
| 营业总收入 | `TOT_OPERA_REV` | income | 当前值 + 去年同期值 + 同比增幅 |
| 营业利润 | `OPERA_PROFIT` | income | 当前值 + 同比变动额 + 同比增幅 |
| 归母净利润 | `NET_PRO_EXCL_MIN_INT_INC` | income | 当前值 + 同比变动额 + 同比增幅 |
| 经营现金流净额 | `NET_CASH_FLOW_OPERA_ACT` | cashflow | 当前值 + 同比变动额 + 同比增幅 |
| 总资产 | `TOTAL_ASSETS` | balance_sheet | 当前值 + 去年同期值 + 同比变动额 |
| 总负债 | `TOTAL_LIAB` | balance_sheet | 当前值 + 去年同期值 + 同比变动额 |
| 归母权益 | `TOT_SHARE_EQUITY_EXCL_MIN_INT` | balance_sheet | 当前值 + 去年同期值 + 同比变动额 |
| 资产负债率 | `TOTAL_LIAB / TOTAL_ASSETS` | balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 流动比率 | `TOTAL_CUR_ASSETS / TOTAL_CUR_LIAB` | balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 速动比率 | `(TOTAL_CUR_ASSETS - INV) / TOTAL_CUR_LIAB` | balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 总资产周转率 | `TOT_OPERA_REV / AVG(TOTAL_ASSETS)` | income + balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 应收账款周转率 | `TOT_OPERA_REV / AVG(ACCT_RECEIVABLE)` | income + balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 存货周转率 | `LESS_OPERA_COST / AVG(INV)` | income + balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| ROE | `NET_PRO_EXCL_MIN_INT_INC / AVG(TOT_SHARE_EQUITY_EXCL_MIN_INT)` | income + balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| ROA | `NET_PRO_EXCL_MIN_INT_INC / AVG(TOTAL_ASSETS)` | income + balance_sheet | 当前值 + 去年同期值 + 同比变动 |
| 净利率 | `NET_PRO_EXCL_MIN_INT_INC / TOT_OPERA_REV` | income | 当前值 + 去年同期值 + 同比变动 |
| 营业利润率 | `OPERA_PROFIT / TOT_OPERA_REV` | income | 当前值 + 去年同期值 + 同比变动 |
| OCF/净利润 | `NET_CASH_FLOW_OPERA_ACT / NET_PRO_EXCL_MIN_INT_INC` | cashflow + income | 当前值 + 去年同期值 + 同比变动 |
| OCF/营业收入 | `NET_CASH_FLOW_OPERA_ACT / TOT_OPERA_REV` | cashflow + income | 当前值 + 去年同期值 + 同比变动 |

## 8.4 杜邦分析口径
### 三层杜邦（首期）
```text
ROE = 净利率 × 资产周转率 × 权益乘数
净利率     = 归母净利润 / 营业总收入
资产周转率 = 营业总收入 / 平均总资产
权益乘数   = 平均总资产 / 平均归母权益
```

### 页面展示要求
- 当前期值
- 去年同期值
- 同比变动
- 多期趋势
- 驱动方向标识

## 8.5 现金流质量口径
| 指标 | 解释 | 数据要求 |
|------|------|----------|
| 经营现金流净额 | 企业经营活动造血能力 | `NET_CASH_FLOW_OPERA_ACT` |
| OCF/净利润 | 利润现金含量 | `NET_CASH_FLOW_OPERA_ACT` + `NET_PRO_EXCL_MIN_INT_INC` |
| OCF/营业收入 | 收入转现金效率 | `NET_CASH_FLOW_OPERA_ACT` + `TOT_OPERA_REV` |
| FCF（简版） | 优先直接使用 PhoenixA 字段 | `FREE_CASH_FLOW` 有则展示，无则隐藏 |

## 8.6 周转与偿债口径
| 指标 | 公式建议 | 是否首期展示 |
|------|----------|--------------|
| 总资产周转率 | `营业总收入 / 平均总资产` | 是 |
| 应收账款周转率 | `营业总收入 / 平均应收账款` | 是（字段齐备时） |
| 存货周转率 | `营业成本 / 平均存货` | 是（字段齐备时） |
| 资产负债率 | `总负债 / 总资产` | 是 |
| 流动比率 | `流动资产 / 流动负债` | 是 |
| 速动比率 | `(流动资产 - 存货) / 流动负债` | 是 |
| 有息负债占比 | 需统一有息负债口径 | Phase 2 |

> 注意：银行、保险、券商的财报口径和制造业差异较大。首期先保证非金融公司可用，对金融类公司只展示元数据和有限基础指标。

---
## 9. PhoenixA 已确认可提供的数据与 BI 可用范围
## 9.1 PhoenixA 的定位不变
PhoenixA 仍然只负责：
- 提供标准化财务/行情/分类数据
- 保证字段与查询契约稳定
- 提供批量查询与字段过滤能力
- 提供 catalog / capability 能力说明

## 9.2 首期已确认可直接消费的数据域
依据 PhoenixA 现有文档，BI 首期可以明确使用以下数据：

| 数据域 | PhoenixA 接口 | 首期用途 | 是否进入首期 |
|--------|---------------|----------|--------------|
| 证券基础信息 | `/api/v2/securities` | 公司搜索、名称/市场/交易所/状态展示 | 是 |
| 财务报表 | `/api/v2/financial/{source}/{statement_type}` | 所有财务指标核心来源 | 是 |
| 行业分类映射 | `/api/v2/taxonomy/by_security/{symbol}` | 行业标签、金融行业识别 | 是 |
| 行业成分股/分类定义 | taxonomy 分类接口 | 同业范围构造 | Phase 1.5 |
| 行业权重/行业日行情 | taxonomy 行业接口 | 行业背景增强 | Phase 1.5 |
| 个股 K 线 | `/api/v2/bars/{asset_type}/{market}` | 页面顶部行情上下文（可选） | 可选 |
| 公司行为 | `/api/v2/corporate-action/{source}/{action_type}` | 分红/配股事件提示条 | Phase 1.5 |
| 财报快报/预告 | `profit_express / profit_notice` | 提前预告或快报 banner | Phase 1.5 |

## 9.3 首期真正使用的 PhoenixA 财务字段
### A. 利润表（income）
首期建议使用：
- `TOT_OPERA_REV`
- `OPERA_PROFIT`
- `TOTAL_PROFIT`
- `NET_PRO_EXCL_MIN_INT_INC`
- `TOT_OPERA_COST`
- `LESS_OPERA_COST`
- `LESS_SELLING_EXP`
- `LESS_ADMIN_EXP`
- `LESS_FIN_EXP`
- `RD_EXP`
- `EBIT`
- `EBITDA`

### B. 资产负债表（balance_sheet）
首期建议使用：
- `TOTAL_ASSETS`
- `TOTAL_LIAB`
- `TOTAL_CUR_ASSETS`
- `TOTAL_CUR_LIAB`
- `TOT_SHARE_EQUITY_EXCL_MIN_INT`
- `INV`
- `ACCT_RECEIVABLE`
- `CURRENCY_CAP`
- `ST_BORROWING`
- `LT_LOAN`
- `BONDS_PAYABLE`

### C. 现金流量表（cashflow）
首期建议使用：
- `NET_CASH_FLOW_OPERA_ACT`
- `NET_CASH_FLOW_INV_ACT`
- `NET_CASH_FLOW_FIN_ACT`
- `FREE_CASH_FLOW`
- `CASH_PAID_PUR_CONST_FIOLTA`
- `CASH_RECP_SG_AND_RS`
- `NET_INCR_CASH_AND_CASH_EQU`

## 9.4 首期按“已有数据”明确不做的内容
以下内容在当前 PhoenixA 文档中未被定义为首期稳定供给，因此不纳入 Phase 1：
- 财报正文、MD&A、管理层表述变化
- 研报式 narrative 文本
- 财报附注级别的更细分业务拆解
- 全市场广覆盖百分位和复杂横截面排名
- 依赖外部 SaaS 或未在 PhoenixA 文档中声明的数据源

## 9.5 对 PhoenixA 的配合要求（仍然是数据供给，不是页面聚合）
### 建议 1：继续确保以下查询能力稳定可用
- `symbols` 多标的查询
- `reporting_periods` 多期批量查询
- `fields` 精确字段过滤
- `ann_date_before` PIT 查询
- `comp_type_code` 过滤

### 建议 2：稳定输出公司与行业元数据
- 公司名称、市场、状态
- `canonical_category_name`
- `canonical_index_code`
- `derived_flags.financial_sector`

### 建议 3：不要新增页面聚合型 PhoenixA API
例如不建议在 PhoenixA 新增：
- `/dashboard/company/{symbol}`
- `/dupont/{symbol}`
- `/cashflow-quality/{symbol}`

这些仍应由 Artemis BI 层负责。

---
## 10. Artemis BI API 设计建议
## 10.1 路由前缀
建议统一使用：
```text
/bi/...
```
而不是继续挂到：
```text
/workbench/...
```

## 10.2 建议 API 清单
### Phase 1
#### 1）公司财务总览
```text
GET /bi/financial/company/{symbol}/dashboard
```
参数：
- `as_of_date`
- `market=zh_a`
- `source=amazing_data`

返回：
- company meta
- KPI cards
- 多期趋势
- warnings
- source notes

#### 2）杜邦分析
```text
GET /bi/financial/company/{symbol}/dupont
```
返回：
- `roe`
- `net_margin`
- `asset_turnover`
- `equity_multiplier`
- 多期趋势
- driver summary（结构化）

#### 3）经营质量 / 现金流 / 周转 / 偿债
```text
GET /bi/financial/company/{symbol}/quality
```
返回：
- operating quality
- cashflow quality
- turnover metrics
- leverage/solvency metrics
- warnings

#### 4）指标定义
```text
GET /bi/meta/metrics
```
返回：
- metric code
- 中文名
- 公式说明
- 数据来源
- 适用对象
- version

### Phase 1.5
#### 5）同行对比
```text
POST /bi/financial/peer-comparison
```
请求：
- `symbols[]` 或 `industry_code`
- `as_of_date`
- `metrics[]`

> 当前代码状态：**已实现初版**。

### Phase 2+
#### 6）财报数智化分析
```text
GET /bi/financial/company/{symbol}/insight
```
返回：
- structured highlights
- anomaly list
- trend summary
- `narrative_source = rules | atlas`

> 当前代码状态：**已实现结构化摘要初版，但只基于 Artemis 规则，不包含 Atlas 字段。**

## 10.3 指标返回模型建议
重点不是“把 PhoenixA 数据透传给前端”，而是定义清晰的 BI read model，并统一同比字段。

建议每个指标对象至少支持：
- `value`
- `unit`
- `same_period_last_year`
- `yoy_delta`
- `yoy_growth`（若适用）
- `display_kind`（amount / ratio / pct_point）
- `data_period`
- `source_fields`

例如：
```json
{
  "symbol": "000001",
  "company": {
    "name": "平安银行",
    "market": "zh_a",
    "industry": "银行",
    "comp_type_code": 2
  },
  "as_of_date": "2026-05-19",
  "latest_period": "2025-12-31",
  "kpis": {
    "revenue_total": {
      "value": 123.45,
      "unit": "亿元",
      "same_period_last_year": 110.12,
      "yoy_delta": 13.33,
      "yoy_growth": 0.121,
      "display_kind": "amount",
      "data_period": "2025-12-31",
      "source_fields": ["income.TOT_OPERA_REV"]
    },
    "roe": {
      "value": 0.143,
      "unit": "ratio",
      "same_period_last_year": 0.136,
      "yoy_delta": 0.007,
      "display_kind": "pct_point",
      "data_period": "2025-12-31",
      "source_fields": [
        "income.NET_PRO_EXCL_MIN_INT_INC",
        "balance_sheet.TOT_SHARE_EQUITY_EXCL_MIN_INT"
      ]
    }
  },
  "warnings": [
    {"code": "ocf_weaker_than_profit", "severity": "medium", "message": "经营现金流低于净利润"}
  ]
}
```

## 10.4 Artemis BI API read model 详细 schema（MVP）

> 说明：以下 schema 只描述 `BI` 读模型，不包含 `Atlas` 字段，也不预留 narrative 富文本结构。

### 10.4.1 公共基础结构
```json
{
  "symbol": "000001",
  "as_of_date": "2026-05-19",
  "latest_period": "2025-12-31",
  "company": {
    "symbol": "000001",
    "name": "平安银行",
    "market": "zh_a",
    "exchange": "SZ",
    "industry": {
      "taxonomy": "sw",
      "level": 1,
      "code": "801000",
      "name": "银行",
      "index_code": "801000.SI"
    },
    "comp_type_code": 2,
    "financial_sector": true
  }
}
```

### 10.4.2 MetricValue schema
每个指标统一为：
```json
{
  "code": "revenue_total",
  "label": "营业总收入",
  "unit": "亿元",
  "display_kind": "amount",
  "value": 123.45,
  "same_period_last_year": 110.12,
  "yoy_delta": 13.33,
  "yoy_growth": 0.121,
  "data_period": "2025-12-31",
  "source_fields": ["income.TOT_OPERA_REV"],
  "available": true,
  "degraded": false,
  "notes": []
}
```

字段语义：
- `display_kind`: `amount | ratio | pct_point | count`
- `available`: 该指标是否成功计算
- `degraded`: 是否为降级展示（如字段缺失导致部分能力隐藏）
- `notes`: 口径说明或降级原因

### 10.4.3 `GET /bi/financial/company/{symbol}/dashboard`
```json
{
  "symbol": "000001",
  "as_of_date": "2026-05-19",
  "latest_period": "2025-12-31",
  "company": {},
  "kpis": [
    {"code": "revenue_total"},
    {"code": "operating_profit"},
    {"code": "net_profit_parent"},
    {"code": "operating_cashflow"},
    {"code": "total_assets"},
    {"code": "debt_ratio"},
    {"code": "roe"},
    {"code": "roa"}
  ],
  "trend_sections": [
    {
      "code": "revenue_profit_trend",
      "title": "收入 / 利润趋势",
      "periods": ["2023-12-31", "2024-03-31", "2024-06-30", "2024-09-30", "2025-12-31"],
      "series": [
        {"code": "revenue_total", "label": "营业总收入", "values": [1,2,3]},
        {"code": "operating_profit", "label": "营业利润", "values": [1,2,3]},
        {"code": "net_profit_parent", "label": "归母净利润", "values": [1,2,3]}
      ]
    }
  ],
  "summary_cards": [
    {
      "code": "profit_summary",
      "title": "盈利摘要",
      "items": [{"code": "revenue_total"}, {"code": "operating_profit"}, {"code": "net_profit_parent"}]
    }
  ],
  "warnings": [
    {
      "code": "ocf_weaker_than_profit",
      "severity": "medium",
      "title": "现金转化偏弱",
      "message": "经营现金流低于归母净利润",
      "evidence_metric_codes": ["operating_cashflow", "net_profit_parent"]
    }
  ],
  "source_notes": [
    {
      "section": "kpis",
      "statement_types": ["income", "balance_sheet", "cashflow"],
      "pit_rule": "ann_date_before",
      "metric_version": "v1"
    }
  ]
}
```

### 10.4.4 `GET /bi/financial/company/{symbol}/dupont`
```json
{
  "symbol": "000001",
  "as_of_date": "2026-05-19",
  "latest_period": "2025-12-31",
  "company": {},
  "headline_metrics": {
    "roe": {},
    "net_margin": {},
    "asset_turnover": {},
    "equity_multiplier": {}
  },
  "dupont_tree": {
    "code": "roe",
    "label": "ROE",
    "metric": {},
    "children": [
      {"code": "net_margin", "label": "净利率", "metric": {}},
      {"code": "asset_turnover", "label": "总资产周转率", "metric": {}},
      {"code": "equity_multiplier", "label": "权益乘数", "metric": {}}
    ]
  },
  "trend_sections": [
    {"code": "roe_trend", "series": [{"code": "roe", "values": []}]},
    {"code": "net_margin_trend", "series": [{"code": "net_margin", "values": []}]},
    {"code": "asset_turnover_trend", "series": [{"code": "asset_turnover", "values": []}]},
    {"code": "equity_multiplier_trend", "series": [{"code": "equity_multiplier", "values": []}]}
  ],
  "driver_summary": [
    {
      "driver": "net_margin",
      "direction": "up",
      "message": "利润率贡献为主要正向驱动"
    }
  ],
  "comparison_rows": [
    {
      "period": "2025-12-31",
      "roe": 0.143,
      "net_margin": 0.08,
      "asset_turnover": 0.92,
      "equity_multiplier": 1.94
    }
  ]
}
```

### 10.4.5 `GET /bi/financial/company/{symbol}/quality`
```json
{
  "symbol": "000001",
  "as_of_date": "2026-05-19",
  "latest_period": "2025-12-31",
  "company": {},
  "panels": [
    {
      "code": "operating_quality",
      "title": "经营利润质量",
      "metrics": [{"code": "operating_profit_margin"}, {"code": "net_margin"}],
      "trend_sections": [],
      "table_rows": [],
      "warnings": []
    },
    {
      "code": "cashflow_quality",
      "title": "现金流质量",
      "metrics": [{"code": "operating_cashflow"}, {"code": "ocf_to_profit"}],
      "trend_sections": [],
      "table_rows": [],
      "warnings": []
    },
    {
      "code": "turnover",
      "title": "资产周转",
      "metrics": [{"code": "asset_turnover"}, {"code": "ar_turnover"}, {"code": "inventory_turnover"}],
      "trend_sections": [],
      "table_rows": [],
      "warnings": []
    },
    {
      "code": "solvency",
      "title": "资产负债 / 偿债",
      "metrics": [{"code": "debt_ratio"}, {"code": "current_ratio"}, {"code": "quick_ratio"}],
      "trend_sections": [],
      "table_rows": [],
      "warnings": []
    }
  ],
  "source_notes": []
}
```

### 10.4.6 `GET /bi/meta/metrics`
```json
{
  "version": "v1",
  "metrics": [
    {
      "code": "revenue_total",
      "label": "营业总收入",
      "category": "profitability",
      "display_kind": "amount",
      "formula": "TOT_OPERA_REV",
      "source_fields": ["income.TOT_OPERA_REV"],
      "applicable_comp_types": [1],
      "phase": "phase1",
      "available": true
    }
  ]
}
```

---
## 11. Cthulhu 前端设计建议（更细化到层级 / 层次）
## 11.1 前端入口建议
尽管后端落在 Artemis，**前端建议新增独立顶层菜单组 `BI`**。

### 原因
1. 用户心智更清晰：看板 ≠ 研究工作台
2. 后续不管 BI 后端是否拆分，前端导航都稳定
3. 可以容纳未来非财务 BI 页面，不被 `workbench` 名称限制
4. 当前 `Cthulhu` 的顶层导航就是按产品域组织，`BI` 很适合成为新增一级域

## 11.2 信息架构分层
结合 `Cthulhu` 当前的 `TopNavService`、`app.routes.ts`、`side-menu.service.ts`，建议按 4 层组织：

| 层级 | 载体 | 建议内容 | 说明 |
|------|------|----------|------|
| L1 | 顶部导航（Top Nav） | `BI` | 与 `CronJobs / Artemis / Workbench / Atlas / PhoenixA` 并列 |
| L2 | 左侧菜单（Side Menu） | `总览`、`公司财务`、`同业对比`、`指标字典` | 适配现有 `menuGroup + menu order` 机制 |
| L3 | 页面内局部导航（Local Tabs） | `总览 / 杜邦 / 质量` | 放在公司页头部，不挤占全局侧边栏 |
| L4 | 页面区块（Sections） | KPI / 趋势 / 表格 / 预警 / 来源说明 | 真正承载信息密度 |

> 这里有一个很重要的实现约束：当前 `side-menu.service.ts` 是“顶层 feature + 一个 shell + 一组扁平子菜单”的模式，因此**公司详情页内部的多页面切换更适合做成局部 tab，而不是继续增加很多侧边栏菜单项**。

## 11.3 建议路由结构
```text
/bi
/bi/overview
/bi/financial
/bi/financial/company/:symbol/overview
/bi/financial/company/:symbol/dupont
/bi/financial/company/:symbol/quality
/bi/financial/compare                  # Phase 1.5
/bi/meta/metrics
/bi/financial/company/:symbol/insight  # Phase 2+
```

## 11.4 菜单与导航层次建议
### 顶部导航
- 新增 `BI`
- icon 建议使用 `dashboard` / `area-chart` / `fund` 这类心智更接近看板的图标

### 左侧菜单（Phase 1）
1. `总览`：进入 BI landing
2. `公司财务`：进入公司检索与最近访问
3. `指标字典`：查看口径和字段来源

### 左侧菜单（Phase 1.5 增补）
4. `同业对比`

### 页面内局部导航（公司详情页）
当用户已经进入某个公司后，在页面头部放局部 tabs：
- `总览`
- `杜邦`
- `质量`
- `数智分析`（Phase 2 后才显示）

这样可以形成清晰层次：
`BI（顶层） → 公司财务（侧栏） → 某公司（上下文） → 总览/杜邦/质量（局部 tabs）`

## 11.5 前端模块建议
```text
src/app/features/bi/
├─ bi.routes.ts
├─ pages/
│  ├─ bi-shell.component.ts
│  ├─ bi-overview.page.ts
│  ├─ company-financial-entry.page.ts
│  ├─ company-financial-shell.page.ts
│  ├─ financial-dashboard.page.ts
│  ├─ dupont-analysis.page.ts
│  ├─ financial-quality.page.ts
│  ├─ metric-dictionary.page.ts
│  ├─ peer-comparison.page.ts          # Phase 1.5
│  └─ financial-insight.page.ts        # Phase 2+
├─ services/
│  └─ bi-api.service.ts
├─ models/
│  └─ bi.models.ts
└─ ui/
   ├─ company-context-bar.component.ts
   ├─ metric-card.component.ts
   ├─ metric-grid.component.ts
   ├─ trend-chart.component.ts
   ├─ warning-list.component.ts
   ├─ source-note.component.ts
   ├─ dupont-tree.component.ts
   └─ metric-definition-drawer.component.ts
```

## 11.6 页面布局建议
### A. BI Landing
- 上：模块说明 + 搜索
- 中：功能入口卡片
- 下：数据范围说明 + 使用指引

### B. 公司详情页统一骨架
- 第一行：Breadcrumb
- 第二行：公司上下文条（代码/名称/行业/市场/报告期/日期）
- 第三行：局部 tabs（总览 / 杜邦 / 质量）
- 第四行起：具体页面内容

### C. 财务总览页布局
- 上：8 张 KPI 卡片（2 行 4 列）
- 中：趋势图（左 8 列） + 预警区（右 4 列）
- 下：财务结构摘要 + 数据来源说明

### D. 杜邦分析页布局
- 上：ROE 总卡 + 三层拆解
- 中：4 张小趋势图
- 下：驱动解释表 + 历史对比表

### E. 质量页布局
- 采用四段式自上而下布局：
  1. 经营利润质量
  2. 现金流质量
  3. 资产周转
  4. 偿债与杠杆

每一段内部保持同一结构：
- 指标卡片
- 趋势图
- 明细表
- 预警/说明

## 11.7 展示规范建议
- 前端只负责展示单位转换和图表渲染
- 指标口径、颜色逻辑、预警阈值尽量由后端返回或统一配置
- 关键指标支持 hover 查看“公式 / 来源 / 更新时间 / 口径版本”
- 所有卡片统一位置展示：当前值、去年同期值、同比变动额、同比增长/同比变动
- 对比率类指标统一用“百分点变化”样式，避免误导用户

## 11.8 Cthulhu 路由 / 页面清单（MVP 实施版）

> 说明：当前只建设 `BI` 页面，不建设 `Atlas` 联动页，也不在 `BI` 内嵌 `Atlas` 入口。

| 路由 | 页面组件 | 页面职责 | 调用 API | 是否首期 |
|------|----------|----------|----------|----------|
| `/bi` | shell redirect | BI 顶层入口，跳转到 `/bi/overview` | 无 | 是 |
| `/bi/overview` | `bi-overview.page.ts` | BI landing、模块说明、公司检索、快捷入口 | 可选 `GET /bi/meta/metrics` | 是 |
| `/bi/financial` | `company-financial-entry.page.ts` | 公司搜索 / 最近访问 / 快速跳转 | 无或后续证券检索接口 | 是 |
| `/bi/financial/company/:symbol` | redirect shell | 公司页统一入口，默认跳 `/overview` | 无 | 是 |
| `/bi/financial/company/:symbol/overview` | `financial-dashboard.page.ts` | 财务总览看板 | `GET /bi/financial/company/{symbol}/dashboard` | 是 |
| `/bi/financial/company/:symbol/dupont` | `dupont-analysis.page.ts` | 杜邦分析页 | `GET /bi/financial/company/{symbol}/dupont` | 是 |
| `/bi/financial/company/:symbol/quality` | `financial-quality.page.ts` | 经营质量 / 现金流 / 周转 / 偿债页 | `GET /bi/financial/company/{symbol}/quality` | 是 |
| `/bi/meta/metrics` | `metric-dictionary.page.ts` | 指标字典 / 口径说明 / 字段来源 | `GET /bi/meta/metrics` | 是 |
| `/bi/financial/compare` | `peer-comparison.page.ts` | 同业对比 | `POST /bi/financial/peer-comparison` | 已实现初版 |
| `/bi/financial/company/:symbol/insight` | `financial-insight.page.ts` | 结构化财报摘要 | `GET /bi/financial/company/{symbol}/insight` | 已实现初版 |

## 11.9 Cthulhu 页面实现清单（MVP）

### Phase 1 必做页面
1. `BI Overview / Landing`
   - 模块说明
   - 股票代码输入
   - 最近访问列表
   - 功能入口卡片
2. `Company Financial Overview`
   - 公司上下文条
   - 8 个 KPI 卡
   - 3 组趋势图
   - 预警列表
   - 数据来源说明
3. `Dupont Analysis`
   - ROE 总卡
   - 三层拆解树
   - 多期趋势
   - 驱动解释
4. `Financial Quality`
   - 经营质量 panel
   - 现金流质量 panel
   - 资产周转 panel
   - 偿债与杠杆 panel
5. `Metric Dictionary`
   - 指标名称
   - 公式
   - 字段来源
   - 是否首期可用

### Phase 1 非必做（可先占位）
- `Peer Comparison`（当前已实现初版）
- `Financial Insight`（当前已实现结构化摘要初版）

## 11.10 当前 BI 文档边界声明
为避免范围漂移，当前前端设计边界明确如下：
- 不做 `Atlas` 页面跳转耦合
- 不做 `Atlas` 文本摘要卡片
- 不做财报原文阅读器
- 不做跨产品的 `BI + Atlas` 混合洞察页
- 本轮实现只围绕 `BI 结构化财务看板` 展开

## 11.11 当前前端实现补充说明
在原始 MVP 设计基础上，当前实现已经额外补充：
- 趋势区从“表格趋势”升级为真正图表展示（ECharts）
- `BI Overview / 公司财务入口` 已补远程证券搜索体验
- `同行对比` 页面已可用，支持 `symbols[]` 发起对比
- `结构化摘要` 页面已可用，但只基于 Artemis 规则生成
- 以上扩展仍然严格位于 `BI` 范围内，不引入 `Atlas`

---
## 12. 财报数智化分析后置建议
## 12.1 为什么后置
你的 comment 是对的：**财报数智化分析不应该和首期结构化财务看板一起推进**。原因有三：
1. 首期的关键风险在于指标口径和页面读模型，不在文本生成
2. 当前 PhoenixA 已明确的是结构化数据，不是财报正文语料能力
3. 若太早引入 narrative，会让需求从“做对财务指标”变成“做像研究报告”，复杂度急剧上升

## 12.2 建议演进顺序
### Phase 2：结构化摘要
- 由 Artemis BI Engine 基于规则生成短摘要
- 只总结指标变化、异常项、驱动项
- 不接入 LLM

### Phase 3：Atlas / LLM 增强
- 财报原文摘要
- 管理层表述变化
- 风险事项提炼
- 文本证据引用

## 12.3 Artemis 与 Atlas 的边界建议
| 能力 | 放在哪 |
|------|--------|
| 结构化财务指标计算 | Artemis |
| 同比/对比/拆解 | Artemis |
| 看板 API | Artemis |
| 结构化摘要（规则生成） | Artemis（Phase 2） |
| 财报原文解析 / LLM 摘要 / 图谱补充 | Atlas（Phase 3） |

---
## 13. 缓存与计算策略建议
## 13.1 MVP 阶段
使用 Artemis 进程内缓存或轻量 TTL cache 即可。

缓存 key 建议：
```text
symbol + market + as_of_date + source + metric_version
```

适用对象：
- 公司总览
- 杜邦拆解
- 质量页多 panel 结果
- 同期多期趋势结果

## 13.2 Phase 1.5 / Phase 2
如果同一批热门标的会频繁访问，再考虑：
- Redis 缓存
- 每日 snapshot 预计算
- 定时 warm-up

## 13.3 什么时候需要预计算
满足以下条件再做：
- 首页需要同时展示全市场/全行业 TopN
- 同行比较用户访问频繁
- 单页面要同时展示多个公司面板
- Phase 2 后结构化摘要计算代价开始明显上升

---
## 14. 何时应该从 Artemis 中拆出独立 BI 服务
建议提前写入 ADR 的“拆分触发条件”：

### 满足以下任意 3 条，可启动独立 BI 服务拆分
1. BI API 数量和代码量已接近或超过 Artemis 其他子域总和
2. BI 需求已明显超出财务/量化分析，扩展到多业务域 dashboard
3. 需要独立的发布节奏，不希望 Artemis 任务/引擎变更影响 BI
4. 需要独立的权限体系、租户隔离、用户画像
5. 需要大规模预计算、物化视图、snapshot jobs
6. 需要聚合 PhoenixA、Atlas、外部 SaaS、日志指标等多个数据源
7. Cthulhu 中 BI 已成为一级核心产品模块，而非分析附属页

**也就是说：现在不拆，但要把“以后怎么拆”设计进去。**

---
## 15. 分阶段实施建议
## Phase 0：口径与契约准备
- 明确首期指标清单
- 逐项确认 PhoenixA 已有字段与可计算指标
- 明确非金融 / 金融公司差异处理策略
- 输出 metric definition 文档
- 输出“可展示 / 降级展示 / 后置”的指标矩阵

## Phase 1：Artemis BI MVP（只做结构化财务看板）
- 新增 `bi_engine`
- 新增 `/bi/financial/company/{symbol}/dashboard`
- 新增 `/bi/financial/company/{symbol}/dupont`
- 新增 `/bi/financial/company/{symbol}/quality`
- 新增 `/bi/meta/metrics`
- Cthulhu 新增 `BI` 顶层菜单与基础页面层级
- 页面统一支持同比值与同比增长/同比变动展示

## Phase 1.5：同业对比与数据增强
- 行业内公司对比
- 行业映射驱动的 peer set
- 快报 / 预告 / 公司行为事件条
- 更多趋势与预警

## Phase 2：结构化财报摘要
- 新增 `/bi/financial/company/{symbol}/insight`
- 基于规则生成结构化 highlights
- 输出变化项 / 异常项 / 驱动项摘要

## Phase 3：Atlas / LLM 文本增强
- Artemis 对接 Atlas narrative 能力
- 财报/公告/图谱联动补充
- 文本证据和解释链路

## Phase 4：是否拆服务评估
- 按第 14 章触发条件评估是否独立为 BI 服务
---
## 16. 最终建议（面向当前决策）
如果你现在要做这个 BI 能力，我的建议是：
### 后端落位
- **放在 Artemis**
- 但以**新子域 `BI Engine`** 实现
- **不要塞进 PhoenixA，也不要先新建独立服务**
### 前端落位
- **在 Cthulhu 新建顶层 `BI` 模块**
- 不放到 `Workbench` 导航下
### PhoenixA 角色
- 继续作为数据中台
- 补齐通用数据读取与字段契约
- 不承载 dashboard 聚合逻辑
### Atlas 角色
- 暂时不是主承载者
- 在财报“数智化分析”阶段作为增强能力接入
### 首期最稳的策略
> **Artemis 负责“算”和“装配页面读模型”，PhoenixA 负责“供数”，Cthulhu 负责“展示”，Atlas 负责后续“文本与知识增强”。**
这条路线在当前资源约束下最稳，也最容易把首期财务看板真正做出来。
---
## 17. 建议的 ADR（可后续拆成正式 ADR）
### ADR-001
**BI 首期后端落位于 Artemis，而非新建独立服务。**
### ADR-002
**PhoenixA 不承载看板聚合逻辑，仅提供标准数据供给。**
### ADR-003
**Cthulhu 新增顶层 BI 模块，而非挂入 Workbench。**
### ADR-004
**财报数智化分析采用“结构化规则优先，Atlas/LLM 增强可插拔”的演进路径。**
---
## 18. 相关文档
- `docs/system_design/2026-04-29 DESIGN_OF_FINANCIAL_QUANT_PLATFORM.md`
- `docs/system_design/2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md`
- `app/projects/phoenixA/docs/2026-04-14 ARCHITECTURE_DESIGN_FOR_PHOENIXA_V2.md`
- `app/projects/phoenixA/docs/api_biz_data_description/financial_statements.md`
- `app/projects/phoenixA/docs/2026-05-11 FACTOR_ENGINE_DATA_CONTRACT.md`
- `app/projects/artemis/docs/2026-04-02_0 FEATURE_STRATEGY_RESEARCH_WORKBENCH.md`
---
*文档创建时间：2026-05-19*
