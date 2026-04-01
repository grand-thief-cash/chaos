# Artemis 基于 Task Orchestration + Backtrader 的回测 / 实时模拟任务系统设计方案

## 0. 文档目标

本文档基于当前 Artemis 已存在的任务编排骨架：

- `BaseTaskUnit`
- `OrchestratorUnit`
- `WorkerUnit`
- `TaskContext`
- `TaskEngine`

在**尽量不引入过度设计**的前提下，给出一个适用于 `backtrader` 的任务系统方案，目标覆盖：

1. **历史回测**：基于 PhoenixA 中已有行情数据执行策略回测。
2. **实时模拟**：使用实时/准实时数据驱动 backtrader，验证过去回测中表现有效的策略在实时推进场景下是否依旧有效。
3. **结果持久化**：回测/实时模拟结果通过 PhoenixA 写入数据库，作为后续查询、分析、审计记录。
4. **与现有任务体系一致**：复用 Artemis 生命周期、父子任务编排、进度上报、日志与 fail-fast 机制。
5. **为长期运行能力预留接口**：实时模拟在业务上允许长期运行；任务调度扩展由配套文档 `app/projects/cronjob/docs/2026-04-01 FEATURE_EXTEND_RUNNING_STRATEGY.md` 承接。

> 本文档当前只做设计，不修改代码。

---

## 1. 需求理解、review 结论与边界

### 1.1 这次要解决的问题

核心诉求不是“做一个 backtrader demo”，而是：

- 在 Artemis 中引入一套**任务化**的 backtrader 执行方式；
- 让回测与实时模拟都能被 `cronjob / API` 触发；
- 支持父任务规划多个子任务，例如：
  - 多标的；
  - 多组策略参数；
  - 多时间窗口；
  - 历史模式与实时模拟模式；
- 让结果沉淀到 PhoenixA，而不是只停留在日志或内存里；
- 为后续 plot 呈现能力预留 artifact 结构，而不在第一阶段绑定最终渲染方式。

### 1.2 本次 review 已确认的结论

基于 review，以下点已经明确：

- 第 1 章列出的“不做事项”是正确的，仍然不纳入本次范围；
- 任务分层接受：
  - 一个 `BACKTRADER_CAMPAIGN` 父任务；
  - 一个 `BACKTRADER_RUN` 子任务；
  - 通过 `mode` 区分历史回测与实时模拟；
- PhoenixA 持久化先坚持 `run_summary + run_artifact`，不提前拆大量细表；
- 实时模式不是正式交易，而是**实时模拟 / paper-like strategy validation**；
- 需要同时考虑 Artemis 架构边界，以及 cronjob 对长期运行任务的扩展；
- plot 暂时不决定最终是“生成图片上传”还是“保存数据由 Cthulhu 绘图”，但系统要预留支持能力。

### 1.3 本文档纳入的范围

本次方案纳入：

- Backtrader 执行模型在 Artemis 任务体系中的映射；
- 历史回测与实时模拟的统一任务框架；
- `strategy_code / data_provider_code / analyzer_profile` 的注册式设计；
- PhoenixA 结果落库模型与 API 方向；
- plot artifact 预留设计；
- Artemis 架构层面的约束与建议；
- 实施顺序建议。

### 1.4 本文档不负责完全展开的范围

为了避免把两个问题混在同一文档里，以下内容只在这里做接口级说明，详细设计放到配套文档：

- `cronjob` 对长期运行任务的执行模型扩展；
- `SYNC / ASYNC` 之外的新 `exec_type` 设计；
- 长期运行任务的 heartbeat / stop / control-plane 语义。

对应文档：

- `app/projects/cronjob/docs/2026-04-01 FEATURE_EXTEND_RUNNING_STRATEGY.md`

### 1.5 本次设计明确不做的事情

为了避免过度设计，下面这些不作为第一阶段目标：

- 真实下单 / 券商交易接入；
- 高频 tick 级低延迟交易系统；
- 分布式任务调度 / 多机 worker 集群；
- 大规模参数优化框架；
- 完整策略研究平台 UI；
- 大体量二进制归档体系；
- 完整的可视化 plotting 平台实现。

---

## 2. 当前代码基础与可复用能力

### 2.1 Artemis 当前任务生命周期骨架

当前 `BaseTaskUnit.run()` 已提供统一生命周期：

1. `parameter_check`
2. `load_task_config`
3. `load_dynamic_parameters`
4. `before_execute`
5. `execute`
6. `post_process`
7. `sink`
8. `finalize`

并且具备：

- 统一 phase timing；
- 统一错误处理；
- 统一 `ctx.stats` 输出；
- 统一日志结构；
- fail-fast 行为。

这与 backtrader 执行天然契合，因为一次策略运行本身就会分成：参数解析、数据准备、引擎构建、策略运行、结果规范化、结果落库。

### 2.2 当前 Orchestrator / Worker 的适配性

现有 `OrchestratorUnit` 已支持：

- `plan()` 产生 child spec；
- 顺序执行 child task；
- 进度上报；
- 子任务失败导致父任务失败。

因此可以直接映射为：

- **父任务**：回测/模拟 campaign orchestrator；
- **子任务**：单次 backtrader run worker。

### 2.3 当前 PhoenixA 的基础能力

从现有代码看，PhoenixA 已具备：

- 股票列表查询；
- 历史行情查询与写入；
- 标准的 controller / service / dao / model 分层；
- Artemis 侧已有 `PhoenixAClient`。

这意味着：

1. 历史回测输入可以优先从 PhoenixA 获取；
2. 结果持久化也继续走同一条 service 边界；
3. Artemis 与 PhoenixA 的职责可以保持清晰：
   - Artemis 负责“任务执行与策略运行”；
   - PhoenixA 负责“数据读取、结果落库、结果查询”。

---

## 3. 总体设计原则

### 3.1 原则一：尽量复用现有任务模型，不重造一套回测调度系统

不建议为 backtrader 单独造一套完全不同的调度框架。

推荐做法：

- 回测/实时模拟仍然是 Artemis 的 task；
- backtrader 只是执行引擎；
- 编排继续由 `OrchestratorUnit -> WorkerUnit` 完成。

### 3.2 原则二：一个 child task = 一个独立 backtrader run

每个子任务只负责一次明确运行，通常对应：

- 一个 `strategy_code`
- 一个 `symbol`
- 一个 `timeframe`
- 一个 `mode`
- 一组 `strategy_params`
- 一个明确的数据提供方式

好处是：

- 生命周期清晰；
- 失败范围小；
- 结果容易落库；
- 将来并发扩展更自然；
- 单次日志与诊断更清楚。

### 3.3 原则三：对 backtrader 的灵活性做白名单式收口

backtrader 很灵活，但任务系统不应直接开放：

- 任意 Python 类路径；
- 任意 import；
- 任意 feed 组合；
- 任意 analyzer / observer 动态拼装。

否则容易带来：

- 参数不可控；
- 安全风险高；
- 可观测性变差；
- 结果 schema 难统一；
- PhoenixA 无法稳定消费结果。

因此建议引入三层注册表机制：

- `strategy_code -> Strategy class`
- `data_provider_code -> feed adapter`
- `analyzer_profile -> analyzers / observers / recorders 组合`

任务入参只传 `code + params`，不直接传可执行对象。

#### 3.3.1 `strategy_code -> Strategy class`

这一层负责：

- 统一策略白名单；
- 限定可用参数；
- 做策略参数 schema 校验；
- 标识支持的市场、周期、mode；
- 给回测结果打稳定的 `strategy_code`。

#### 3.3.2 `data_provider_code -> feed adapter` 的详细设计

这是 review 中需要展开说明的重点。

`data_provider_code` 的目标不是“只是一个数据源名字”，而是一个**受控的数据接入契约**。它代表：

- 数据来自哪里；
- 以什么粒度提供；
- 如何转换成 backtrader 可消费的数据；
- 在历史/实时模式下分别如何 warmup、补齐、重试、记录诊断。

建议把一个 provider entry 定义为：

| 字段 | 说明 |
|---|---|
| `code` | 稳定标识，例如 `phoenixa_hist_daily` |
| `adapter_cls` | 适配器类 |
| `supported_modes` | `historical` / `realtime_test` |
| `supported_timeframes` | `daily`, `1m` 等 |
| `markets` | `CN_A` 等 |
| `warmup_capable` | 是否支持回补 warmup 数据 |
| `replay_capable` | 是否支持历史重放 |
| `stream_capable` | 是否支持持续 live 数据推进 |
| `config_schema` | provider 自身参数校验规则 |
| `diagnostic_fields` | 建议输出的诊断字段 |

适配器本身建议承担以下职责：

1. **参数校验**
   - 例如检查 `symbol/timeframe/adjust/market` 是否支持；
   - 检查 `poll_interval_seconds`、`warmup_bars` 等 provider 参数是否合法。

2. **数据读取与标准化**
   - 历史模式：从 PhoenixA 读取 bars，标准化为统一 bar schema；
   - 实时模式：轮询或流式读取最新 bar，标准化为统一增量 bar schema。

3. **backtrader feed 构建**
   - 把标准化 bars 转换为 backtrader feed 所需的数据结构；
   - 屏蔽不同数据源字段差异。

4. **warmup / backfill**
   - 在实时模拟开始前，为策略准备必要的历史 bar；
   - 这样技术指标有足够 lookback，不会在 live 启动时失真。

5. **诊断信息输出**
   - 记录 gap、重复 bar、延迟、空 bar、异常重试等信息；
   - 供 `diagnostics` artifact 与 `ctx.stats` 使用。

建议 adapter 的概念接口能力包含：

- `validate(params)`
- `load_history(...)`
- `load_warmup(...)`
- `build_bt_feed(...)`
- `iter_live_bars(...)` 或 `poll_next_bar(...)`
- `snapshot_diagnostics()`

这里不要求第一阶段就把接口写得非常抽象，但设计上要保证这几个职责清晰分离。

建议首批 provider code：

- `phoenixa_hist_daily`
- `phoenixa_hist_intraday`（若 PhoenixA 后续补齐）
- `phoenixa_polling_live_1m`

职责边界建议如下：

##### Artemis 负责

- 驱动 adapter 生命周期；
- 统一 bar schema；
- 把数据喂给 backtrader；
- 记录运行期诊断指标。

##### PhoenixA 负责

- 历史数据读取；
- 若后续扩展，也可提供准实时 bar 查询接口；
- 不直接感知 backtrader 细节。

##### 不建议由 adapter 负责的事情

- 策略参数校验；
- 结果落库；
- 任务调度；
- Cronjob 协议。

#### 3.3.3 `analyzer_profile -> analyzers / observers / recorders` 的详细设计

第二个需要展开的重点是 `analyzer_profile`。

`analyzer_profile` 不只是“analyzers list”，更准确地说应是一个**运行观测配置预设**，内部包含：

- analyzers；
- observers；
- Artemis 自定义 recorders；
- summary 提取规则；
- artifact 落库策略。

建议一个 profile entry 至少包含：

| 字段 | 说明 |
|---|---|
| `profile_code` | 稳定标识，例如 `default_hist_v1` |
| `supported_modes` | 适用模式 |
| `supported_timeframes` | 适用周期 |
| `analyzers` | backtrader analyzer 列表 |
| `observers` | backtrader observer 列表 |
| `recorders` | Artemis 业务 recorder 列表 |
| `summary_mapping` | 从 analyzer/recorder 中抽取 summary 的规则 |
| `persist_artifacts` | 建议持久化的 artifact 类型 |
| `plot_capabilities` | 可生成哪些 plot 数据 |

其中三类组件职责要明确区分：

##### A. Analyzers

用于输出**聚合指标**，通常在一次 run 结束或 checkpoint 时计算，例如：

- Returns
- SharpeRatio
- DrawDown
- TradeAnalyzer
- SQN

这类结果更适合进入：

- `summary`
- `analyzers` artifact

##### B. Observers

用于观察**运行过程中的时间序列变化**，例如：

- broker value
- cash
- buy/sell marker
- drawdown line

Observer 更接近“绘图/运行可视化”的原始来源。它们不一定直接形成 summary，但非常适合成为：

- `equity_curve`
- `positions`
- `plot_series`

##### C. Recorders

Recorders 是 Artemis 自定义的一层，用来把 backtrader 运行中的业务事件规范化输出为 JSON 友好的 artifact，例如：

- `EquityCurveRecorder`
- `OrderRecorder`
- `SignalRecorder`
- `LiveDiagnosticsRecorder`
- `PlotManifestRecorder`

Recorder 的价值在于：

- 不依赖 backtrader 原始对象直接跨服务传输；
- 结构稳定，便于 PhoenixA 存储；
- 能为 Cthulhu 绘图预留清晰数据接口。

建议默认 profile：

- `default_hist_v1`
- `default_live_sim_v1`

示意：

- `default_hist_v1`
  - analyzers: `Returns`, `SharpeRatio_A`, `DrawDown`, `TradeAnalyzer`
  - observers: `Broker`, `Trades`
  - recorders: `EquityCurveRecorder`, `TradeRecorder`, `PlotManifestRecorder`

- `default_live_sim_v1`
  - analyzers: `Returns`, `DrawDown`, `TradeAnalyzer`
  - observers: `Broker`
  - recorders: `OrderRecorder`, `SignalRecorder`, `LiveDiagnosticsRecorder`, `EquityCurveRecorder`, `PlotManifestRecorder`

### 3.4 原则四：实时模式先定义为“实时模拟”，不是正式交易模式

这里需要根据 review 做更准确的定义。

实时模式的核心不是“只验证数据接入稳定”，而是：

- 验证过去回测中表现有效的策略；
- 在实时/准实时 bar 持续推进场景下；
- 是否依旧保持逻辑有效性与行为一致性；
- 但**不进入真实交易**。

因此这里建议统一称为：

- `realtime_test`
- 或语义更清楚的 `realtime_simulation`

本质上它是：

- 用 live-like 数据驱动 backtrader；
- 输出订单、信号、仓位、收益、风险变化；
- 人工或调度控制终止；
- 不对接真实券商下单。

### 3.5 原则五：实时模拟在业务上允许长期运行，但调度扩展与策略执行设计解耦

这点是本轮 review 的关键补充。

需要区分两个层面：

#### A. 策略执行层（本文档负责）

关注：

- feed adapter 怎么工作；
- backtrader run 如何组织；
- analyzer / observer / recorder 如何设计；
- 结果如何 checkpoint / 落库。

#### B. 长期运行调度层（配套文档负责）

关注：

- `cronjob` 如何支持长期运行任务；
- `SYNC / ASYNC` 之外是否新增 `LONGRUN`；
- 如何 heartbeat / progress / stop；
- 如何终止与 finalize。

也就是说：

- 在 backtrader 语义上，实时模拟可以是“持续运行直到手动停止”；
- 在 Artemis 现有执行框架上，这已经超出纯 `ASYNC` bounded job 的语义；
- 因此需要 cronjob 与 Artemis 一起扩展运行模型。

---

## 4. 建议的任务分层

### 4.1 任务角色划分

建议增加两类任务：

#### A. 回测/模拟编排父任务（Orchestrator）

建议命名：

- `BACKTRADER_CAMPAIGN`

职责：

- 校验任务请求；
- 解析 `mode`、`strategy_code`、`data_provider_code`、`analyzer_profile`；
- 获取动态数据（标的池、数据可用范围等）；
- 生成子任务列表；
- 汇总子任务进度；
- 在最终阶段形成 campaign summary。

#### B. 单次运行子任务（Worker）

建议命名：

- `BACKTRADER_RUN`

职责：

- 构建单个 backtrader `Cerebro`；
- 挂载 feed / strategy / analyzers / observers / recorders；
- 执行一次历史回测，或一次实时模拟运行实例；
- 规范化结果；
- 落库到 PhoenixA。

### 4.2 是否拆成两个 worker

本轮结论保持：先使用**方案 1**。

- 一个 `BACKTRADER_RUN`
- 通过 `mode` 区分历史回测与实时模拟

理由：

- 结构更统一；
- 结果契约更稳定；
- 父任务 plan 更简单；
- 现在还不需要过早把 worker 按模式拆开。

---

## 5. Backtrader 在 Artemis 生命周期中的映射

### 5.1 `parameter_check`

建议校验：

- `mode` 是否支持；
- `strategy_code` 是否注册；
- `data_provider_code` 是否注册；
- `analyzer_profile` 是否注册；
- `symbols` / `universe_code` 是否提供；
- `timeframe` 是否支持；
- 历史模式下 `start_date / end_date` 是否合理；
- 实时模拟下 `warmup_bars / poll_interval / checkpoint_interval` 是否合理；
- `cash / commission / slippage` 是否合法；
- `strategy_params` 是否通过 schema 校验。

对于长期运行模式，还应额外校验：

- 是否声明了 stop policy；
- 是否声明 checkpoint 频率；
- 是否声明 progress / heartbeat 频率。

### 5.2 `merge_parameters`

继续复用 `task.yaml`。

适合放入默认配置的内容：

- `mode + market + timeframe` 对应的默认 broker 参数；
- 默认 `data_provider_code`；
- 默认 `analyzer_profile`；
- 默认 `persist_artifacts`；
- 默认 checkpoint / report 策略；
- 默认 plot artifact 开关。

### 5.3 `load_dynamic_parameters`

建议用于获取运行前动态信息：

- 根据 `symbols / universe_code` 展开实际标的；
- 查询 PhoenixA 中可用的数据区间；
- 为历史模式计算有效回测窗口；
- 为实时模式准备 warmup 数据区间；
- 初始化 provider 所需的动态连接信息；
- 为参数网格展开准备实际子任务列表。

### 5.4 `before_execute`

建议只做轻量准备：

- 校验 PhoenixA / 实时数据源可用性；
- 根据 `strategy_code` 取得策略类；
- 根据 `data_provider_code` 构造 adapter；
- 根据 `analyzer_profile` 构造 analyzer / observer / recorder 组合；
- 写入本次 run 的基础 metadata 到 `ctx.stats`；
- 若是实时模拟，则完成 warmup 数据预装。

### 5.5 `execute`

这是 worker 的核心阶段，需要比上一版更明确。

#### 5.5.1 历史回测执行语义

历史回测是标准 bounded run：

1. 构建 `Cerebro`；
2. 加载历史 feed；
3. 添加 strategy；
4. 配置 broker / sizer / commission；
5. 挂 analyzers / observers / recorders；
6. 执行 `cerebro.run()`；
7. 导出最终结果。

#### 5.5.2 实时模拟执行语义

实时模拟不再简单定义为“有边界的 live session”。

更准确的说法是：

- 在**策略业务语义**上，它是一个持续运行的实时模拟任务；
- 启动后会持续接入新 bar；
- 直到收到人工/调度终止信号才结束；
- 过程中持续 checkpoint、report progress、产生日志与中间指标。

因此 `execute` 在实时模拟下的职责应理解为：

1. 初始化 live adapter；
2. 用 warmup 历史 bars 预热策略状态；
3. 持续接入新 bar；
4. 每推进一批 bar，就让 backtrader 更新 strategy 状态；
5. 周期性提取 checkpoint 指标与 artifact；
6. 检查 stop signal；
7. 在停止时输出 terminal snapshot。

也就是说，**实时模拟的边界主要是手动/调度边界，而不是自动 session 边界**。

若后续仍需要“有边界实时 replay session”，可以将其视为 `realtime_test` 的一个子形态，但不是本次主目标。

#### 5.5.3 `挂 analyzers / observers` 的更详细解释

这里上一版过于简略，本版明确如下：

- **analyzers**：负责生成聚合统计，如收益、回撤、交易统计；
- **observers**：负责暴露运行中的可观测序列，如资金曲线、订单标记、持仓变化；
- **recorders**：负责把运行事件转成 Artemis 可持久化 artifact。

在 worker 里“挂载”它们的含义是：

- 依据 `analyzer_profile` 统一向 `Cerebro` 注册 analyzer / observer；
- 同时给策略或 broker 绑定自定义 recorder 钩子；
- 不允许任务调用方任意插入未知 analyzer 类。

### 5.6 `post_process`

建议将 backtrader 原始结果统一规范化成 JSON 友好结构，例如：

- `summary`
- `analyzers`
- `orders`
- `trades`
- `equity_curve`
- `positions`
- `signals`
- `diagnostics`
- `plot_manifest`
- `plot_series`

注意不建议把 backtrader 原始对象直接透传给 PhoenixA，因为：

- 不稳定；
- 不利于 API 传输；
- 不利于版本管理；
- 不利于前端/BI 消费。

### 5.7 `sink`

`sink` 负责把**已经规范化好的结果**写到 PhoenixA，职责应尽量纯：

- 写 run summary；
- 写 run artifact；
- 写 checkpoint artifact（实时模式下可选）；
- 可选写 campaign 汇总。

建议把中间 checkpoint 的持久化也放在 `sink` 语义下理解，而不是放到 `finalize`。

### 5.8 `finalize`

这里需要结合长期运行任务重新定义。

`finalize` 不适合承担“长期监督”职责，它只负责**终态收口**。

建议 `finalize` 做的事情：

- 补齐 `ctx.stats` 最终值；
- 补齐 terminal metadata，例如：
  - `stop_reason`
  - `final_bar_time`
  - `checkpoint_count`
  - `terminal_status`
- 输出最终日志；
- 父任务汇总指标；
- 确保 terminal finalize 行为只发生一次。

对于长期实时模拟任务：

- **运行中**：靠 progress / heartbeat / checkpoint；
- **终止时**：才进入 `finalize`；
- `finalize` 只处理终态，不处理中间持续上报。

---

## 6. 历史回测模式设计

### 6.1 目标

历史回测用于：

- 给定策略与参数，基于 PhoenixA 历史行情运行回测；
- 输出收益、回撤、交易次数、胜率等结果；
- 将结果记录为可查询数据。

### 6.2 推荐执行单位

第一阶段一个 child run 只处理：

- 一个策略；
- 一组参数；
- 一个 symbol；
- 一个 timeframe；
- 一个 date_range。

后续若需要组合回测，再扩展 multi-feed / portfolio 语义。

### 6.3 数据来源建议

历史模式优先使用 PhoenixA 作为 canonical source：

1. Artemis 调用 PhoenixA 获取 bars；
2. `data_provider_code` 对应 adapter 进行标准化；
3. 转为 backtrader feed；
4. 执行回测。

### 6.4 PhoenixA 读取接口建议

第一阶段优先支持：

- A 股日线历史数据。

建议 Artemis 侧收口为统一方法：

- `PhoenixAClient.get_bars(...)`

避免业务 task 直接拼底层 URL。

### 6.5 历史模式父任务 plan 维度

父任务 `plan()` 可按以下维度展开：

- `symbols`
- `strategy_code`
- `parameter_grid`
- `date_windows`
- `timeframe`
- `data_provider_code`

### 6.6 历史模式输出建议

每个 child run 至少输出：

- 元信息：`run_id`, `parent_run_id`, `strategy_code`, `symbol`, `mode`
- 资金：`start_cash`, `end_value`, `pnl`, `pnl_pct`
- 风险：`max_drawdown`, `sharpe`, `sqn`
- 交易：`trade_count`, `win_count`, `loss_count`, `win_rate`
- 运行：`bars_processed`, `duration_ms`

---

## 7. 实时模拟模式设计

### 7.1 模式定义

这里明确：

**实时模拟不是实时交易，而是对“历史上有效的策略”做实时推进验证。**

它要回答的问题是：

- 该策略在 live-like 数据到来时，行为是否仍然符合预期；
- 历史回测里的 edge，在实时推进条件下是否仍有延续性；
- 订单、信号、仓位、收益变化是否与回测逻辑一致；
- 数据接入异常、延迟、缺口是否显著影响策略表现。

### 7.2 为什么它仍然属于“测试模式”

因为它依然不包含：

- 真实券商下单；
- 订单路由与成交回报；
- 对账与恢复；
- 正式交易风控闭环。

所以它更准确地说是：

- `paper-like realtime strategy validation`

### 7.3 推荐数据接入形态

建议分两层：

#### A. Polling live bar（第一阶段推荐）

- Artemis 周期性拉取最新 bar；
- adapter 过滤重复 bar / 不完整 bar；
- 驱动 backtrader 策略状态前进。

优点：

- 复用现有 HTTP 体系；
- 实现难度低；
- 易于调试。

#### B. Streaming live bar（后续增强）

- websocket / queue 持续推送；
- adapter 把流转换成 backtrader 消费格式；
- 更接近真正 live feed。

优点是更真实，但连接管理复杂度更高。

### 7.4 运行边界与停止方式

根据 review，这里不再把实时模拟默认定义为“自动有边界 session”。

更推荐的定义是：

- 默认长期运行；
- 启动后持续运行；
- 直到人工或 cronjob 协同停止；
- 停止时写 terminal snapshot 与终止原因。

可选地，仍允许配置自动停止条件，例如：

- `market_close_cutoff`
- `max_runtime_seconds`
- `max_bars`

但这不是主路径，而是附加 stop policy。

### 7.5 实时模式建议记录的额外指标

除了历史回测常规指标，建议额外记录：

- `live_bars_received`
- `bars_dropped`
- `duplicate_bars`
- `feed_latency_ms_avg`
- `feed_gap_count`
- `signal_count`
- `order_count`
- `warmup_bars_loaded`
- `last_bar_timestamp`
- `checkpoint_count`
- `session_started_at`
- `session_ended_at`
- `stop_reason`

---

## 8. Backtrader 组件分层建议

为了避免把所有细节塞进 task unit，建议在 Artemis 内部增加轻量分层：

```text
artemis/
  backtrader/
	strategy_registry.py
	data_provider_registry.py
	analyzer_profile_registry.py
	engine_builder.py
	result_schema.py
	analyzers/
	observers/
	recorders/
	adapters/
```

### 8.1 Strategy Registry

维护：

- `strategy_code`
- 对应 `bt.Strategy` class
- 默认参数
- 参数 schema
- 支持的 mode / market / timeframe

### 8.2 Data Provider Registry

维护：

- `data_provider_code`
- 适配器类
- 支持的 market / timeframe / mode
- provider config schema
- 诊断能力标签

### 8.3 Analyzer Profile Registry

维护：

- `analyzer_profile`
- analyzers 清单
- observers 清单
- recorders 清单
- summary mapping
- persist artifact 策略
- plot 能力标记

### 8.4 Engine Builder

统一封装：

- `adddata`
- `addstrategy`
- `addanalyzer`
- `addobserver`
- `broker cash / commission / slippage`
- recorder 初始化

### 8.5 Result Normalizer

负责把运行结果统一转换为：

- summary
- analyzers
- trades
- orders
- equity_curve
- signals
- diagnostics
- plot_manifest
- plot_series

---

## 9. 结果模型与 plot 预留设计

### 9.1 总体原则

第一阶段仍然坚持两层结果模型：

1. `Run Summary`（强结构化）
2. `Run Artifact`（弱结构化 JSON）

但 artifact 类型要为 plot 预留空间。

### 9.2 第一层：Run Summary

建议字段：

| 字段 | 说明 |
|---|---|
| run_id | 本次子任务运行 ID |
| parent_run_id | 父任务 ID |
| task_code | 任务码 |
| mode | `historical` / `realtime_test` |
| strategy_code | 策略标识 |
| symbol | 标的 |
| timeframe | 周期 |
| data_provider_code | 数据提供方式 |
| analyzer_profile | 观测配置 |
| start_date | 回测/会话开始 |
| end_date | 回测/会话结束 |
| start_cash | 初始资金 |
| end_value | 结束净值 |
| pnl | 盈亏 |
| pnl_pct | 收益率 |
| max_drawdown | 最大回撤 |
| sharpe | 夏普 |
| trade_count | 交易数 |
| win_rate | 胜率 |
| checkpoint_count | checkpoint 次数 |
| status | SUCCESS / FAILED / CANCELED |
| stop_reason | 终止原因 |
| error_message | 失败原因 |
| duration_ms | 运行耗时 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### 9.3 第二层：Run Artifact

建议字段：

| 字段 | 说明 |
|---|---|
| run_id | 关联 run |
| artifact_type | artifact 类型 |
| payload_json | JSON 内容 |
| payload_version | 版本号 |
| sequence_no | 顺序号/分片号（可选） |
| checkpoint_at | checkpoint 时间（可选） |
| created_at | 创建时间 |

建议第一阶段支持的 `artifact_type`：

- `analyzers`
- `trades`
- `orders`
- `equity_curve`
- `signals`
- `diagnostics`
- `plot_manifest`
- `plot_series`
- `plot_image_ref`（预留）

### 9.4 为什么要提前设计 `plot_manifest`

因为现在虽然还不决定 plot 的最终交付方式，但无论未来走哪条路，都需要稳定的中间层：

#### 路线 A：Python 侧直接绘图

- 生成图片；
- 上传 OSS；
- `plot_image_ref` 保存引用与元信息。

#### 路线 B：保存绘图数据，由 Cthulhu 绘图

- `plot_series` 保存净值、回撤、买卖点等序列；
- `plot_manifest` 描述有哪些 series、字段含义、推荐图层；
- Cthulhu 拉取 artifact 自行渲染。

因此建议第一阶段至少做到：

- 能保存 `plot_manifest`；
- 能保存绘图所需的基础 series；
- 不把二进制图片落库作为强制目标。

### 9.5 `plot_manifest` 建议结构

示意：

```json
{
  "version": "v1",
  "charts": [
	{
	  "chart_code": "equity_overview",
	  "series": ["equity_curve", "drawdown_curve", "buy_markers", "sell_markers"],
	  "x_axis": "timestamp",
	  "notes": "for cthulhu rendering or python plotting"
	}
  ]
}
```

---

## 10. PhoenixA 持久化设计建议

### 10.1 职责划分

#### Artemis 负责

- 组装回测/实时模拟任务；
- 执行 backtrader；
- 生成标准化结果；
- 调用 PhoenixA 落库。

#### PhoenixA 负责

- 提供历史市场数据读取接口；
- 提供 run summary / artifact 写入接口；
- 提供查询接口；
- 管理数据库 schema 与一致性。

### 10.2 建议新增的数据对象

建议新增：

1. `StrategyRunSummary`
2. `StrategyRunArtifact`

如果想延续“backtest”命名也可以，但从语义上讲，`StrategyRun*` 更能同时覆盖历史回测与实时模拟。

### 10.3 PhoenixA API 建议

建议新增：

#### 写入接口

- `POST /api/v1/strategy/run/summary/upsert`
- `POST /api/v1/strategy/run/artifact/upsert`
- 可选：`POST /api/v1/strategy/run/checkpoint/upsert`

#### 查询接口

- `GET /api/v1/strategy/run/list`
- `GET /api/v1/strategy/run/{run_id}`
- `GET /api/v1/strategy/run/{run_id}/artifacts`

#### Artemis 客户端建议方法

- `save_strategy_run_summary(payload)`
- `save_strategy_run_artifacts(payload)`
- `get_strategy_market_bars(...)`

### 10.4 Campaign 是否单独落库

建议：可以有，但不是第一优先级。

因为多数 campaign 级结果可以由 child summary 聚合获得；等后续明确有批次分析需求时，再补 `campaign summary` 表即可。

---

## 11. 统一结果契约

建议无论 `mode` 是什么，都返回统一顶层结构：

```json
{
  "run_meta": {},
  "summary": {},
  "artifacts": {
	"analyzers": {},
	"trades": [],
	"orders": [],
	"equity_curve": [],
	"signals": [],
	"diagnostics": {},
	"plot_manifest": {},
	"plot_series": {}
  }
}
```

其中：

- 历史模式重点使用 `summary + analyzers + trades + equity_curve + plot_series`
- 实时模拟重点使用 `summary + orders + signals + diagnostics + equity_curve + plot_series`

---

## 12. 父任务规划策略建议

### 12.1 Parent Task 输入建议

建议支持两类输入：

#### A. 直接指定运行集合

适合手工触发：

- `symbols`
- `strategy_code`
- `strategy_params`
- `data_provider_code`
- `analyzer_profile`
- `start_date / end_date`

#### B. 指定批量展开规则

适合系统化批量运行：

- `universe_code`
- `parameter_grid`
- `date_windows`
- `symbol_limit`
- `max_children`

### 12.2 Parent Task 的 plan 输出建议

统一输出：

```json
[
  {
	"key": "BACKTRADER_RUN",
	"params": {
	  "mode": "historical",
	  "strategy_code": "sma_cross",
	  "data_provider_code": "phoenixa_hist_daily",
	  "analyzer_profile": "default_hist_v1",
	  "symbol": "600000",
	  "timeframe": "daily",
	  "start_date": "2024-01-01",
	  "end_date": "2024-12-31",
	  "strategy_params": {"fast": 10, "slow": 30}
	}
  }
]
```

### 12.3 实时模拟的 plan 建议

对于实时模拟，父任务的 plan 不一定会展开大量 child。

更推荐：

- 一个 symbol / strategy / timeframe 对应一个长期运行 child；
- 这样 stop、checkpoint、进度、诊断都更清晰；
- 不建议一个 child 同时承载过多 symbol 的长期 live 逻辑。

---

## 13. Worker Task 的推荐执行流程

单个 `BACKTRADER_RUN` 建议流程如下：

1. 校验 `mode / strategy / symbol / timeframe`；
2. 通过 registry 获取 strategy class；
3. 通过 `data_provider_code` 获取 feed adapter；
4. 通过 `analyzer_profile` 获取 analyzers / observers / recorders；
5. 获取历史数据或 warmup 数据；
6. 构建 `Cerebro`；
7. 设置 broker / sizer / commission；
8. 安装 analyzers / observers / recorders；
9. 执行历史回测或实时模拟循环；
10. 周期性生成 checkpoint（实时模式）；
11. 归一化 terminal 结果；
12. 通过 PhoenixA 落库；
13. 更新 `ctx.stats`。

---

## 14. 推荐 analyzer / observer / recorder 组合

### 14.1 默认历史 profile

- analyzers
  - `Returns`
  - `SharpeRatio_A`
  - `DrawDown`
  - `TradeAnalyzer`
  - `SQN`（可选）
- observers
  - `Broker`
  - `Trades`（视开销决定）
- recorders
  - `EquityCurveRecorder`
  - `TradeRecorder`
  - `PlotManifestRecorder`

### 14.2 默认实时模拟 profile

- analyzers
  - `Returns`
  - `DrawDown`
  - `TradeAnalyzer`
- observers
  - `Broker`
- recorders
  - `EquityCurveRecorder`
  - `OrderRecorder`
  - `SignalRecorder`
  - `LiveDiagnosticsRecorder`
  - `PlotManifestRecorder`

### 14.3 为什么要强调 recorder

因为真正会被 PhoenixA 与 Cthulhu 消费的，往往不是 backtrader 原生对象，而是 recorder 产出的业务结构化结果。

---

## 15. 配置建议（`task.yaml`）

继续复用当前 `task.yaml` 变体机制，不单独再造 backtest config 文件。

### 15.1 适合放进 `task.yaml` 的内容

- `mode + market + timeframe` 对应默认参数；
- 默认 `data_provider_code`；
- 默认 `analyzer_profile`；
- 默认 broker 参数；
- 默认 artifact 持久化策略；
- 默认 checkpoint / report 间隔；
- 默认 plot artifact 开关。

### 15.2 示例结构（设计示意）

```yaml
tasks:
  BACKTRADER_CAMPAIGN:
    variants:
      - match: { mode: "historical", market: "CN_A", timeframe: "daily" }
        config:
          data_provider_code: "phoenixa_hist_daily"
          analyzer_profile: "default_hist_v1"
          cash: 100000.0
          commission: 0.001
          persist_artifacts: ["analyzers", "trades", "equity_curve", "plot_manifest", "plot_series"]

      - match: { mode: "realtime_test", market: "CN_A", timeframe: "1m" }
        config:
          data_provider_code: "phoenixa_polling_live_1m"
          analyzer_profile: "default_live_sim_v1"
          cash: 100000.0
          commission: 0.001
          checkpoint_interval_seconds: 300
          heartbeat_interval_seconds: 60
          persist_artifacts: ["orders", "signals", "diagnostics", "equity_curve", "plot_manifest", "plot_series"]
```

### 15.3 不建议放进 `task.yaml` 的内容

- 任意 Python 类路径；
- 任意可执行代码片段；
- 任意第三方模块 import；
- 过于细碎的逐 symbol 临时实验参数。

---

## 16. 推荐请求示例

### 16.1 历史回测任务示例

```json
{
  "meta": {
	"run_id": 10001,
	"task_id": 501,
	"exec_type": "ASYNC",
	"task_code": "BACKTRADER_CAMPAIGN"
  },
  "body": {
	"mode": "historical",
	"market": "CN_A",
	"timeframe": "daily",
	"strategy_code": "sma_cross",
	"data_provider_code": "phoenixa_hist_daily",
	"analyzer_profile": "default_hist_v1",
	"symbols": ["600000", "000001"],
	"start_date": "2023-01-01",
	"end_date": "2024-12-31",
	"parameter_grid": [
	  {"fast": 10, "slow": 30},
	  {"fast": 20, "slow": 60}
	],
	"cash": 100000,
	"commission": 0.001
  }
}
```

### 16.2 实时模拟任务示例

> 这里用 `LONGRUN` 表达目标设计语义；当前代码仍只有 `SYNC / ASYNC`，对应扩展见 cronjob 配套文档。

```json
{
  "meta": {
	"run_id": 10002,
	"task_id": 502,
	"exec_type": "LONGRUN",
	"task_code": "BACKTRADER_CAMPAIGN"
  },
  "body": {
	"mode": "realtime_test",
	"market": "CN_A",
	"timeframe": "1m",
	"strategy_code": "sma_cross",
	"data_provider_code": "phoenixa_polling_live_1m",
	"analyzer_profile": "default_live_sim_v1",
	"symbols": ["600000"],
	"strategy_params": {"fast": 10, "slow": 30},
	"warmup_bars": 120,
	"checkpoint_interval_seconds": 300,
	"heartbeat_interval_seconds": 60,
	"stop_policy": {
	  "manual_stop_enabled": true,
	  "market_close_cutoff": "15:00:00"
	},
	"cash": 100000,
	"commission": 0.001
  }
}
```

---

## 17. 端到端流程建议

### 17.1 历史回测流程

```text
Cronjob / API
   -> Artemis TaskEngine
   -> BACKTRADER_CAMPAIGN (Orchestrator)
	  -> parameter_check
	  -> load_task_config
	  -> load_dynamic_parameters
	  -> plan child runs
	  -> BACKTRADER_RUN (Worker) x N
		 -> 从 PhoenixA 读取 bars
		 -> adapter 标准化 + 构建 feed
		 -> 构建 Cerebro
		 -> 执行回测
		 -> post_process 标准化结果
		 -> sink 到 PhoenixA
	  -> finalize campaign summary
```

### 17.2 实时模拟流程

```text
Cronjob / API
   -> Artemis TaskEngine / LongRun execution model
   -> BACKTRADER_CAMPAIGN
	  -> parameter_check
	  -> load_task_config
	  -> load_dynamic_parameters
	  -> plan child runs
	  -> BACKTRADER_RUN
		 -> 初始化 live adapter
		 -> warmup 历史 bars
		 -> 持续接入实时 bars
		 -> 周期性 checkpoint / progress / heartbeat
		 -> 收到 stop signal
		 -> post_process terminal snapshot
		 -> sink 到 PhoenixA
	  -> finalize
```

---

## 18. 失败处理与可观测性建议

### 18.1 失败策略

对于历史回测，继续沿用当前默认策略：

- 子任务失败 -> 父任务 fail-fast；
- 不做自动重试；
- 所有失败信息进入结构化日志。

对于实时模拟，建议额外考虑：

- 短暂数据源异常与 terminal failure 分开；
- 允许记录 `degraded diagnostics`，但是否立即失败由 stop policy 决定；
- 真正 terminal failure 时仍要输出终态 summary / diagnostics。

### 18.2 建议补充的结构化日志字段

- `mode`
- `strategy_code`
- `symbol`
- `timeframe`
- `data_provider_code`
- `analyzer_profile`
- `bars_count`
- `trade_count`
- `pnl`
- `max_drawdown`
- `artifact_types`
- `checkpoint_seq`
- `stop_reason`

### 18.3 建议写入 `ctx.stats` 的内容

建议 worker 最终写入：

- `bars_processed`
- `orders_count`
- `trades_count`
- `signals_count`
- `checkpoint_count`
- `result_summary`
- `phase_durations_ms`
- `total_duration_ms`

父任务建议写入：

- `children_total`
- `children_completed`
- `success_count`
- `failed_count`
- `campaign_mode`

---

## 19. Artemis 架构层面的考虑

这一章是本轮 review 新增的重点。

### 19.1 当前实现对 bounded task 很合适

从代码看，当前 Artemis 的执行模型非常适合：

- 一次性历史回测；
- 有明确结束边界的 worker；
- 父任务 plan 出固定 child list 的场景。

### 19.2 当前实现对长期运行任务的限制

当前限制主要有：

1. `TaskMode` 只有 `SYNC / ASYNC`；
2. `TaskEngine.run()` 的 `ASYNC` 本质上是进程内后台线程；
3. `CronjobClient` 目前主要支持 `progress` 与一次性 `finalize`；
4. `TaskStatus.CANCELED` 已预留，但还没有完整 control-plane；
5. `OrchestratorUnit.plan()` 当前默认假设 child list 是有限的。

这说明：

- 历史回测可以直接复用现有模型；
- 实时模拟的“策略执行设计”可以先写清楚；
- 但真正的长期运行交付，需要 cronjob 和 Artemis 一起补强执行契约。

### 19.3 因此建议的架构切分

建议明确分成两层：

#### Artemis Backtrader Layer

解决：

- 策略注册；
- feed adapter；
- analyzer profile；
- result schema；
- checkpoint / artifact；
- PhoenixA sink。

#### LongRun Execution Layer

解决：

- `LONGRUN` 任务类型；
- heartbeat；
- stop request；
- finalize once；
- 运行状态查询。

后者不建议塞进 backtrader worker 内部自行发明协议，而应由 cronjob / Artemis 共用任务运行模型来承接。

---

## 20. 实施顺序建议

为了降低落地风险，建议分三步走。

### Phase 1：历史回测 MVP

目标：先把“能跑、能落库、能追踪”做起来。

建议内容：

1. 定义 `BACKTRADER_CAMPAIGN` + `BACKTRADER_RUN`；
2. 只支持 `historical`；
3. 接 PhoenixA 历史 bars；
4. 引入 `strategy_code / data_provider_code / analyzer_profile` 三层注册；
5. 结果先落：
   - run summary
   - analyzers artifact
   - trades artifact
   - equity curve artifact
   - plot manifest / plot series artifact

### Phase 1 implementation checklist（Artemis / PhoenixA / Cronjob）

下面这部分作为真正开始编码前的 implementation checklist。原则上先按这个 checklist 拆任务、排期、建分支；如果 checklist 中某一项要改范围，应该先回到设计文档更新，而不是直接在代码里临时扩散。

#### 20.1 Phase 1 scope freeze

- [ ] 本阶段只支持 `historical` mode，不实现 `realtime_test`
- [ ] 一个 child run 只处理：`1 strategy + 1 symbol + 1 timeframe + 1 date_range + 1 parameter set`
- [ ] Artemis 侧只接 PhoenixA 历史 bars，不接其他数据源
- [ ] 只做 PhoenixA 持久化：`summary + artifact`
- [ ] Cronjob 只复用现有 `ASYNC` 模式，不引入 `LONGRUN`
- [ ] 不改 `BaseTaskUnit` / `WorkerUnit` / `OrchestratorUnit` 的基础生命周期语义，除非发现明确 blocker

#### 20.2 Artemis implementation checklist

##### A. 任务码、注册与目录结构

- [ ] 在 `artemis/consts/task_code.py` 增加：
  - `BACKTRADER_CAMPAIGN`
  - `BACKTRADER_RUN`
- [ ] 在 `artemis/task_units/` 下增加 backtrader 相关目录与文件，建议形态：
  - `artemis/task_units/backtrader/campaign.py`
  - `artemis/task_units/backtrader/run.py`
- [ ] 在 `config/registrations.yaml` 注册两个任务，保证 `TaskRegistry` 可以解析到对应 class
- [ ] 确认 `TaskRegistry.scan_unregistered()` 能识别新增 task unit，避免目录或命名方式不兼容

##### B. 尽量复用现有基类，不做 Phase 1 无意义改动

- [ ] `BaseTaskUnit` 保持现状，继续使用：
  - `parameter_check`
  - `merge_parameters`
  - `load_dynamic_parameters`
  - `before_execute`
  - `execute`
  - `post_process`
  - `sink`
  - `finalize`
- [ ] `WorkerUnit` 不单独扩展公共逻辑，先作为语义化基类使用
- [ ] `OrchestratorUnit` 第一阶段只复用现有：
  - `plan()`
  - 子任务串行执行
  - `children_total / children_completed` progress 上报
- [ ] 只有在历史回测 worker 真正需要时，才补最小公用 helper；不要一开始就抽象出大而全 backtrader framework

##### C. `BACKTRADER_CAMPAIGN`（父任务）

- [ ] `parameter_check` 校验：
  - `mode == historical`
  - `strategy_code` 已注册
  - `data_provider_code` 已注册
  - `analyzer_profile` 已注册
  - `symbols` 或 `universe_code` 至少有一个
  - `start_date <= end_date`
  - `parameter_grid` / `strategy_params` 结构合法
  - `max_children`、`max_symbols` 等保护阈值合法
- [ ] `load_dynamic_parameters` 负责：
  - 展开 `symbols / universe_code`
  - 调用 PhoenixA 预检查 symbol 是否存在
  - 查询历史数据可用区间（至少能判断有没有数据）
  - 计算实际 child specs 所需的 date window
- [ ] `plan()` 输出稳定的 child spec：
  - `key = BACKTRADER_RUN`
  - `params` 中明确带上 `strategy_code / symbol / timeframe / date_range / strategy_params / data_provider_code / analyzer_profile`
- [ ] `finalize` 只做 campaign 层聚合：
  - `children_total`
  - `children_completed`
  - `success_count`
  - `failed_count`
  - 不在 Phase 1 引入 campaign summary 持久化表

##### D. `BACKTRADER_RUN`（子任务）

- [ ] `parameter_check` 校验单次 run 所需字段完整
- [ ] `before_execute` 初始化：
  - strategy registry
  - data provider registry
  - analyzer profile registry
  - broker 默认参数
- [ ] `execute` 完成最小历史回测流程：
  - 从 PhoenixA 拉取 bars
  - 转换成 backtrader feed
  - 构建 `Cerebro`
  - 加载 strategy
  - 挂 analyzers / observers / recorders
  - 执行 `cerebro.run()`
- [ ] `post_process` 归一化输出：
  - `summary`
  - `analyzers`
  - `trades`
  - `equity_curve`
  - `plot_manifest`
  - `plot_series`
- [ ] `sink` 调 PhoenixA 写入：
  - run summary
  - analyzers artifact
  - trades artifact
  - equity curve artifact
  - plot manifest / plot series artifact
- [ ] `finalize` 回填 `ctx.stats`：
  - `bars_processed`
  - `trade_count`
  - `orders_count`（若可得）
  - `phase_durations_ms`
  - `total_duration_ms`
  - `result_summary`

##### E. Artemis 内部 backtrader 模块

- [ ] 增加最小目录：
  - `artemis/backtrader/strategy_registry.py`
  - `artemis/backtrader/data_provider_registry.py`
  - `artemis/backtrader/analyzer_profile_registry.py`
  - `artemis/backtrader/engine_builder.py`
  - `artemis/backtrader/result_normalizer.py`
  - `artemis/backtrader/recorders/`
- [ ] `strategy_registry` Phase 1 只注册一小批可控策略，不做任意 class path 动态加载
- [ ] `data_provider_registry` Phase 1 只提供 `phoenixa_hist_daily`
- [ ] `analyzer_profile_registry` Phase 1 只提供 `default_hist_v1`
- [ ] `engine_builder` 负责统一装配：
  - data
  - strategy
  - analyzers
  - observers
  - broker cash / commission
- [ ] `result_normalizer` 负责把 backtrader 原始对象转成稳定 dict/list，禁止 PhoenixA 直接消费原始对象

##### F. 配置文件与 runtime file 影响面

- [ ] 更新 `config/task.yaml`：
  - 增加 `BACKTRADER_CAMPAIGN` historical variant
  - 增加 `BACKTRADER_RUN` historical variant
  - 配置默认 `data_provider_code`、`analyzer_profile`、`cash`、`commission`、`persist_artifacts`
- [ ] 检查 `ConfigManager.task_variant()` 是否能满足 Phase 1 匹配规则；如果不够，只做最小增强，不做复杂 rule engine
- [ ] 若需要通过 runtime 管理接口查看/编辑 task yaml，确认 `RuntimeFileService.read_task_yaml()` / `write_task_yaml()` 不需要协议级改动
- [ ] `config/config.yaml` 中确认 `dept_services.phoenixA` 与 `dept_services.cronjob` 可用
- [ ] `config/registrations.yaml` 与 runtime tree 一致，不让任务注册来源混乱

##### G. `TaskContext` / `TaskEngine` / client 侧最小改动

- [ ] `TaskContext` Phase 1 重点复用现有能力，不为历史回测新增 long-run 字段
- [ ] 在 `ctx.stats` 中约定 backtest 常用字段，避免每个 task unit 各写各的 key
- [ ] `TaskEngine` Phase 1 继续复用 `ASYNC`，不引入 `LONGRUN`
- [ ] 确认历史回测作为顶层任务时：
  - 失败会触发 `finalize_failed`
  - 成功会触发 `finalize_success`
- [ ] 在 `PhoenixAClient` 中补充方法：
  - `get_strategy_market_bars(...)`
  - `save_strategy_run_summary(...)`
  - `save_strategy_run_artifacts(...)`
- [ ] 所有 PhoenixA client 方法都带稳定日志字段：`run_id`、`task_code`、`artifact_type`

##### H. Artemis 测试与验收

- [ ] 单测：`BACKTRADER_CAMPAIGN.plan()` 对 symbol / parameter_grid 展开正确
- [ ] 单测：`task.yaml` variant 命中逻辑符合预期
- [ ] 单测：result normalizer 输出 schema 稳定
- [ ] 单测：PhoenixA client payload 结构正确
- [ ] 集成 smoke test：mock PhoenixA 返回固定历史 bars，Artemis 能完成一次最小回测并输出 summary + artifact
- [ ] 集成 smoke test：子任务失败时父任务 fail-fast，且 cronjob finalize 为 failed

#### 20.3 PhoenixA implementation checklist

> PhoenixA 侧详细设计同时记录在 `app/projects/phoenixA/docs/DESIGN.md`，这里保留与 Artemis Phase 1 直接相关的 checklist。

##### A. 命名与边界先冻结

- [ ] 在编码前冻结命名，建议直接使用：
  - `StrategyRunSummary`
  - `StrategyRunArtifact`
- [ ] 明确 PhoenixA Phase 1 只做：
  - 历史 bars 读取
  - strategy run summary / artifact 持久化
  - run 查询接口
- [ ] 不在 Phase 1 引入 campaign summary 表
- [ ] 不在 Phase 1 引入 plot 图片存储或 OSS 上传链路

##### B. 历史 bars 读取接口

- [ ] 确认是复用现有历史数据接口，还是新增一个更适合 Artemis 的 bars query 接口
- [ ] 无论最终路由如何，返回结构要稳定支持：
  - `symbol`
  - `timestamp/trade_date`
  - `open/high/low/close`
  - `volume`（若有）
  - `amount`（若有）
- [ ] 支持 Artemis 按 `symbol + timeframe + date_range` 查询
- [ ] 支持必要的 limit / ordering 约束，避免一次读出过大数据集

##### C. strategy run 持久化

- [ ] 增加 summary 表模型：至少包含 `run_id`、`parent_run_id`、`strategy_code`、`symbol`、`mode`、`timeframe`、`pnl`、`max_drawdown`、`trade_count`、`status`
- [ ] 增加 artifact 表模型：至少包含 `run_id`、`artifact_type`、`payload_json`、`payload_version`、`created_at`
- [ ] 为 summary 表加必要索引：
  - `run_id` 唯一
  - `parent_run_id`
  - `strategy_code`
  - `symbol`
  - `created_at`
- [ ] artifact 表按 `run_id + artifact_type` 做查询优化

##### D. API / service / dao 落地

- [ ] 增加写入接口：
  - `POST /api/v1/strategy/run/summary/upsert`
  - `POST /api/v1/strategy/run/artifact/upsert`
- [ ] 增加查询接口：
  - `GET /api/v1/strategy/run/{run_id}`
  - `GET /api/v1/strategy/run/{run_id}/artifacts`
  - `GET /api/v1/strategy/run/list`
- [ ] Controller 只做参数校验与响应构造，不写业务逻辑
- [ ] Service 负责：
  - upsert 规则
  - payload 基础校验
  - artifact 类型白名单校验
- [ ] DAO 负责具体表读写，不在 DAO 写 artifact 业务含义判断

##### E. PhoenixA 验收

- [ ] Artemis 能成功读取 PhoenixA 历史 bars
- [ ] Artemis 能成功写入 1 条 summary + 多条 artifact
- [ ] PhoenixA 查询接口能完整回放该 run 的 summary + artifacts
- [ ] 非法 artifact type / 缺字段 payload 会被 PhoenixA 拒绝，并返回可诊断错误

#### 20.4 Cronjob implementation checklist

> Cronjob Phase 1 仍然是 bounded historical backtest integration，不是 long-run 改造。long-run 设计继续以 `app/projects/cronjob/docs/2026-04-01 FEATURE_EXTEND_RUNNING_STRATEGY.md` 为准。

##### A. 执行模型

- [ ] Phase 1 明确只使用现有 `ASYNC` 执行类型
- [ ] 不在 Phase 1 引入 `LONGRUN`、heartbeat、stop control
- [ ] Cronjob 对历史回测的预期语义仍然是：
  - 创建 run
  - 接收 progress
  - 接收最终 success / failed callback

##### B. 任务定义与触发

- [ ] 增加或配置可触发 `BACKTRADER_CAMPAIGN` 的任务定义
- [ ] 任务请求体能传递：
  - `mode = historical`
  - `strategy_code`
  - `symbols` / `universe_code`
  - `date_range`
  - `parameter_grid`
- [ ] 若 Cronjob 侧已有 task schema 校验，需要同步补齐这些字段

##### C. 运行态展示与回调

- [ ] progress 继续复用当前 `children_completed / children_total` 语义
- [ ] finalize success / failed 不改协议，只校验能正确显示历史回测任务结果
- [ ] 若 Cronjob UI / API 有任务类型展示，补充 `BACKTRADER_CAMPAIGN` 可读名称
- [ ] 若 Cronjob 有运行详情页，建议显示 Artemis 返回的 `ctx.stats` 摘要字段

##### D. Cronjob 验收

- [ ] Cronjob 能成功发起一个历史回测 `ASYNC` run
- [ ] 能看到父任务 progress 递增
- [ ] 成功场景下收到 finalize success
- [ ] 失败场景下收到 finalize failed
- [ ] 不因为回测任务耗时略长就误判为失联任务

#### 20.5 Cross-service 联调 checklist

- [ ] PhoenixA 先准备一小份稳定历史样本数据，作为联调基线
- [ ] Artemis 用同一份样本数据跑固定策略，确保结果可重复
- [ ] Cronjob 发起同一任务 2~3 次，确认 run_id、summary、artifact、callback 行为稳定
- [ ] 人工抽查一条 run：
  - Cronjob 中能看到 run 完成
  - PhoenixA 中能查到 summary
  - PhoenixA 中能查到 analyzers / trades / equity_curve / plot artifacts
- [ ] 失败链路联调至少覆盖：
  - PhoenixA bars 读取失败
  - strategy_code 未注册
  - PhoenixA 写 summary / artifact 失败
  - 子任务失败导致父任务 fail-fast

### Phase 2：实时模拟 MVP

建议内容：

1. 增加 `realtime_test` mode；
2. 先支持 polling bar provider；
3. 增加 live diagnostics recorder；
4. 增加 checkpoint artifact；
5. 结果落库与历史模式复用统一 schema。

### Phase 3：长期运行任务扩展 + 增强能力

建议内容：

1. 与 cronjob 一起扩展 `LONGRUN` 语义；
2. 增加 heartbeat / stop / control-plane；
3. 增加 streaming feed adapter；
4. 更丰富的 analyzer profile；
5. 多 symbol 组合回测；
6. 可选 plot image 生成与外部存储引用。

---

## 21. 不过度设计的落地建议

如果希望第一轮尽快成功，我建议有意识地克制。

### 第一阶段先坚持做这几件事

- 一个 orchestrator；
- 一个 worker；
- 先把历史回测打通；
- 引入三层注册表：strategy / provider / analyzer profile；
- 一个 PhoenixA 历史数据适配器；
- 一个 PhoenixA 结果写入适配器；
- summary + artifact 两层结果模型；
- plot manifest / plot series 预留。

### 第一阶段先不要做这几件事

- 任意策略热加载；
- 多市场多频率一次性全覆盖；
- 大规模参数优化；
- 复杂 portfolio engine；
- 完整 websocket/queue live infra；
- 完整 plotting 上传链路；
- 大量明细表范式拆分。

---

## 22. 结论

综合当前 Artemis 代码现状、你的 review 反馈以及 backtrader 的特点，主方案建议为：

- **Artemis 继续作为任务编排层；**
- **Backtrader 作为单次策略运行引擎接入；**
- **父任务负责 campaign 规划，子任务负责单次 run；**
- **历史回测与实时模拟共用一套 worker 骨架，通过 `mode` 区分；**
- **通过 `strategy_code / data_provider_code / analyzer_profile` 三层注册，收住 backtrader 灵活性；**
- **PhoenixA 同时承担历史数据来源与结果持久化出口；**
- **结果模型先采用“summary + artifact”两层结构，并为 plot 预留 artifact 能力；**
- **长期运行任务的调度/终止/heartbeat 由 cronjob 配套扩展方案承接。**

这个方案既能充分利用已有的 task orchestration design，也能给 backtrader 留出足够灵活空间，同时把复杂度控制在可落地范围内。

---

## 23. 下一步建议

如果这版设计通过，建议下一步按下面顺序推进：

1. 先定任务码、目录结构、三层 registry、result schema；
2. 再补 Artemis 侧 backtrader orchestrator / worker；
3. 再补 PhoenixA 的 run summary / artifact API 与表结构；
4. 并行推进 cronjob 长期运行模型设计；
5. 最后补最小可运行样例与测试用例。
