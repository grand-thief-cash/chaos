# 01. 需求与边界

## 1. 业务场景

用户选择一个 `security_id` 和起始交易日。系统按交易日推进，每页展示：

- 当前日期之前的日线背景，不展示未来交易日；
- 当前交易日的分钟 K 线；
- 当时可识别的 BUY/SELL 决策点；
- 下一根可成交 bar 上的模拟成交点；
- 置信度、触发原因、关键指标快照；
- 当日交易配对、收益、MAE/MFE 和信号质量统计；
- 上一个/下一个交易日快捷导航。

批量模式对一个或多个股票、一个日期区间执行同样的逐根回放，生成可按股票、月份、时段和市场状态切片的报告。

## 2. 术语

| 术语 | 定义 |
|---|---|
| observation time | 行情事件在交易所发生的时间 |
| bar start/end | K 线覆盖区间的起止时间 |
| available at | 该 bar 已完整、策略允许读取的时间 |
| decision time | 策略根据截至 `available_at` 的数据作出决策的时间 |
| fill time | 模拟成交发生的时间，必须不早于 decision time |
| oracle point | 使用未来数据得到的事后参考高低点，只用于评估 |
| signal point | 策略在当时产生的决策点 |
| fill point | 应用成交模型后的成交点 |
| round trip | 一对方向相反、数量可匹配的成交 |
| replay | 严格按时间顺序逐 bar 驱动相同策略状态机 |

## 3. 因果性规则

在 bar `i` 上作决策时只能读取：

```text
bars[0..i]
daily_context <= current trading day
events.available_at <= decision_time
model/trading configuration frozen before the run
```

不得读取：

- bar `i+1` 的开高低收；
- 当前日最终最高/最低、最终成交量；
- 未来复权因子和未来公告；
- 使用完整样本拟合后再回填到历史的标准化参数；
- 未来股票池成员或当前仍上市股票构成的历史 universe。

训练标签可以使用未来窗口，但必须由独立 label pipeline 生成，且不能被 feature pipeline 读取。

## 4. 信号与成交分离

第一轮使用 bar-close 决策和 next-bar-open 成交：

```text
09:35 bar 完整
    -> 计算特征和 BUY 决策
    -> 09:40 bar open 模拟成交
```

API 和 UI 必须同时返回/显示 decision 与 fill，禁止用决策 bar 的 close 冒充成交价。最后一根 bar 上产生但没有下一根可成交 bar 的信号应标记为 `unfilled`。

## 5. 第一轮功能需求

### 5.1 数据

- 下载指定股票或股票集合的 BaoStock 5 分钟 K 线；
- 分钟字段为 `date,time,open,high,low,close,volume,amount,adjustflag`；
- 组合日期和时间为带 `Asia/Shanghai` 偏移的时间戳；
- 以 `security_id` 作为 API 身份，以 symbol 作为 PhoenixA 物理 bars 键；
- 支持按交易日范围分页查询；
- 数据质量失败应显式拒绝，不得用 0 填充无效 OHLC。

### 5.2 单日回放

- 输入 `security_id/trade_date/period/strategy_config`；
- 返回 bars、features 摘要、signals、fills、trade pairs 和 daily summary；
- 支持 `buy_first` 和 `sell_first` 方向；
- 支持最大往返次数、确认窗口、最小毛利阈值和成本配置；
- 无交易机会时返回成功且 `signals=[]`。

### 5.3 批量报告

- 输入多个 security_id 和日期区间；
- 对每个证券、每个交易日复用单日回放；
- 返回 overall、by_security、by_day 和 failure 列表；
- 单个证券/交易日失败不应抹掉其他成功结果；
- 报告记录策略配置、数据周期和生成时间。

### 5.4 结果持久化策略

回测结果和分钟行情采用不同的持久化策略：

- 分钟行情是共享基础数据，写入 PhoenixA；
- 单日 replay 默认 `persistence_mode=ephemeral`，只返回前端，不保存 run、signals、fills、trades 或 bars 副本；
- 批量报告默认也为 ephemeral，只在当前响应中保留聚合与逐日摘要；
- `summary_only` 预留为只保存 run 配置和聚合摘要；
- `full` 预留为保存完整 artifact，第一轮不实现；
- 非 ephemeral 模式在后端尚未实现时必须返回明确的 422，不得悄悄降级或落库。

前端默认值固定为 ephemeral，并明确标注“仅本次查看，刷新后结果消失”。

### 5.5 前端

- 做 T 页面位于 Artemis Workbench；
- 复用 security_id、日期和 period 选择方式；
- K 线保留完整分钟时间，不得截断成日期；
- BUY/SELL decision 与 fill 使用不同图例；
- 提供前后交易日导航；第一轮若没有独立交易日历 API，可跳过周末并在无数据时继续提示；
- 展示当日和批量统计。
- 提供结果保存方式配置；第一轮只启用“不保存（推荐）”。

## 6. 非功能需求

- 可复现：同一 data/model/config 产生相同结果；
- 可解释：每个信号包含 reason codes 和关键特征；
- 可测试：核心算法不依赖 FastAPI、数据库或全局单例；
- 可扩展：数据源、信号策略、成交模型和报告聚合均使用独立接口；
- 失败关闭：身份、时间、OHLC 或配置非法时拒绝运行；
- 分页安全：分钟数据不能被 PhoenixA 默认 5000 行限制静默截断；
- 并发安全：不修改全局策略状态，单次 replay 状态只属于该请求。

## 7. 第一轮验收标准

1. 一只股票一天的分钟 bars 能从下载任务写入 PhoenixA 并查询回来；
2. 时间戳不被截断，顺序、去重和日内切片正确；
3. replay 每根 bar 只读取当前及历史数据；
4. decision 和 fill 至少相隔一个可成交步骤；
5. 单日 API 返回图表和统计所需完整契约；
6. 批量 API 能汇总多日结果并保留失败明细；
7. Cthulhu 能展示 K 线、信号、成交和统计并翻页；
8. Python、Go 测试与前端类型检查通过；
9. 使用少量真实或固定样本完成一次端到端验证。
