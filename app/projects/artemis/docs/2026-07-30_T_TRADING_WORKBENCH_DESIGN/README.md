# Artemis 做 T 研究工作台设计

> 日期：2026-07-30  
> 状态：Phase 0-6 MVP 已实现并完成最小全链路验收  
> 影响项目：Artemis、PhoenixA、Cthulhu；Cronjob 为后续批量与实时调度提供编排  
> 第一轮实现范围：历史分钟数据、因果信号、逐日复盘、批量统计报告，不连接券商、不自动交易

## 1. 目标

本设计为 A 股日内做 T 研究提供一条可审计的端到端链路：

1. Artemis 下载并标准化分钟 K 线；
2. PhoenixA 保存分钟行情并提供统一查询；
3. Artemis 在严格 point-in-time 边界内逐根回放行情；
4. 信号引擎生成候选点、决策点和模拟成交点；
5. Cthulhu 以“一个交易日一页”的方式展示分钟 K 线、买卖点、原因和统计；
6. 对单股或股票集合运行批量回测并生成结构化报告；
7. 当历史回测和实时影子验证均达到门槛后，再扩展实时订阅。

核心成功标准不是在事后图形中命中绝对最高/最低点，而是：在不使用未来数据的条件下，产生扣除成本后具有稳定正期望、可解释、可复现的信号。

## 2. 文档导航

- [01_REQUIREMENTS_AND_BOUNDARIES.md](01_REQUIREMENTS_AND_BOUNDARIES.md)：需求、术语、非目标、因果边界和验收原则。
- [02_ARCHITECTURE_AND_MODULES.md](02_ARCHITECTURE_AND_MODULES.md)：总体架构、模块划分、调用时序和部署边界。
- [03_MINUTE_DATA_CONTRACT_AND_STORAGE.md](03_MINUTE_DATA_CONTRACT_AND_STORAGE.md)：分钟数据契约、PhoenixA 表、下载与质量规则。
- [04_SIGNAL_REPLAY_AND_REPORT.md](04_SIGNAL_REPLAY_AND_REPORT.md)：特征、信号算法、成交模型、回放和统计报告。
- [05_API_AND_CTHULHU_UI.md](05_API_AND_CTHULHU_UI.md)：HTTP API、前端页面、图表标记和交互设计。
- [06_PHASED_DEVELOPMENT_AND_TEST_PLAN.md](06_PHASED_DEVELOPMENT_AND_TEST_PLAN.md)：逐 Phase 开发、测试、发布、回滚和后续迭代计划。

## 3. 决策摘要

- 内部周期统一使用 `min1/min5/min15/min30/min60`；外部 SDK 周期只在适配器边界转换。
- 第一轮只将原始不复权分钟价格作为成交价格；复权因子独立保存，禁止使用包含未来公司行为的前复权价格模拟成交。
- 信号时间、决策时间、可成交时间和成交时间必须分开记录。
- 事后最优高低点只作为评估基准，禁止进入在线特征。
- 单日交互回放直接走 Workbench API；批量执行复用同一内核，后续可由 TaskEngine/Cronjob 编排。
- 第一轮使用透明的因果规则基线；机器学习只作为候选点过滤器进入后续 Phase。
- `no_signal` 是合法且重要的结果，不强制每个交易日产生交易。
- 当前仅持久化分钟行情。回放默认 `persistence_mode=ephemeral`，结果只随 HTTP 响应返回前端；需要跨用户保存、比较和审计时才显式选择 `summary_only/full`。

## 4. 第一轮交付物

- PhoenixA `min5/nf` 分钟 bars 表及通用 bars API 时间戳支持；
- Artemis `STOCK_ZH_A_MINUTE_PARENT/CHILD` 下载任务；
- Artemis 做 T 特征、信号、模拟成交、交易配对、单日回放、批量报告服务；
- `/workbench/t-trading/*` API，默认回测结果不落库；
- Cthulhu Workbench 做 T 复盘页；
- 单元、API、最小全链路测试；
- Artemis、PhoenixA、Cthulhu CHANGELOG。

## 5. 实现与验收状态

- 已实现 `min5/nf` 的 BaoStock 下载、PhoenixA TIMESTAMPTZ 存储和 Workbench 查询；其他 canonical period 保留在底层边界，MVP API/UI 只开放具有物理表和任务配置的 `min5`。
- 已实现严格因果回放：当前 bar 收盘决策、下一 bar 开盘成交，且有前缀不变性测试防止未来数据参与。
- 已实现单日 replay 和最多 500 个 security-day 组合的同步 batch；batch 默认只返回摘要，单项失败隔离。
- 已实现 `ephemeral` 唯一结果模式，没有回测 repository/DAO/table；前端刷新后结果自然释放。
- 已实现 Cthulhu 日导航、判断点/成交点标记、信号审计、成本后统计和批量报告。
- 自动测试：Artemis 做 T/分钟下载 12 项通过，PhoenixA controller/DAO/const 通过，Cthulhu production build 通过。
- 真实小样本：`security_id=3172`（600000）在 `2024-07-01` 下载并存储 48 根 min5 bars，随后通过真实 PhoenixA -> Artemis HTTP 链路得到 2 个信号、2 个下一 bar 成交和 1 个完整往返；run meta 为 `persistence_mode=ephemeral`。

## 6. 延后能力

- AmazingData Level-1 历史/实时五档快照；
- 1 分钟全市场长期历史下载；
- 机器学习模型训练、模型注册和 champion/challenger；
- 实时影子会话、heartbeat、断线恢复；
- 券商连接、真实下单、订单回报和资金对账。
