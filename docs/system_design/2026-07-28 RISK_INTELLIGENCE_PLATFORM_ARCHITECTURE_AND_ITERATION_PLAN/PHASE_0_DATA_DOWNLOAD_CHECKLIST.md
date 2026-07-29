# Phase 0 数据下载清单

> 日期：2026-07-28
> 用途：Phase 0 唯一数据执行清单
> 说明：当前机器无法访问生产，`CODE_EXISTS` 仅表示代码存在，不表示生产已经下载或调度；开发机已完成的极小样本验证单独标为 `CANARY`

状态：

- `TODO`：尚未实现；
- `CODE_EXISTS`：任务代码已存在，等待修复、扩围或生产验证；
- `CANARY`：正在小范围真实写入验证；
- `BACKFILLING`：历史回填中；
- `DAILY`：日常/周期增量已运行；
- `READY`：历史和日常要求均满足；
- `BLOCKED`：来源或写入存在阻塞。

---

## 1. 短期核心数据

这些数据必须达到 `READY` 才能完成 Phase 0。

| ID | 数据集 | Artemis 任务 | 主来源候选 | 写入 | 历史目标 | 调度 | 当前状态 | 当前动作 |
|---|---|---|---|---|---|---|---|---|
| C01 | 国内证券身份（股票、指数、ETF、可转债） | `STOCK_ZH_A_LIST` | AmazingData 代码信息接口 | PhoenixA `security_registry` | 当前快照；仅写新增或变化身份 | 每交易日 | `CODE_EXISTS` | 核心四类默认开启；港股通、逆回购、期货、期权按需开启 |
| C02 | A 股不复权日线 | `STOCK_ZH_A_HIST_PARENT/CHILD` | BaoStock | PhoenixA 股票日线 | 2015/2016 至今 | 每交易日盘后 | `CODE_EXISTS` | 修复填零后全量回填 |
| C03 | 成交量/额/换手率 | 同 C02 | BaoStock | PhoenixA bars/ext | 同 C02 | 每交易日盘后 | `CODE_EXISTS` | 缺失改 NULL，保留真实零 |
| C04 | PE/PB/PS/PCF | 同 C02 | BaoStock | PhoenixA bars ext | 同 C02 | 每交易日盘后 | `CODE_EXISTS` | 取消无标记填零 |
| C05 | `tradestatus/isST` | 扩展 C02 | BaoStock | PhoenixA bars ext | 来源可提供范围 | 每交易日盘后 | `CODE_EXISTS` | 小范围回填后核对停牌与 ST 样本 |
| C06 | 复权因子 | `STOCK_ZH_A_BS_ADJUST_FACTOR_PARENT/CHILD` | BaoStock | PhoenixA `adjust_factor` | 2015 至今 | 每交易日/公司行为后 | `CODE_EXISTS` | 全量运行并确认 BJ 范围 |
| C07 | 核心指数身份 | `STOCK_ZH_A_LIST` | AmazingData `get_code_info(EXTRA_INDEX_A)` | PhoenixA `security_registry` | 当前有效指数 | 每交易日 | `CODE_EXISTS` | 与其他证券身份统一增量维护 |
| C08 | 核心指数日线 | `INDEX_ZH_A_DAILY` | AmazingData `query_kline` | PhoenixA 既有 Bars | 2015 至今 | 每交易日盘后 | `CODE_EXISTS` | 仅下载配置白名单，并按各 `security_id` 数据库水位增量 |

---

## 2. Phase 2–3 蓄水数据

R01–R06、R10–R17 必须达到 `DAILY` 或 `BACKFILLING + DAILY`。R07–R09 至少完成 Canary，来源不稳定时可标记 `BLOCKED`。

| ID | 数据集 | Artemis 任务 | 主来源候选 | 写入 | 历史目标 | 调度 | 当前状态 | 当前动作 |
|---|---|---|---|---|---|---|---|---|
| R01 | 申万分类层级 | `STOCK_ZH_A_MKT_CATEGORY_SWHY` | AmazingData | PhoenixA taxonomy | 当前完整版本 | 低频 | `CODE_EXISTS` | 从样例扩为完整分类 |
| R02 | 申万行业成分 | `STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY` | AmazingData | PhoenixA constituent | 可回填范围 + 当前起快照 | 每日/每周 | `CODE_EXISTS` | 全行业运行并保存快照日期 |
| R03 | 申万行业权重 | 已有 Parent/Child | AmazingData | PhoenixA industry weight | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 修复缺失填零并扩围 |
| R04 | 申万行业日行情/估值 | 已有 Parent/Child | AmazingData | PhoenixA industry daily | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 修复 OHLC/估值填零并扩围 |
| R05 | 科技行业白名单 | 配置数据 | 申万分类 | 配置文件 + PhoenixA taxonomy | 当前版本 | 分类变化时 | `CODE_EXISTS` | 与完整申万分类核对后冻结首版 |
| R06 | 融资融券市场汇总 | `STOCK_ZH_A_MARGIN_SUMMARY` | AmazingData `get_margin_summary` | `ods.margin_summary_daily` | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 从数据库水位 +1 日增量；小范围 Canary |
| R07 | 沪深港通/北向指标 | `STOCK_ZH_A_HSGT_HIST` | AKShare `stock_hsgt_hist_em` | `ods.hsgt_daily` | 来源稳定范围 | 每交易日 | `CODE_EXISTS` | `symbols` 配置，逐 symbol 水位过滤；首期北向资金 |
| R08 | 各标的 QVIX | `INDEX_ZH_A_OPTION_QVIX` | AKShare 9 个 QVIX 日频接口 | `ods.option_qvix_daily` | 来源稳定范围 | 每交易日 | `CODE_EXISTS` | 逐 symbol 水位过滤；逐接口 Canary |
| R09 | 期权每日统计 | `OPTION_ZH_A_DAILY_STATS` | AKShare `option_daily_stats_sse/szse` | `ods.option_daily_stats` | 来源稳定范围 | 每交易日 | `CODE_EXISTS` | 按交易所顺序补齐缺失工作日 |
| R10 | 全球宽基/成长指数 | `GLOBAL_SECURITY_LIST` + `GLOBAL_INDEX_DAILY` | AKShare `index_global_spot_em`、`index_global_hist_em`、`stock_hk_index_daily_sina` | `security_registry` + 标准 Bars | 2015 至今 | 身份每日；行情各市场收盘后 | `CODE_EXISTS` | 身份任务维护完整可用指数；行情任务只消费 SPX/NDX/HSI/HSTECH/KS11/TWII/N225 白名单 |
| R11 | 费城半导体 SOX | 待确定 | AKShare `macro_global_sox_index` 仅有收盘值 | 待确定 | 2015 至今 | 美国收盘后 | `BLOCKED` | 不能伪造 OHLC；先寻找真实 OHLC 源 |
| R12 | VIX/VXN | 待确定 | 当前 SDK 文档未确认可用 OHLC 源 | 待确定 | 2015 至今 | 美国收盘后 | `BLOCKED` | 先确认 VIX 真实历史源；VXN 延后 |
| R13 | 中美国债收益率、期限利差、GDP 年增率 | `GLOBAL_SECURITY_LIST` + `GLOBAL_RATE_DAILY` | AKShare `bond_zh_us_rate` | `security_registry` + `ods.market_observation_daily` 纵向事实 | 2015 至今 | 每日 | `CODE_EXISTS` | 接口全部 12 个值字段按 `observation_type` 保存，逐 security_id 水位增量 |
| R14 | DXY 与主要汇率 | `GLOBAL_SECURITY_LIST` + `GLOBAL_FX_DAILY` | AKShare 全球指数/外汇实时清单与历史 | `security_registry` + 标准 Bars | 2015 至今 | 每日 | `CODE_EXISTS` | 注册所有可用身份；行情只消费 UDI、USDCNY、USDCNH、USDJPY、USDKRW 白名单 |
| R15 | 国际商品期货 | `GLOBAL_SECURITY_LIST` + `GLOBAL_COMMODITY_DAILY` | AKShare `futures_global_spot_em`、`futures_global_hist_em` | `security_registry` + 标准 Bars | 2015 至今 | 每日 | `CODE_EXISTS` | 注册可用期货身份；行情首期只下载铜/黄金/原油并可逐步扩白名单 |
| R16 | 美股科技/半导体白名单 | `STOCK_US_LIST` + `STOCK_US_DAILY` | AKShare `stock_us_spot_em`、`stock_us_hist` | `security_registry` + 标准 Bars | 2015 至今 | 身份每日；行情美国收盘后 | `CODE_EXISTS` | 证券身份完整注册；行情仅按 symbols/exchanges 选择并逐 security_id 增量 |
| R17 | 港股科技/半导体白名单 | 待拆分 `STOCK_HK_LIST` / `STOCK_HK_DAILY` | AKShare 港股清单与历史 | `security_registry` + 标准 Bars | 2015 至今 | 港股收盘后 | `PENDING` | 不再混入美股任务；独立完成身份来源和 Canary 后接入 |

---

## 3. Phase 5–6 中期蓄水数据

这些数据必须完成批量 Canary 并进入日常或周期调度，历史回填可以继续。

| ID | 数据集 | Artemis 任务 | 主来源候选 | 写入 | 历史目标 | 调度 | 当前状态 | 当前动作 |
|---|---|---|---|---|---|---|---|---|
| M01 | 资产负债表 | `STOCK_ZH_A_BALANCE_SHEET` | AmazingData | PhoenixA financial statement | 2015 至今 | 财报季每日 | `CODE_EXISTS` | 去掉样例证券限制 |
| M02 | 利润表 | `STOCK_ZH_A_INCOME` | AmazingData | PhoenixA financial statement | 2015 至今 | 财报季每日 | `CODE_EXISTS` | 去掉样例证券限制 |
| M03 | 现金流量表 | `STOCK_ZH_A_CASH_FLOW` | AmazingData | PhoenixA financial statement | 2015 至今 | 财报季每日 | `CODE_EXISTS` | 去掉样例证券限制 |
| M04 | 业绩预告 | `STOCK_ZH_A_PROFIT_NOTICE` | AmazingData | PhoenixA financial statement/event | 2015 至今 | 每日 | `CODE_EXISTS` | 全市场运行并保留公告日期 |
| M05 | 业绩快报 | `STOCK_ZH_A_PROFIT_EXPRESS` | AmazingData | PhoenixA financial statement/event | 2015 至今 | 每日 | `CODE_EXISTS` | 全市场运行并保留公告日期 |
| M06 | 分红 | `STOCK_ZH_A_DIVIDEND`/BaoStock dividend | AmazingData 主源 | PhoenixA corporate action | 2015 至今 | 每日/每周 | `CODE_EXISTS` | 选定主源避免重复 |
| M07 | 配股 | `STOCK_ZH_A_RIGHT_ISSUE` | AmazingData | PhoenixA corporate action | 2015 至今 | 每日/每周 | `CODE_EXISTS` | 去掉样例证券限制 |
| M08 | 龙虎榜 | `STOCK_ZH_A_LONG_HU_BANG` | AmazingData | PhoenixA long hu bang | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 修复填零并扩大范围 |
| M09 | 研报 | `EASTMONEY_RESEARCH_REPORT` | 东方财富 | PhoenixA 元数据 + MinIO PDF | 2024 至今并持续 | 每日 | `BACKFILLING` | 继续运行和失败重试 |
| M10 | A 股公告 | `STOCK_ZH_A_NOTICE` | CNInfo/交易所优先 | PhoenixA 元数据；原文仍待 MinIO | 来源可回填范围 | 每日 | `CODE_EXISTS` | 按证券公告最大日期 +1 增量下载；元数据 Canary 后补原文保存 |
| M11 | 财报披露计划 | `STOCK_ZH_A_DISCLOSURE_SCHEDULE` | CNInfo/AKShare | PhoenixA 日程/元数据 | 来源近四期 | 每日/每周 | `CODE_EXISTS` | 动态生成当前报告期；来源返回当期快照后只写新增或变化事件 |

---

## 4. 暂缓数据

- 分钟、Tick、逐笔和订单簿；
- 全球全量股票和全量财务；
- 完整期权曲面；
- 社交媒体和全网新闻；
- 卫星、物流、招聘、专利等另类数据；
- 真实供应链订单、库存和交付；
- 商业分析师一致预期；
- 券商持仓、成交和组合级实时数据。
