# Artemis 做 T 研究工作台设计

> 日期：2026-07-30  
> 状态：信号优先 MVP + AmazingData 上下文策略已实现；待真实账号与迁移环境验收
> 影响项目：Artemis、PhoenixA、Cthulhu；Cronjob 为后续批量与实时调度提供编排  
> 第一轮实现范围：历史分钟数据、因果信号、逐日复盘、批量统计报告，不连接券商、不自动交易

## 1. 目标

本设计为 A 股日内做 T 研究提供一条可审计的端到端链路：

1. Artemis 下载并标准化分钟 K 线；
2. PhoenixA 保存分钟行情并提供统一查询；
3. Artemis 在严格 point-in-time 边界内逐根回放行情；
4. 多策略信号引擎生成可解释 BUY/SELL 点；
5. Cthulhu 以“一个交易日一页”的方式展示分钟 K 线、买卖点、原因和统计；
6. 对单股或股票集合运行批量回测并生成结构化报告；
7. 当历史回测和实时影子验证均达到门槛后，再扩展实时订阅。

核心成功标准不是事后命中绝对最高/最低点，也不是先依赖某个成交假设得到漂亮 PnL，而是：在不使用未来数据的条件下，BUY/SELL 信号在多个后续 horizon 上具有稳定的方向收益、MFE/MAE 和 first-touch 优势，并且可解释、可复现。

## 2. 文档导航

- [01_REQUIREMENTS_AND_BOUNDARIES.md](01_REQUIREMENTS_AND_BOUNDARIES.md)：需求、术语、非目标、因果边界和验收原则。
- [02_ARCHITECTURE_AND_MODULES.md](02_ARCHITECTURE_AND_MODULES.md)：总体架构、模块划分、调用时序和部署边界。
- [03_MINUTE_DATA_CONTRACT_AND_STORAGE.md](03_MINUTE_DATA_CONTRACT_AND_STORAGE.md)：分钟数据契约、PhoenixA 表、下载与质量规则。
- [04_SIGNAL_REPLAY_AND_REPORT.md](04_SIGNAL_REPLAY_AND_REPORT.md)：策略研究、信号算法、前瞻事件评估、实时点流和统计报告。
- [05_API_AND_CTHULHU_UI.md](05_API_AND_CTHULHU_UI.md)：HTTP API、前端页面、图表标记和交互设计。
- [06_PHASED_DEVELOPMENT_AND_TEST_PLAN.md](06_PHASED_DEVELOPMENT_AND_TEST_PLAN.md)：逐 Phase 开发、测试、发布、回滚和后续迭代计划。
- [07_TWO_STAGE_INTRADAY_SIGNAL_RESEARCH_REPORT.md](07_TWO_STAGE_INTRADAY_SIGNAL_RESEARCH_REPORT.md)：单股实验结论、数据扩样、文件型 Level-1 pilot，以及两阶段 BUY/SELL 独立点位模型研究协议。

## 3. 决策摘要

- 内部周期统一使用 `min1/min5/min15/min30/min60`；外部 SDK 周期只在适配器边界转换。
- 第一轮只将原始不复权分钟价格作为成交价格；复权因子独立保存，禁止使用包含未来公司行为的前复权价格模拟成交。
- 信号时间、事后 outcome 时间和可选成交时间必须分开记录。
- 事后最优高低点只作为评估基准，禁止进入在线特征。
- 单日交互回放直接走 Workbench API；批量执行复用同一内核，后续可由 TaskEngine/Cronjob 编排。
- 第一轮使用透明的因果规则基线；机器学习只作为候选点过滤器进入后续 Phase。
- `no_signal` 是合法且重要的结果，不强制每个交易日产生交易。
- 当前仅持久化分钟行情。回放默认 `persistence_mode=ephemeral`，结果只随 HTTP 响应返回前端；需要跨用户保存、比较和审计时才显式选择 `summary_only/full`。

## 4. 第一轮交付物

- PhoenixA stock `min1/min5/min30`、index `min1/min5` 的 `nf` bars 表及通用 bars API；
- Artemis BaoStock 兼容任务，以及 registry-native 的 AmazingData 按需增量 K 线 parent/child；
- Artemis 做 T 多策略特征、信号、前瞻事件评估、单日回放、批量报告服务；
- `/workbench/t-trading/*` API，默认回测结果不落库；
- Cthulhu Workbench 做 T 复盘页；
- 单元、API、最小全链路测试；
- Artemis、PhoenixA、Cthulhu CHANGELOG。

## 5. 实现与验收状态

- 已实现 AmazingData `min1/min30/daily` 个股和 `min1/min5` 指数的按需增量任务；目标证券从 `security_registry` 解析，watermark 所在日重放，避免默认全市场下载。BaoStock `min5` 作为兼容源保留。
- 已实现严格因果回放：完整 bar 可用后决策，信号冻结后由独立 evaluator 统计 min1 的 1/3/5/15 bars 或 min5 的 1/3/6/12 bars 的方向收益、MFE/MAE 和 first-touch；成交模拟默认关闭。
- 已实现单日 replay 和最多 500 个 security-day 组合的同步 batch；batch 默认只返回摘要，单项失败隔离。
- 已实现 `ephemeral` 唯一结果模式，没有回测 repository/DAO/table；前端刷新后结果自然释放。
- 已实现七类策略，包括同分钟历史量比、宽基市场残差反转、日线/30 分钟顺势回踩；行业残差因缺少明确行业指数分钟接口而有意排除。
- 已实现 Cthulhu 日导航、1/5 分钟、多策略选择、每个策略的 BUY/SELL 分色标记、按策略信号效果和批量报告。
- 已实现供应商无关实时 `QuotePoint`、直接消费报价点的在线 compact outcome tracker，以及从新浪网页实际响应解析交易所时间、累计量额和五档盘口的 adapter 核心；实时链路不合成 bar，原始轮询点不落历史行情表。
- 已实现最多 10 只股票、31 个自然日的 AmazingData Level-1 历史快照文件任务：按 `security_id/trade_date` 原子写 ZSTD Parquet + manifest/SHA-256，不写 PhoenixA；真实单日 smoke test 已落 5,770 条快照。
- 单股研究已否定当前对称 MACD/量能/EMA 规则的样本外优势。下一研究基线改为状态 gate + BUY/SELL 独立未来路径模型，并要求 walk-forward、跨股票留一和允许 `no_signal`；详见 07 报告。
- 真实小样本：`security_id=3172`（600000）在 `2024-07-01` 下载并存储 48 根 min5 bars，随后通过真实 PhoenixA -> Artemis HTTP 链路完成信号事件回放；run meta 为 `persistence_mode=ephemeral`。成交模拟仅作显式 opt-in 诊断，不再作为默认评估。

## 6. 延后能力

- AmazingData Level-1 多股票、多日期的样本外增量验证，以及有证据后才讨论数据库契约；
- 1 分钟全市场长期回填（当前仅支持显式按需，或明确 `all_registered=true`）；
- 机器学习模型训练、模型注册和 champion/challenger；
- 实时影子会话、heartbeat、断线恢复；
- 新浪实时 adapter 的调度/监控、腾讯/东财 adapter、compact signal/outcome sink、checkpoint 和 EOD projection；
- 券商连接、真实下单、订单回报和资金对账。
