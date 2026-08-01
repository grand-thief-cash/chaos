# 06. 分阶段开发与测试计划

## Phase 0：设计与契约冻结

交付：

- 本文档集；
- period、timestamp、adjust、signal/fill、API 和报告契约；
- 第一轮范围与延后项。

退出标准：评审确认不把实时交易、ML 和结果持久化混入 MVP。

## Phase 1：PhoenixA 分钟 bars

实现：

- period canonicalization 与 intraday 判断；
- `bars_stock_zh_a_min5_nf` migration；
- generic bars upsert/query/last-update 保留 intraday timestamp；
- 分钟查询不调用日线日期截断；
- DAO 返回完整 watermark；
- Go 单测覆盖 timestamp、period alias 和路由。

测试：

- model/helper unit tests；
- controller request/response tests；
- DAO/table name tests；
- migration `up/down` 或 development DB smoke test。

退出标准：同一 symbol 同日多根 bar 能幂等写入并完整查询。

## Phase 2：Artemis 分钟下载

实现：

- 新 TaskCode、任务注册和 `task.yaml` min5/nf variant；
- parent 解析证券集合、watermark 和重叠下载日期；
- child 使用分钟 fields，解析 17 位时间，验证并 upsert；
- PhoenixAClient period canonicalization；
- Workbench/Phoenix provider 对分钟时间范围兼容；
- Arrow cache period 与 timestamp 修复，或 replay 显式禁用不安全缓存。

测试：

- BaoStock timestamp parser；
- minute fields 与日线 fields 隔离；
- parent incremental planning；
- child reject/normalize/sink；
- fake PhoenixA contract tests。

退出标准：固定样本和小量真实 BaoStock 数据均可进入 PhoenixA。

## Phase 3：信号、回放和报告

实现：

- TTrading Pydantic/领域模型；
- causal feature engine；
- mean-reversion、MACD 量价、VWAP/Bollinger 和 opening-range 状态机；
- 独立 forward event evaluator（多 horizon、MFE/MAE、first-touch）；
- next-bar execution 保留为默认关闭的可选诊断；
- replay service；
- batch aggregator；
- config/replay/batch API。
- `persistence_mode=ephemeral` 默认值与未实现模式 fail-closed 校验；

测试：

- 前缀一致性/未来数据扰动测试；
- signal engine 与 future evaluator 模块隔离；
- BUY/SELL 方向收益对称、horizon 完整性和同 bar ambiguity；
- buy_first/sell_first；
- 成本、最低佣金、印花税和滑点；
- paired/unpaired；
- no-signal、warmup、部分失败；
- FastAPI contract tests。
- ephemeral 路径不调用任何结果 sink 的测试。

退出标准：使用固定分钟 bars 可以稳定产生多策略可解释信号、多个 horizon outcome 和批量信号效果报告。

## Phase 4：Cthulhu 页面

实现：

- TypeScript models 和 WorkbenchApiService；
- `/workbench/t-trading` route；
- 参数、日期导航、分钟图、markers；
- 方向正确率、方向收益、MFE/MAE 卡片和 signal/outcome 明细；
- 批量表单和报告展示。

测试：

- TypeScript compile；
- route/service/component unit tests（项目测试设施允许时）；
- 空数据、无信号、API error 和 partial failure UI；
- 手工浏览器 smoke test（环境允许时）。

退出标准：用户可从选择证券日期到查看信号、成交和统计完成一次操作。

## Phase 5：最小全链路验证

数据规模：一只股票 1–3 个交易日，避免全市场下载。

步骤：

1. 使用替代端口启动 development PhoenixA；
2. 执行 migration；
3. 运行分钟下载 child 或固定样本 upsert；
4. 查询 PhoenixA 确认时间戳与 bar 数；
5. 使用替代端口启动 Artemis；
6. 调用 replay；
7. 调用 batch；
8. 启动/构建 Cthulhu，确认页面契约；
9. 保存命令、端口、输入和结果摘要。

如果本机数据库或 AmazingData 与 Atlas 测试冲突，使用独立端口、独立 schema/测试数据库；不得停止或重启其他任务进程。

## Phase 6：发布与 CHANGELOG

- Artemis CHANGELOG：任务、引擎、API、因果保证和测试；
- PhoenixA CHANGELOG：migration、分钟 timestamp 和 API；
- Cthulhu CHANGELOG：页面、图表和报告；
- `git diff --check`；
- 相关测试结果清单；
- 已知限制与下一 Phase 建议。

## 迭代优化路线

### Phase 7：基线误差分析

建立失败分类：

- 强趋势中逆势候选；
- 候选正确但确认过晚；
- 出场过早/过晚；
- 毛利被成本吞噬；
- 流动性或涨跌停不可成交；
- 源数据缺口/时间错位。

每次只修改对应模块，并在冻结样本外区间比较。

### Phase 8：AmazingData 与 Level-1

- 已完成：基于 `security_registry` 的个股/指数 `min1/min5/min30/daily` 按需增量 K 线任务；
- 已完成：PhoenixA 个股 `min1/min30`、指数 `min1/min5` 物理表 migration；
- 已完成：同分钟历史量比、宽基市场残差、多周期顺势回踩策略和按需上下文读取；
- 已完成：单日/批量多策略请求、`by_strategy` 汇总和 Cthulhu 多选分色；
- 明确不做：行业残差，原因是行业指数分钟 K 线能力未在供应商 API 中明确；
- 待完成：真实 AmazingData 账号上的历史 Level-1 snapshot/竞价阶段权限探测；
- spread、queue imbalance、microprice 和交易阶段；
- OFI、queue imbalance、microprice 买卖点策略；
- 与 min5 基线做样本外增量价值比较。

### Phase 8A：实时轻存储信号链路

- 已完成：统一 `RealtimeQuoteAdapter` 协议、`SinaRealtimeQuoteAdapter` GB18030/五档解析和真实响应离线契约测试；
- 已完成：`QuotePoint`、五档结构和直接消费报价点的在线 compact outcome tracker；
- 待完成：Tencent/Eastmoney QuotePoint adapter；
- source time/observed time、延迟、重复、乱序和 stale 管理；
- point-native feature/signal runtime：每个有效 QuotePoint 更新状态，不合成 OHLC bar；
- 为历史候选策略设计显式、独立版本的实时 point-native 对应策略，并分别评估；
- signal sink 只保存信号、策略/配置 checksum 和特征快照；
- active outcome tracker 在线更新 1/3/5/15 分钟 MFE/MAE/first-touch；
- compact state checkpoint 与崩溃 incomplete 语义；
- 收盘权威分钟线投射，不覆盖实时 signal time/price；
- 新浪/腾讯/东财数据授权、频率限制、字段漂移和稳定性评审。

### Phase 9：机器学习候选过滤

- label pipeline；
- walk-forward/purge/embargo；
- LightGBM/Logistic baseline；
- calibration、precision-coverage、champion/challenger；
- 模型版本和 feature checksum。

### Phase 10：实时影子验证

- AmazingData realtime subscription；
- 幂等 session start/stop；
- warmup、duplicate/gap/latency 监控；
- 所有 input/signal/fill expectation 留痕；
- 收盘 finalize report；
- 不下真实订单。

## 发布门槛

历史进入实时影子前至少满足：

- 数据完整性和时间语义通过交叉源抽样；
- 样本外扣费后正期望不是由少数日期贡献；
- 多只股票、多个市场状态下方向一致；
- 提高 confidence threshold 时 precision 总体单调改善；
- 参数扰动和成本/滑点压力测试不过度敏感；
- 所有尝试次数、失败实验和模型版本可追踪。

实时影子进入任何真实交易集成前需要单独安全、合规、风控和券商执行设计，不属于本文档范围。
