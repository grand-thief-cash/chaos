# Phase 0 数据下载清单

> 日期：2026-07-28
> 用途：Phase 0 唯一数据执行清单
> 说明：当前机器无法访问生产，`CODE_EXISTS` 仅表示代码存在，不表示生产已经下载或调度

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
| C01 | A 股证券列表 | `STOCK_ZH_A_LIST` | AmazingData | PhoenixA `security_registry` | 当前全量 | 每交易日 | `CODE_EXISTS` | 切换真实全市场配置并验证生产 |
| C02 | A 股不复权日线 | `STOCK_ZH_A_HIST_PARENT/CHILD` | BaoStock | PhoenixA 股票日线 | 2015/2016 至今 | 每交易日盘后 | `CODE_EXISTS` | 修复填零后全量回填 |
| C03 | 成交量/额/换手率 | 同 C02 | BaoStock | PhoenixA bars/ext | 同 C02 | 每交易日盘后 | `CODE_EXISTS` | 缺失改 NULL，保留真实零 |
| C04 | PE/PB/PS/PCF | 同 C02 | BaoStock | PhoenixA bars ext | 同 C02 | 每交易日盘后 | `CODE_EXISTS` | 取消无标记填零 |
| C05 | `tradestatus/isST` | 扩展 C02 | BaoStock | bars ext 或最小状态表 | 来源可提供范围 | 每交易日盘后 | `TODO` | 加回字段并实现写入 |
| C06 | 复权因子 | `STOCK_ZH_A_BS_ADJUST_FACTOR_PARENT/CHILD` | BaoStock | PhoenixA `adjust_factor` | 2015 至今 | 每交易日/公司行为后 | `CODE_EXISTS` | 全量运行并确认 BJ 范围 |
| C07 | 核心指数身份 | `INDEX_ZH_A_DAILY` 的注册步骤 | 固定白名单/AKShare | PhoenixA `security_registry` | 当前白名单 | 低频 | `TODO` | 注册首批核心指数 |
| C08 | 核心指数日线 | `INDEX_ZH_A_DAILY` | AKShare `index_zh_a_hist` | PhoenixA 指数日线 | 2015 至今 | 每交易日盘后 | `TODO` | 新增统一任务和回填 |

---

## 2. Phase 2–3 蓄水数据

R01–R06、R10–R17 必须达到 `DAILY` 或 `BACKFILLING + DAILY`。R07–R09 至少完成 Canary，来源不稳定时可标记 `BLOCKED`。

| ID | 数据集 | Artemis 任务 | 主来源候选 | 写入 | 历史目标 | 调度 | 当前状态 | 当前动作 |
|---|---|---|---|---|---|---|---|---|
| R01 | 申万分类层级 | `STOCK_ZH_A_MKT_CATEGORY_SWHY` | AmazingData | PhoenixA taxonomy | 当前完整版本 | 低频 | `CODE_EXISTS` | 从样例扩为完整分类 |
| R02 | 申万行业成分 | `STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY` | AmazingData | PhoenixA constituent | 可回填范围 + 当前起快照 | 每日/每周 | `CODE_EXISTS` | 全行业运行并保存快照日期 |
| R03 | 申万行业权重 | 已有 Parent/Child | AmazingData | PhoenixA industry weight | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 修复缺失填零并扩围 |
| R04 | 申万行业日行情/估值 | 已有 Parent/Child | AmazingData | PhoenixA industry daily | 2015 至今优先 | 每交易日 | `CODE_EXISTS` | 修复 OHLC/估值填零并扩围 |
| R05 | 科技行业白名单 | 配置数据 | 申万分类 | PhoenixA taxonomy/version | 当前版本 | 分类变化时 | `TODO` | 固定一级和首批二级代码 |
| R06 | 融资融券市场汇总 | `CN_MARKET_STRESS_DAILY` | AKShare 沪深交易所接口 | PhoenixA 日频序列 | 2015 至今优先 | 每交易日 | `TODO` | 新增任务、Canary 和写入 |
| R07 | 沪深港通/北向指标 | `CN_MARKET_STRESS_DAILY` | AKShare `stock_hsgt_hist_em` | PhoenixA 日频序列 | 来源稳定范围 | 每交易日 | `TODO` | 先验证披露和历史字段 |
| R08 | 50ETF/300ETF QVIX | `CN_MARKET_STRESS_DAILY` | AKShare QVIX 接口 | PhoenixA 日频序列 | 来源稳定范围 | 每交易日 | `TODO` | Canary；失败时允许阻塞 |
| R09 | 期权认沽/认购代理 | `CN_MARKET_STRESS_DAILY` | AKShare 期权日频接口 | PhoenixA 日频序列 | 来源稳定范围 | 每交易日 | `TODO` | 只做 50ETF/300ETF 聚合 |
| R10 | 全球宽基/成长指数 | `GLOBAL_INDEX_DAILY` | AKShare `index_global_hist_em` | PhoenixA 全球日线 | 2015 至今 | 各市场收盘后 | `TODO` | SPX/NDX/HSI/HSTECH/KOSPI/KOSDAQ/TWII/N225/TOPIX |
| R11 | 费城半导体 SOX | `GLOBAL_INDEX_DAILY` | AKShare `macro_global_sox_index` | PhoenixA 全球日线 | 2015 至今 | 美国收盘后 | `TODO` | 新增白名单序列 |
| R12 | VIX/VXN | `GLOBAL_INDEX_DAILY` | AKShare 全球指数接口 | PhoenixA 全球日线 | 2015 至今 | 美国收盘后 | `TODO` | VIX 必做，VXN 可用后增加 |
| R13 | 美国国债收益率 | `GLOBAL_RATE_DAILY` | AKShare `bond_zh_us_rate` | PhoenixA 日频序列 | 2015 至今 | 每日 | `TODO` | 2Y/10Y/30Y，3M 可选 |
| R14 | DXY 与主要汇率 | `GLOBAL_FX_DAILY` | AKShare 全球指数/外汇历史 | PhoenixA 日频序列 | 2015 至今 | 每日 | `TODO` | DXY/USD-CNY/USD-CNH/USD-JPY/USD-KRW |
| R15 | 铜/黄金/原油 | `GLOBAL_COMMODITY_DAILY` | AKShare `futures_global_hist_em` | PhoenixA 日频序列 | 2015 至今 | 每日 | `TODO` | 固定少量连续代理 |
| R16 | 美股科技/半导体白名单 | `GLOBAL_SECURITY_DAILY` | AKShare `stock_us_hist` | PhoenixA 全球日线 | 2015 至今 | 美国收盘后 | `TODO` | NVDA/AMD/AVGO/INTC/QCOM/MU |
| R17 | 港股科技/半导体白名单 | `GLOBAL_SECURITY_DAILY` | AKShare `stock_hk_hist` | PhoenixA 全球日线 | 2015 至今 | 港股收盘后 | `TODO` | 腾讯/阿里/中芯国际 |

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
| M10 | A 股公告 | `STOCK_ZH_A_NOTICE` | CNInfo/交易所优先 | PhoenixA 元数据 + MinIO 原文 | 来源可回填范围 | 每日 | `TODO` | 新增最小目录和原文任务 |
| M11 | 财报披露计划 | `STOCK_ZH_A_DISCLOSURE_SCHEDULE` | CNInfo/AKShare | PhoenixA 日程/元数据 | 来源可回填范围 | 每日/每周 | `TODO` | Canary 并保留披露日期 |

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
