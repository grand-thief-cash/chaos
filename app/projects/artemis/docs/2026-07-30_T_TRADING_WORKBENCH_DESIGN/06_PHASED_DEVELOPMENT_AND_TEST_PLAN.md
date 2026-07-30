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
- mean-reversion candidate/confirmation state machine；
- next-bar execution、成本、配对和 MAE/MFE；
- replay service；
- batch aggregator；
- config/replay/batch API。
- `persistence_mode=ephemeral` 默认值与未实现模式 fail-closed 校验；

测试：

- 前缀一致性/未来数据扰动测试；
- decision 与 fill 时间关系；
- buy_first/sell_first；
- 成本、最低佣金、印花税和滑点；
- paired/unpaired；
- no-signal、warmup、部分失败；
- FastAPI contract tests。
- ephemeral 路径不调用任何结果 sink 的测试。

退出标准：使用固定分钟 bars 可以稳定产生可解释结果和批量报告。

## Phase 4：Cthulhu 页面

实现：

- TypeScript models 和 WorkbenchApiService；
- `/workbench/t-trading` route；
- 参数、日期导航、分钟图、markers；
- 统计卡片和 signal/fill/trade 明细；
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

- min1 历史 K 线；
- 历史 Level-1 snapshot；
- spread、queue imbalance、microprice 和交易阶段；
- Level1TouchExecution；
- 与 min5 基线做增量价值比较。

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
