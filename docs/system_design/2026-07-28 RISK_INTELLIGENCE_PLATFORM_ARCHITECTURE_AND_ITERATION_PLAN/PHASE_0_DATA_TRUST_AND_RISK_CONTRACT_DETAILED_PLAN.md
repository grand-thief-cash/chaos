# Phase 0 计划：核心数据修复与风险数据蓄水

> 状态：Proposed
> 日期：2026-07-28
> 上位文档：[Chaos 风险智能平台架构与分阶段迭代计划](../2026-07-28%20RISK_INTELLIGENCE_PLATFORM_ARCHITECTURE_AND_ITERATION_PLAN.md)
> 文档性质：Phase 0 数据下载、写入、回填和最小验收计划；不包含风险模型和投资策略

---

## 1. 本次调整

Phase 0 不能走向两个极端：

- 不能建设一套过度工业化的数据治理平台；
- 也不能只检查已有数据，而错过短期和中期风险能力所需的数据蓄水。

本阶段采用以下边界：

> 修复核心数据问题；把 Phase 1–3 需要的数据下载和写入能力准备好；让 Phase 5–6 中需要长期积累的数据开始蓄水；非常远期的数据只保留清单。

Phase 0 不建设：

- 通用数据质量服务；
- 质量规则 DSL；
- 质量结果数据库；
- 数据治理工作流；
- Cthulhu 数据质量页面；
- 大量治理报告。

Phase 0 要建设的是实际可运行的数据链路：

```text
来源
  -> Artemis 下载任务
  -> PhoenixA/MinIO 写入
  -> 历史回填
  -> 日常增量
```

---

## 2. 怎么样算 Phase 0 完成

Phase 0 完成时必须同时满足：

1. A 股核心行情和指数数据完成关键零值修复；
2. 短期核心数据已经完成可用历史回填并能日常更新；
3. 全球市场、宏观风险偏好和科技行业数据已经有可运行的下载、写入和调度链路；
4. 中期财务、公告、研报和公司行为数据已经开始持续蓄水；
5. 所有新增任务都完成至少一次 Canary 下载和真实写入；
6. PhoenixA 中有明确的读取位置，不允许只下载到 Artemis 内存或临时文件；
7. 日常任务支持按最后成功日期增量下载，避免每天全量重抓；
8. 只维护一份简洁的数据下载清单；
9. 用户确认 Phase 1 可以开始。

Phase 0 不要求：

- 所有中期数据的历史回填全部结束；
- 所有数据源达到商业数据供应商级稳定性；
- 为每条数据建设在线质量评分；
- 风险 Feature 和模型已经实现。

---

## 3. 三个数据准备级别

### 3.1 `CORE_READY`：短期核心数据

用于 Phase 1 国内市场风险基线。

Phase 0 完成条件：

- Artemis 任务可运行；
- PhoenixA 可写可读；
- 目标历史已回填；
- 日常增量已调度；
- 关键缺失值和零值语义已修复；
- 最近数据已跟上生产交易日。

### 3.2 `RESERVOIR_RUNNING`：短中期蓄水数据

用于 Phase 2 全球传导、Phase 3 科技行业，以及 Phase 5–6 的早期数据积累。

Phase 0 完成条件：

- Artemis 任务已经实现；
- PhoenixA 或 MinIO 写入已经实现；
- Canary 真实写入成功；
- 日常或周期调度已经启用；
- 历史回填已经开始，允许在 Phase 1 开发期间继续。

### 3.3 `LATER`：远期数据

只记录需求，不在 Phase 0 写任务、建表或下载。

---

## 4. 当前代码中的真实起点

以下结论来自当前开发代码和配置，不代表生产数据已经存在：

| 数据族 | 当前代码情况 | 当前主要问题 |
|---|---|---|
| 国内证券身份 | 已有 `STOCK_ZH_A_LIST` | 已扩展股票、指数、ETF、可转债等类型；来源为当前快照，只向注册表写入新增或变化身份 |
| A 股日线 | 已有 `STOCK_ZH_A_HIST_PARENT/CHILD` | 缺失和解析失败被填零；未保留 `tradestatus/isST` |
| A 股指数日线 | PhoenixA 已有指数日线表；Artemis 已有 `INDEX_ZH_A_DAILY` | 下载白名单由配置控制，身份来自 `security_registry`，按各 `security_id` 水位增量 |
| 复权因子 | 已有 BaoStock Parent/Child 任务 | 生产覆盖未知 |
| 申万行业 | 分类、成分、权重和日行情任务已存在 | 配置日期和代码范围仍偏测试/样例 |
| 财务三表 | 任务已存在 | 当前配置主要是少量证券样例 |
| 业绩预告/快报 | 任务已存在 | 当前配置主要是少量证券样例 |
| 分红/配股 | 任务已存在 | 当前配置主要是少量证券样例 |
| 龙虎榜 | 任务已存在 | 历史范围较短，存在填零路径 |
| 东方财富研报 | 统一任务已存在，正在下载 | 需要继续运行和观察稳定性 |
| 全球市场 | 未发现 Artemis 下载任务 | PhoenixA 也缺少明确的全球日线写入边界 |
| 利率、汇率、波动率、商品 | 未发现 Artemis 下载任务 | 需要新的通用时序写入位置 |
| A 股融资、互联互通、QVIX | 未发现 Artemis 下载任务 | 需要先 Canary 验证来源稳定性 |

---

## 5. 短期核心数据清单：必须达到 `CORE_READY`

### 5.1 A 股证券和行情

| ID | 数据 | 当前任务/来源 | Phase 0 工作 | 历史目标 | 更新频率 | PhoenixA |
|---|---|---|---|---|---|---|
| C01 | 国内证券统一身份 | 已有 `STOCK_ZH_A_LIST`；AmazingData | 默认更新股票、指数、ETF、可转债；支持港股通、逆回购、期货和期权；只写新增或变化身份 | 当前快照 | 每交易日 | 现有 `security_registry` |
| C02 | A 股不复权日线 | 已有 `STOCK_ZH_A_HIST_PARENT/CHILD`；BaoStock | 修复填零；全量回填；增量更新 | 优先 2015/2016 至今 | 每交易日盘后 | 现有股票日线表 |
| C03 | A 股成交量、成交额、换手率 | 与 C02 同任务 | 缺失写 NULL；保留真实零；换手率进入扩展表 | 与 C02 一致 | 每交易日盘后 | 现有 bars/ext |
| C04 | A 股 PE/PB/PS/PCF | 与 C02 同任务；BaoStock | 不再填零；缺失不删除行情行 | 与 C02 一致 | 每交易日盘后 | 现有 bars ext |
| C05 | `tradestatus/isST` | BaoStock 日线接口已有候选字段 | 加回下载；选择扩展表或最小状态表写入 | 来源可提供范围 | 每交易日盘后 | 现有扩展表或最小新增表 |
| C06 | 复权因子 | 已有 `STOCK_ZH_A_BS_ADJUST_FACTOR_*`；BaoStock | 从样例/未知状态切换为全量；确认 BJ 支持范围 | 2015 至今优先 | 每交易日或公司行为后 | 现有 `adjust_factor` |

说明：

- C02 是 Phase 1 最重要的数据；
- C05 用于区分停牌、ST 和数据缺失；
- 如果 BaoStock 对 BJ 的字段或历史不完整，BJ 可以被明确降级，但 SH/SZ 不能被拖延；
- 涨跌停状态优先根据价格、证券板块和规则派生，不单独下载一套重复数据。

### 5.2 A 股核心指数

| ID | 数据 | 候选来源/API | Phase 0 工作 | 历史目标 | 更新频率 | PhoenixA |
|---|---|---|---|---|---|---|
| C07 | 核心指数身份 | AmazingData `get_code_info(EXTRA_INDEX_A)` | 由 `STOCK_ZH_A_LIST` 与其他证券类型统一写入 | 当前有效指数 | 每交易日 | 现有 `security_registry` |
| C08 | 核心指数日线 | AmazingData `query_kline` | `INDEX_ZH_A_DAILY` 只下载配置白名单，并按各 `security_id` 最近日期 +1 增量 | 2015 至今优先 | 每交易日盘后 | 现有指数日线表 |

首批指数白名单：

- 上证指数；
- 深证成指；
- 沪深 300；
- 中证 500；
- 中证 1000；
- 创业板指；
- 科创 50；
- 上证 50；
- 全 A 或可获得的全市场代表指数。

不为每个指数创建一个任务。使用一个任务代码，通过 `symbols` 变体配置管理白名单。

### 5.3 `CORE_READY` 验收

每项只检查：

- 历史最早和最晚日期；
- 实际行数；
- 最近日期；
- 主键重复；
- OHLC 合法；
- 最近 20 个交易日是否有整日缺口；
- Artemis 最近一次任务是否成功；
- PhoenixA 是否真实写入。

不生成复杂质量评分或长期质量报告。

---

## 6. Phase 2–3 数据清单：Phase 0 必须启动蓄水

这些数据应在 Phase 0 启动蓄水。

其中：

- R01–R06、R10–R17 是 Phase 2–3 的主要输入，必须达到 `RESERVOIR_RUNNING`；
- R07–R09 受公开来源和披露规则影响较大，必须完成 Canary；来源不稳定时可以记录 `BLOCKED`，但不能用伪造或不完整数据代替；
- R07–R09 被阻塞不影响 Phase 1 开始，但必须在进入 Phase 2 前解决或删除相应 Feature。

### 6.1 申万行业和科技板块

| ID | 数据 | 当前任务/来源 | Phase 0 工作 | 回填/蓄水要求 | 更新频率 |
|---|---|---|---|---|---|
| R01 | 申万一级/二级/三级分类 | 已有 `STOCK_ZH_A_MKT_CATEGORY_SWHY`；AmazingData | 从样例配置切换为完整分类 | 保存当前完整版本 | 低频检查 |
| R02 | 行业成分 | 已有 `STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY` | 全行业运行；从 Phase 0 起保存每次快照日期 | 能回填则回填；不能则立即开始快照 | 每日或每周 |
| R03 | 行业权重 | 已有 Parent/Child；AmazingData | 修复缺失权重填零；扩大指数和日期范围 | 优先回填 2015 至今；至少从现在持续保存 | 每交易日 |
| R04 | 行业日行情与估值 | 已有 Parent/Child；AmazingData | 修复 OHLC/估值填零；全行业回填 | 优先 2015 至今 | 每交易日 |
| R05 | 科技行业白名单 | 由 R01–R04 派生 | 固定电子、计算机、通信及首批二级行业代码 | 保存版本 | 分类变化时 |

首批科技二级方向：

- 半导体；
- 消费电子；
- 元件；
- 光学光电子；
- 通信设备；
- 软件开发；
- IT 服务。

AI 算力、光模块、设备、材料等产业主题，如果没有稳定的历史行业代码，先作为 Atlas Crosswalk 或自定义篮子，不在 Phase 0 强行造历史分类。

### 6.2 国内流动性和风险偏好

| ID | 数据 | 候选来源/API | Phase 0 工作 | 历史目标 | 更新频率 |
|---|---|---|---|---|---|
| R06 | 沪深融资融券市场汇总 | AmazingData `get_margin_summary` | 独立任务；查询数据库最新交易日，下载 `max(start_date, last_update+1)` 之后的数据；来源同一交易日返回多条市场记录但不提供市场标识，因此按交易日汇总可加字段后写成全市场一条记录 | 来源可提供的最长稳定范围，优先 2015 至今 | 每交易日 |
| R07 | 沪深港通/北向历史指标 | AKShare `stock_hsgt_hist_em` | `symbols` 支持六种来源参数；接口虽返回全量，但只写各 symbol 数据库水位之后的记录 | 来源可提供范围 | 每交易日 |
| R08 | 中国期权波动率 QVIX | AKShare 50ETF、300ETF、500ETF、创业板、科创板等 9 个 QVIX 日频接口 | 一个 QVIX 任务按 `symbols` 调用对应 API，并逐 symbol 增量写入真实 OHLC | 来源可提供范围 | 每交易日 |
| R09 | 期权每日统计 | AKShare `option_daily_stats_sse`、`option_daily_stats_szse` | 独立表保存两个交易所全部标的；按交易所水位从最早缺失工作日顺序补齐 | 来源可提供范围 | 每交易日 |

R06–R09 按 API 和业务粒度拆成四个任务，不再通过一个 `dataset` 分支耦合：

```text
STOCK_ZH_A_MARGIN_SUMMARY
STOCK_ZH_A_HSGT_HIST
INDEX_ZH_A_OPTION_QVIX
OPTION_ZH_A_DAILY_STATS
```

### 6.3 全球市场传导

| ID | 数据 | 首批对象 | 候选来源/API | 历史目标 | 更新频率 |
|---|---|---|---|---|---|
| R10 | 全球宽基和成长指数 | 身份清单完整维护；行情首批 SPX、NDX、HSI、HSTECH、KS11、TWII、N225 | AKShare `index_global_spot_em` + `index_global_hist_em`；HSTECH 使用 `stock_hk_index_daily_sina` | 2015 至今优先 | 身份每日；行情各市场收盘后 |
| R11 | 全球半导体指数 | SOX | `macro_global_sox_index` 只有收盘值，不能写入要求真实 OHLC 的 Bar；真实 OHLC 源确认前阻塞 | 2015 至今优先 | 美国收盘后 |
| R12 | 全球波动率 | VIX；可获得时增加 VXN | 当前 SDK 文档未确认真实 OHLC 历史源，来源确认前阻塞 | 2015 至今优先 | 美国收盘后 |
| R13 | 中美利率和宏观序列 | 中美国债 2Y/5Y/10Y/30Y、10Y-2Y 利差、中美 GDP 年增率全部字段 | AKShare `bond_zh_us_rate` | 2015 至今优先 | 每日 |
| R14 | 汇率和美元 | DXY、USD/CNY、USD/CNH、USD/JPY、USD/KRW | `index_global_hist_em`、`forex_hist_em` 等，Canary 后定主源 | 2015 至今优先 | 每日 |
| R15 | 全球商品代理 | 铜、黄金、原油 | AKShare `futures_global_hist_em` | 2015 至今优先 | 每日 |

R10–R15 先由统一身份任务维护 `security_registry`，再由少量行情任务消费白名单：

```text
GLOBAL_SECURITY_LIST
GLOBAL_INDEX_DAILY
GLOBAL_RATE_DAILY
GLOBAL_FX_DAILY
GLOBAL_COMMODITY_DAILY
```

指数、外汇和国际期货的 OHLC 全部写入标准 Bars，不为品种扩列。利率、利差和 GDP 等标量序列写入纵向 `market_observation_daily`，用 `security_id + observation_type` 分类，不为每个字段扩列。

### 6.4 全球科技龙头观察池

全球指数不能完全代表半导体供应链，因此 Phase 0 同时启动一个很小的公司观察池。

首批候选：

- 美国：NVIDIA、AMD、Broadcom、Intel、Qualcomm、Micron；
- 中国香港：腾讯、阿里巴巴、中芯国际；
- 台湾、韩国、日本：如果当前免费来源不能稳定提供个股历史，先使用区域和行业指数，不强行接入脆弱爬虫。

| ID | 数据 | 候选来源/API | Phase 0 要求 |
|---|---|---|---|
| R16 | 美股科技/半导体龙头日线 | AKShare `stock_us_spot_em` + `stock_us_hist` | `STOCK_US_LIST` 注册身份；`STOCK_US_DAILY` 只下载 symbols/exchanges 选择，2015 至今回填、每日更新 |
| R17 | 港股科技/半导体龙头日线 | AKShare 港股清单与历史 | 不混入美股任务；后续独立拆成 `STOCK_HK_LIST` / `STOCK_HK_DAILY` |

证券清单用于稳定身份和 `security_id`；历史行情仍只下载白名单或明确交易所批次，不因注册全量身份而下载全市场历史。

---

## 7. Phase 5–6 中期数据：已有能力必须开始或继续蓄水

这些数据暂不阻塞 Phase 1，但越早积累越有价值。

### 7.1 财务和公司行为

| ID | 数据 | 现有任务/来源 | Phase 0 工作 | 更新频率 |
|---|---|---|---|---|
| M01 | 资产负债表 | `STOCK_ZH_A_BALANCE_SHEET`；AmazingData | 去掉样例证券限制；分批全市场回填 | 财报季每日增量 |
| M02 | 利润表 | `STOCK_ZH_A_INCOME`；AmazingData | 去掉样例证券限制；分批全市场回填 | 财报季每日增量 |
| M03 | 现金流量表 | `STOCK_ZH_A_CASH_FLOW`；AmazingData | 去掉样例证券限制；分批全市场回填 | 财报季每日增量 |
| M04 | 业绩预告 | `STOCK_ZH_A_PROFIT_NOTICE` | 去掉样例证券限制；保存公告日期 | 每日 |
| M05 | 业绩快报 | `STOCK_ZH_A_PROFIT_EXPRESS` | 去掉样例证券限制；保存公告日期 | 每日 |
| M06 | 分红 | `STOCK_ZH_A_DIVIDEND`、BaoStock dividend | 选定主源和补充源，避免重复事实 | 每日或每周 |
| M07 | 配股 | `STOCK_ZH_A_RIGHT_ISSUE` | 去掉样例证券限制 | 每日或每周 |
| M08 | 龙虎榜 | `STOCK_ZH_A_LONG_HU_BANG` | 修复缺失数值填零；扩大历史范围 | 每交易日 |

财务数据的完整 PIT 和修订治理不在 Phase 0 完成，但必须保留来源提供的公告日期，不能只保存报告期。

### 7.2 公告和研报

| ID | 数据 | 当前/候选来源 | Phase 0 工作 | 更新频率 |
|---|---|---|---|---|
| M09 | 东方财富个股/行业/策略/宏观研报 | 已有 `EASTMONEY_RESEARCH_REPORT` | 保持当前下载；完善失败重试和持续调度 | 每日 |
| M10 | A 股公告目录与原文 | AKShare `stock_zh_a_disclosure_report_cninfo` | 按证券已保存公告最大日期 +1 增量下载；先保存元数据，不做事件抽取 | 每日 |
| M11 | 财报披露计划 | AKShare `stock_report_disclosure` | 按运行日期拼接当前有效报告期；接口返回当期全市场快照后，仅写入新增或发生变化的预约事件 | 每日或每周 |

写入边界：

- 文档原文进入 MinIO；
- PhoenixA 保存文档 ID、证券、标题、来源、发布时间、抓取时间和对象路径；
- Atlas 在 Phase 0 不做事件抽取，只继续处理已经下载的研报调试工作。

### 7.3 中期数据的 Phase 0 门槛

M01–M11 不要求全部历史回填结束，但必须：

- 任务不是单证券测试配置；
- 至少完成一次批量 Canary；
- PhoenixA/MinIO 真实写入成功；
- 增量游标或最近日期可用；
- 调度已经启用；
- 失败不会阻塞 C01–C08 的核心行情任务。

---

## 8. 非常远期数据：Phase 0 暂缓

以下数据只保留需求，不写下载任务：

- 分钟、Tick、逐笔成交和订单簿；
- 全球全部股票和全部公司财务；
- 完整期权波动率曲面和全合约 Greeks；
- 社交媒体情绪；
- 全网新闻爬取；
- 卫星、物流、招聘、专利和另类数据；
- 供应链真实订单、库存和交付数据；
- 商业数据库才稳定提供的分析师一致预期；
- 券商账户、真实持仓和成交回报；
- 组合级实时保证金和交易对手数据。

当后续风险阶段能明确说明这些数据会改善什么判断时，再单独立项。

---

## 9. 数据来源选择规则

Phase 0 不要求一次接入所有备选来源。

每条数据只选择：

1. 一个主来源；
2. 一个已记录但默认关闭的备选来源；
3. 主来源 Canary 失败或历史明显不足时才切换。

当前建议：

| 数据 | 主来源候选 | 备选 |
|---|---|---|
| A 股日线和复权 | BaoStock | AKShare |
| 申万行业、财务、公司行为 | AmazingData | AKShare 对应接口 |
| A 股核心指数 | AKShare 指数接口 | BaoStock/其他 AKShare 指数接口 |
| 全球指数、汇率、商品 | AKShare 东方财富历史接口 | AKShare 新浪或区域专用接口 |
| 美股/港股白名单 | AKShare 历史接口 | 全球指数/ETF 代理 |
| 研报 | 现有东方财富任务 | 暂无 |
| 公告 | 交易所/CNInfo 优先的 AKShare 接口 | 东方财富公告接口 |

这里的接口只是本地 SDK 文档中的候选，不代表已经验证可用于生产。Phase 0 必须通过 Canary 决定最终主源。

---

## 10. Artemis 任务代码收敛

已有任务继续复用，不重复创建。

建议新增的任务族：

| 任务代码（建议） | 覆盖数据 | 变体 |
|---|---|---|
| `INDEX_ZH_A_DAILY` | C07–C08 国内核心指数 | `symbols` |
| `STOCK_ZH_A_MARGIN_SUMMARY` | R06 两融市场汇总 | 无；单一 API |
| `STOCK_ZH_A_HSGT_HIST` | R07 沪深港通历史 | `symbols` |
| `INDEX_ZH_A_OPTION_QVIX` | R08 各标的 QVIX | `symbols` |
| `OPTION_ZH_A_DAILY_STATS` | R09 交易所期权每日统计 | `exchanges` |
| `GLOBAL_SECURITY_LIST` | R10、R13–R15 全球指数/外汇/期货/宏观身份 | `sources` |
| `GLOBAL_INDEX_DAILY` | R10 已确认真实 OHLC 来源的全球指数 | `indexes` |
| `GLOBAL_RATE_DAILY` | R13 中美国债收益率、利差和 GDP 全字段 | 无；单一 API |
| `GLOBAL_FX_DAILY` | R14 汇率和美元指数 | `instruments` |
| `GLOBAL_COMMODITY_DAILY` | R15 铜、黄金、原油 | `symbols` |
| `STOCK_US_LIST` | R16 美股身份 | 无；完整身份快照 |
| `STOCK_US_DAILY` | R16 美股行情 | `symbols` 或 `exchanges` |
| `STOCK_ZH_A_NOTICE` | M10 A 股公告 | `category/date` |
| `STOCK_ZH_A_DISCLOSURE_SCHEDULE` | M11 财报披露计划 | `periods` 或 `year + report_types`；默认按运行日期动态生成 |

原则：

- 一个数据族一个任务代码；
- 指数、国家、指标和证券通过配置变体扩展；
- Parent/Child 只在需要按证券拆分并发时使用；
- 不为每个 VIX、汇率或指数创建一套复制代码。

---

## 11. PhoenixA 最小写入准备

### 11.1 复用现有表

以下继续复用当前 PhoenixA：

- A 股证券注册；
- A 股股票日线；
- A 股指数日线；
- BaoStock 扩展字段；
- 复权因子；
- 行业分类、成分、权重和日行情；
- 财务报表；
- 公司行为；
- 龙虎榜；
- 研报下载记录。

### 11.2 新增最小数据族

为新增下载任务只补三类逻辑存储，不建设治理平台：

1. `security_registry` 中的全球指数、外汇、国际期货、宏观序列和美股身份；
2. 标准 Bars 中的全球指数、外汇、国际期货和美股 OHLC；
3. 五个边界明确的非 Bar 数据集：两融汇总、沪深港通、QVIX、期权每日统计、纵向市场观测。

公告继续采用“PhoenixA 元数据 + MinIO 原文”。

对应非 Bar 物理表为 `ods.margin_summary_daily`、`ods.hsgt_daily`、
`ods.option_qvix_daily`、`ods.option_daily_stats` 和
`ods.market_observation_daily`。全球指数、外汇、国际期货和美股行情继续走
既有 Bar 模型/API，仅为新的 `asset_type + market` 组合补物理 Bar 表。

这些存储必须遵守：

- 唯一键能够保证重跑幂等；
- 来源固定在下载任务和字段契约中；只有同一业务字段确实需要多源并存时才增加 `source`；
- 保留原市场日期；
- 文档保留发布时间和抓取时间；
- 不把所有来源专有字段强行塞入一个 JSON 大字段；
- 不为每个指数或指标单独建表。

### 11.3 API 边界

Phase 0 不新增质量 API，但允许新增数据写入和读取所必需的批量接口：

- 批量注册 Instrument；
- 批量 Upsert 日线；
- 查询两融、沪深港通、QVIX、期权每日统计的最新数据日期；
- 批量 Upsert 四类国内风险输入及全球利率、汇率和商品日频业务行；
- 批量 Upsert 文档元数据。

这些是数据接入能力，不是数据治理平台。

---

## 12. 关键零值和缺失值规则

### 12.1 不能使用 `-1`

`-1` 会进入收益、估值、标准化和模型计算，制造虚假的极端风险。

### 12.2 不能统一填零

| 情况 | 处理 |
|---|---|
| 证券、日期缺失 | 拒绝整行并计数 |
| 核心 OHLC 缺失或非法 | 拒绝整行并计数 |
| 估值、换手率等可选字段缺失 | 保留行情行，字段写 `NULL` |
| `NaN/Inf` 或解析失败 | `NULL` 或拒绝核心行，不写零 |
| 来源明确返回真实零 | 保留零 |
| 成交量为零 | 保留，但结合 `tradestatus` 判断 |
| 行业权重缺失 | `NULL`，不解释为零权重 |

### 12.3 历史数据处理

1. 先修 Artemis 新数据逻辑；
2. Canary 重导少量证券和日期；
3. 比较 NULL、零值和行数；
4. 再重导受影响的数据范围；
5. 不执行“全表所有零值改 NULL”。

不建设隔离服务。任务日志只需要记录：

- 下载行数；
- 成功写入行数；
- 拒绝行数；
- 缺失/非法字段计数；
- 少量错误样例。

---

## 13. 最小时间语义

Phase 0 只保留风险计算真正需要的时间：

### 市场日线

- `market_date`：原市场交易日期；
- `market_timezone`：原市场时区；
- `source`：数据来源；
- Artemis 任务完成时间由任务运行记录提供。

### 财务、公告和研报

- `reporting_period`：报告期；
- `published_at`：来源发布或公告时间；
- `retrieved_at`：下载时间；
- 原始文件对象路径。

不要求所有表同时增加 `available_at/revised_at/vintage`。未来确实使用可修订宏观数据训练模型时，再增加 Vintage。

---

## 14. 简洁的数据下载清单

Phase 0 只新增并维护一个文件：

```text
PHASE_0_DATA_DOWNLOAD_CHECKLIST.md
```

[Phase 0 数据下载清单](./PHASE_0_DATA_DOWNLOAD_CHECKLIST.md)

每行只需要：

| 字段 | 含义 |
|---|---|
| id | C/R/M 编号 |
| dataset | 数据集 |
| task_code | Artemis 任务 |
| source | 当前主来源 |
| sink | PhoenixA/MinIO 写入位置 |
| history_from | 目标或实际起点 |
| schedule | 调度频率 |
| status | TODO/CANARY/BACKFILLING/DAILY/READY/BLOCKED |
| note | 一句话问题 |

不再分别建设任务报告、来源报告、异常报告和质量报告。

完成证据直接使用：

- Artemis 任务代码和配置；
- 一次成功运行记录；
- PhoenixA Catalog/查询结果；
- Cronjob 配置；
- 少量 Canary 样例。

---

## 15. 各服务在 Phase 0 做什么

### Artemis

- 修复已知填零；
- 把现有样例任务改造成可全量和可增量运行；
- 新增指数、全球、宏观和公告任务族；
- 所有任务写入 PhoenixA 或 MinIO；
- 支持按最后日期增量；
- 输出最小运行计数。

对其他服务提供：

- 可持续更新的原始/标准化数据；
- 任务运行事实；
- 下载来源和批次信息。

### PhoenixA

- 复用已有国内 ODS；
- 全球 Instrument/日线复用既有 `security_registry + Bars` 写入；
- 非 Bar 数据仅补 A 股市场压力、全球利率、汇率和商品四类明确业务写入；
- 提供 Artemis 所需的批量 Upsert 和最近日期查询；
- 继续使用 Catalog 查看实际覆盖。

不做：

- 质量规则引擎；
- 复杂数据准备度 API；
- 新治理页面。

### Cronjob

- 核心 A 股任务优先；
- 全球任务按原市场收盘时间调度；
- 财务、公告、研报独立限速；
- 回填与日常任务分开，避免回填拖垮每日更新；
- 失败重试保持幂等。

### MinIO

- 继续保存研报；
- 保存新增公告原文；
- 对象路径中保留来源、文档类型和日期。

### Feature Platform

- Phase 0 不计算风险 Feature；
- 只确认后续能够按数据日期读取；
- 不阻塞数据蓄水。

### Atlas

- 继续调试现有研报知识图谱；
- Phase 0 不要求事件和 Impact Engine 完成；
- 可以消费已经下载的研报和公告，但不得阻塞下载链路。

### Aegis 与 Cthulhu

- 无 Phase 0 必做代码；
- 不创建风险服务；
- 不建设页面。

---

## 16. Phase 0 的四个顺序步骤

### Phase 0A：核心行情修复

工作：

- C01–C08 任务、配置和 PhoenixA 写入确认；
- 修复 A 股行情填零；
- 新增核心指数任务；
- Canary 重导。

完成门槛：

- C01–C08 全部完成 Canary；
- 零值修复通过；
- 可以开始历史回填。

### Phase 0B：短期数据任务和写入

工作：

- 完成 R01–R17 的任务族；
- 补 PhoenixA 全球日线和通用序列写入；
- 行业、全球、利率、汇率、波动率、商品完成 Canary；
- 启动日常蓄水。

完成门槛：

- R01–R06、R10–R17 达到 `RESERVOIR_RUNNING`；
- R07–R09 至少完成 Canary；来源不稳定的项目有明确主源替换或标记 `BLOCKED`；
- Blocking 项不能以临时 CSV 代替 PhoenixA 写入。

### Phase 0C：中期数据蓄水

工作：

- 把 M01–M08 从样例配置切换为分批全市场；
- 继续 M09 研报下载；
- 启动 M10 公告和 M11 披露计划；
- 回填任务与每日任务分离调度。

完成门槛：

- M01–M11 至少完成批量 Canary；
- 日常或周期调度已启用；
- 历史回填已开始或排队；
- 中期任务失败不影响核心市场更新。

### Phase 0D：简单验收

工作：

- 更新 `PHASE_0_DATA_DOWNLOAD_CHECKLIST.md`；
- 确认 C01–C08 达到 `CORE_READY`；
- 确认 R/M 数据已经开始蓄水；
- 列出仍被阻塞的来源；
- 用户确认进入 Phase 1。

不编写大型验收报告。

---

## 17. Phase 0 完成后用户能看到什么

用户能看到：

1. 一份明确的数据下载清单；
2. 每个数据是已有、正在回填、已经日更还是被来源阻塞；
3. A 股核心行情已经修复并完成历史准备；
4. 全球、宏观和科技行业数据已经开始持续写入；
5. 财务、公告和研报已经开始为中期阶段蓄水；
6. 非常远期的数据明确没有偷偷扩大 Phase 0；
7. Phase 1 可以直接开始使用哪些数据。

当前开发机无法访问生产，所以现在只能根据代码确认“任务是否存在、写入设计是否存在”。生产真实行数、回填进度和日常更新状态，必须在能访问生产 PhoenixA 的环境填写到下载清单中。

---

## 18. 当前建议

建议确认以下决策：

1. Phase 0 保留数据下载和蓄水，不建设工业化数据治理平台；
2. C01–C08 必须历史可用并日更；
3. R01–R06、R10–R17 必须把任务、写入和调度跑起来，历史回填可以持续；
4. R07–R09 必须完成来源 Canary，不稳定时明确阻塞而不是伪造完整性；
5. M01–M11 必须从样例状态进入真实批量蓄水；
6. 只维护一个简洁下载清单；
7. 新 API 只服务数据写入和读取，不建设质量平台；
8. 非常远期数据全部暂缓；
9. Phase 0D 通过后立即进入 Phase 1，不继续扩张数据范围。
