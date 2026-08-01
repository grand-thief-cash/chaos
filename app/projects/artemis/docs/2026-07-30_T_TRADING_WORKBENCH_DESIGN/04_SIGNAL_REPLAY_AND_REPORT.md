# 04. 买卖点策略、信号回放与效果评估

## 1. 目标重新定义：先评估买卖点，不先评估成交

本阶段要回答的核心问题不是“某套成交假设赚了多少钱”，而是：

- BUY 信号产生后，5/15/30/60 分钟分别上涨或下跌多少；
- SELL 信号产生后，5/15/30/60 分钟分别下跌或上涨多少；
- 在每个观察窗口内，最大顺向空间（MFE）和最大逆向波动（MAE）是多少；
- 目标收益与风险阈值谁先触达；
- 哪类信号、哪个时段、哪种市场状态下更有效；
- 提高 `confidence` 阈值后，信号准确度是否提高、覆盖率损失多少。

成交价、费用、滑点、持仓配对和止盈止损属于下一层问题。过早引入这些假设会把“信号是否有预测力”和“执行方式是否合理”混在一起。因此：

```text
primary evaluation = forward_event_study_v1
execution_simulation_default = false
```

成交模拟代码暂时保留为显式 opt-in 的诊断工具，不参与默认策略排名，也不进入默认批量汇总指标。

## 2. 研究依据与边界

### 2.1 研究结论

本轮检索得到的可操作结论如下：

1. 不能假设 MACD、均线、Bollinger 或突破规则天然有效。中国市场的技术规则研究有正反两类结果；对数据窥探和交易成本校正后，优势经常显著减弱。因此策略名只代表可复现实验假设，不代表已验证 alpha。
2. 日内信号存在明显的市场状态依赖。开盘区间突破更偏趋势/高量能状态，VWAP/Bollinger 反转更偏区间/过度反应状态，不能把二者混成一套无条件规则。
3. 原始成交量不是最短周期上最直接的供需信息。order-flow imbalance、盘口队列不平衡和 micro-price 在论文中对短期价格变化具有更直接的解释或预测作用；分钟 OHLCV 策略应视为可交付基线，不是数据终点。
4. 日内成交量和波动率有强烈时段季节性。当前 bar 的量不能只和“同一天此前若干 bar”比较；成熟版本应使用过去交易日相同分钟的 time-of-day 基线。
5. 买卖点应先做事件研究：固定多个 horizon，报告方向收益、MFE、MAE 和 first-touch。只看胜率会忽略盈亏幅度，只看 PnL 又会混入执行假设。

### 2.2 主要参考

- Gao et al., *Market Intraday Momentum*, Journal of Financial Economics：开盘半小时收益对收盘半小时收益存在预测关系，且在高波动、高成交量时更强。[论文信息与 DOI](https://www.researchwithrutgers.org/en/publications/market-intraday-momentum/)
- Cont, Kukanov and Stoikov, *The Price Impact of Order Book Events*：短时间价格变化与 order-flow imbalance 的关系比原始成交量更稳健。[arXiv](https://arxiv.org/abs/1011.6402)
- Gould and Bonart, *Queue Imbalance as a One-Tick-Ahead Price Predictor*：队列不平衡对下一次 mid-price 方向有显著预测力，尤其适用于 large-tick 股票。[arXiv](https://arxiv.org/abs/1512.03492)
- Stoikov, *The Micro-Price: A High Frequency Estimator of Future Prices*：结合 spread 与 imbalance 的 micro-price 对短期价格优于 mid-price/weighted mid-price。[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694)
- Zhu et al., *Profitability of Simple Technical Trading Rules of Chinese Stock Exchange Indexes*：移动平均与区间突破在计入成本和 data snooping 后优势可能消失。[arXiv](https://arxiv.org/abs/1504.04254)
- Balsara, Chen and Zheng, *The Chinese Stock Market: an Examination of the Random Walk Model and Technical Trading Rules*：在其样本中，均线、通道和 Bollinger 的反向规则对部分个股在计费后仍有正收益。[Indiana University ScholarWorks](https://scholarworks.indianapolis.iu.edu/items/c0ab8d68-2985-43ac-9387-4e4d20131dcd)
- Chen et al., *Assessing the Profitability of Timely Opening Range Breakout on Index Futures Markets*：使用 1 分钟数据研究不同市场的开盘区间突破，最佳 probing time 存在市场差异。[DOAJ/IEEE Access](https://doaj.org/article/3976caa87d1c48e4837a4f5d606b54a2)
- Marshall, Nguyen and Visaltanachoti, *A Note on Intraday Event Studies*：讨论日内事件研究统计量的设定与检验能力。[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3015618)
- Sullivan, Timmermann and White, *Data Snooping, Technical Trading Rule Performance, and the Bootstrap*：大量规则中挑选“最好规则”必须校正数据窥探偏差。[LSE](https://researchonline.lse.ac.uk/119144/)

这些研究来自不同市场、时期和数据结构，只用于形成待验证假设。任何论文结果都不能直接外推为 A 股单股 5 分钟做 T 的有效性证明。

## 3. 已实现的 OHLCV 与跨周期策略

所有实现只读取截至当前 decision bar 的数据，可在 `min1/min5` 上运行。策略由单个 `strategy` 或多选 `strategies[]` 指定：

```text
strategy:
  causal_mean_reversion_v1
  macd_volume_momentum_v1
  vwap_bollinger_reversion_v1
  opening_range_breakout_v1
  time_of_day_volume_momentum_v1
  market_residual_reversal_v1
  multi_timeframe_pullback_v1
```

选择。默认仍为 `causal_mean_reversion_v1`，保证旧请求兼容。

### 3.1 公共因果特征

```text
return_1
rolling_mean / rolling_std / zscore
rsi
session_vwap / vwap_deviation
range_position
volume_ratio
ema_fast / ema_slow / ema_fast_slope
macd / macd_signal / macd_hist / previous_macd_hist
atr / trend_strength_atr
body_ratio / lower_wick_ratio / upper_wick_ratio
opening_range_high / opening_range_low / opening_range_position
relative_volume_tod / volume_tod_history_days
benchmark_return / rolling_market_beta
market_residual_return / market_residual_zscore
daily_trend / higher_timeframe_trend / pullback_distance_atr
```

禁止 centered rolling、`shift(-n)`、当前日最终高低/成交量和全样本标准化。

`volume_ratio` 仍是“当前成交量 / trailing volume median”，用于四个单日 OHLCV 基线。跨日策略已另行实现：

```text
relative_volume_tod =
current cumulative/bar volume
/
median volume of the same minute over previous N trading days
```

其历史样本只允许使用目标交易日之前的数据；目标日 bar 不得回填同一分钟基线。

### 3.2 `causal_mean_reversion_v1`

定位：最小可解释反转基线。

BUY 候选：

```text
zscore <= -entry_z
AND rsi <= entry_rsi
AND close <= session_vwap
```

在 `confirmation_bars` 内出现价格转强、阳线和 RSI 回升后确认。SELL 对称。该策略容易在单边趋势中连续抄底/摸顶，因此只作为对照组。

### 3.3 `macd_volume_momentum_v1`

定位：实现用户提出的“MACD + 成交量 + 分钟均线”，但避免只在滞后的传统金叉时入场。

BUY 候选：

```text
macd_hist > previous_macd_hist
AND close >= ema_fast * 0.998
AND ema_fast >= ema_slow
AND volume_ratio >= min_volume_ratio
```

随后要求价格方向、K 线实体和 RSI 同向确认。SELL 对称。离场候选使用 MACD histogram 动能衰减、价格相对 EMA 的位置和价格反转。

这里使用 histogram 改善而非强制 `EMA_fast > EMA_slow`，目的是把候选点提前到负动能收缩阶段；严格均线多头排列通常明显滞后。`0.998/1.002` 是 V1 的“靠近快线”容差，必须在 walk-forward 中做扰动检验，不能在同一回测集上挑最优值。

### 3.4 `vwap_bollinger_reversion_v1`

定位：寻找过度偏离后的拒绝点，不在强趋势中无条件逆势。

BUY 候选：

```text
zscore <= -bollinger_z
AND rsi <= entry_rsi
AND close < session_vwap
AND lower_wick_ratio >= reversal_wick_ratio
AND volume_ratio >= min_volume_ratio
AND trend_strength_atr <= max_trend_strength_atr
```

SELL 对称。候选后仍需价格和 RSI 确认。`trend_strength_atr` 用快慢 EMA 距离除以 ATR，作为这个单日基线自己的趋势过滤；跨市场和跨周期信息由下述独立策略使用，不混入本策略。

### 3.5 `opening_range_breakout_v1`

定位：在开盘价格发现完成后寻找放量趋势启动点。

前 `opening_range_bars` 根 bar 只建立区间，不发 breakout 信号。之后 BUY 候选：

```text
close >= opening_range_high + breakout_atr_buffer * ATR
AND volume_ratio >= min_volume_ratio
AND close >= session_vwap
AND ema_fast >= ema_slow
AND body_ratio >= 0.5
```

SELL 对称。退出候选使用价格仍在突破区间外、MACD histogram 转弱和价格反转。开盘区间长度在不同市场与波动状态下差异很大，默认 6 根 5 分钟 bar 只是实验起点。

### 3.6 `time_of_day_volume_momentum_v1`

定位：把“异常放量”从同日 trailing volume 改为过去交易日的相同分钟基线。

BUY 候选：

```text
volume_tod_history_days >= min_time_of_day_history_days
AND relative_volume_tod >= relative_volume_tod_threshold
AND macd_hist > previous_macd_hist
AND close >= ema_fast
```

SELL 对称。默认至少要求 20 个历史交易日。回放服务按需读取目标日前最多约 70 个自然日的同周期个股 bars，同分钟成交量中位数作为 point-in-time 基线；缺失历史时特征为 NULL 并且不发信号。

### 3.7 `market_residual_reversal_v1`

定位：只做“个股相对宽基市场”的短期残差反转，不做行业残差。

同步个股与用户提供的 `benchmark_security_id` 分钟收益，在滚动窗口估计：

```text
beta = cov(stock_return, benchmark_return) / var(benchmark_return)
residual = stock_return - beta * benchmark_return
residual_z = rolling_zscore(residual)
```

BUY 候选为 `residual_z <= -residual_z_threshold`，SELL 候选对称；残差回到 0 附近作为反向候选。基准必须是已经登记在 `security_registry` 的宽基指数，且对应 `min1/min5` 指数 bars 已按需下载。

**明确排除行业残差：** AmazingData 文档只明确给出行业指数日行情，没有明确的行业指数分钟 K 线。同步频率不满足，因此当前 API 不暴露行业残差策略，也不以日线行业指数冒充分钟上下文。

### 3.8 `multi_timeframe_pullback_v1`

定位：只在更高周期方向一致时寻找分钟级回踩后的再启动。

BUY 候选：

```text
prior daily trend > 0
AND completed 30-minute trend > 0
AND distance(close, nearest EMA/VWAP) / ATR <= pullback_tolerance_atr
AND macd_hist > previous_macd_hist
```

SELL 对称。日线只取目标日前已完成的数据；30 分钟上下文按 completed bar 的 `available_at` as-of 合并，禁止把尚未完成的 30 分钟 K 线提前给 1/5 分钟信号。

### 3.9 信号状态

当前仍保留 `buy_first/sell_first` 和交替状态机，用于表达做 T 的方向语义：

- `buy_first`：先寻找 BUY 点，再寻找 SELL 点；
- `sell_first`：先寻找 SELL 点，再寻找 BUY 点。

这不是成交配对。每个信号都独立做前瞻事件评估。后续应增加 `independent_events` 研究模式，让 BUY/SELL 候选各自去重后独立评估，以免交替状态机抑制有效但未配对的候选点。

## 4. 策略落地状态与后续数据

| 策略假设 | 主要买点 | 需要的数据 | 当前状态 |
|---|---|---|---|
| time-of-day relative volume | 同分钟历史基线上的异常放量 + 价格确认 | 至少 20 日相同分钟 bars | **已实现** |
| 宽基市场残差反转 | 个股相对宽基的异常残差后反转 | 个股和宽基同步分钟线；滚动 beta | **已实现** |
| 行业残差反转 | 个股相对行业的异常残差后反转 | 行业指数同步分钟线 | **暂不实现：供应商只明确行业日线** |
| 多周期顺势回踩 | 日线/30 分钟同向状态中，1/5 分钟回踩 VWAP/EMA 后再启动 | point-in-time 日线与 30 分钟线 | **已实现** |
| opening gap continuation/fade | 相对昨收跳空后，区间突破或回补失败 | 昨收、当日集合竞价、开盘量、公司事件 | 第二阶段 |
| OFI/队列不平衡 | bid 需求增强、ask 供给减弱，micro-price 上移 | Level-1/Level-2 bid/ask price/size 更新 | 高价值数据升级 |
| 主动买卖流/CVD | 主动买量占优后回踩不破 | 逐笔成交、aggressor side 或可推断成交方向 | 高价值数据升级 |
| micro-price 偏离 | micro-price 高于 mid/last 且 spread/深度可接受 | 最优盘口或多档盘口 | 高价值数据升级 |
| 集合竞价不平衡 | 开盘前订单不平衡与撤单结构 | 竞价快照/委托数据 | 数据可得性待确认 |
| 事件/新闻条件化 | 利好/利空事件后的趋势或过度反应 | point-in-time 公告、新闻与发布时间 | 不进入首轮实时 |

数据优先级：

1. 历史 1 分钟 OHLCV + 20 日同分钟量能基线；
2. 宽基指数同步 1 分钟线；行业分钟线在供应商能力明确前不列入依赖；
3. 5 秒实时快照中的 bid/ask、size、累计量额；
4. 逐笔成交和多档盘口；
5. 独立竞价快照、公告和新闻。

AmazingData 的分钟 K 线说明只能证明开盘集合竞价成交量被计入第一根 K 线、收盘集合竞价成交量被计入最后一根 K 线，不能从聚合 K 线中单独还原竞价价格、挂单不平衡或撤单结构。历史 Snapshot API 虽有交易阶段和五档字段，是否能返回完整竞价阶段数据仍取决于实际权限与样本验证。

分钟周期从 5 分钟降到 1 分钟主要改善时间定位；真正提高短周期买点质量的更大增量通常来自盘口供需，而不是继续叠加价格指标。

## 5. 前瞻事件评估

### 5.1 与信号引擎隔离

`signal_evaluation.py` 可以读取未来窗口，`signal_engine.py` 不得 import 它。标签/评估模块只能在所有信号冻结后运行：

```text
bars[0..i] -> signal at i
freeze signal
bars[i+1..i+h] -> outcome evaluation
```

### 5.2 默认 horizons

默认 horizon 随周期切换：

```text
min1: horizons_bars = [1, 3, 5, 15], primary = 5
min5: horizons_bars = [1, 3, 6, 12], primary = 6
```

分别对应 1/3/5/15 分钟和 5/15/30/60 分钟。最后若干根 bar 无法覆盖完整 horizon 时标记 `insufficient_future_bars`，不得缩短窗口后冒充完整样本。

### 5.3 指标定义

令：

```text
s = +1 for BUY, -1 for SELL
P = decision_price
```

方向收益：

```text
directional_return_h = s * (close[i+h] / P - 1)
```

BUY：

```text
MFE_h = max(0, high[i+1..i+h] / P - 1)
MAE_h = max(0, 1 - low[i+1..i+h] / P)
```

SELL：

```text
MFE_h = max(0, 1 - low[i+1..i+h] / P)
MAE_h = max(0, high[i+1..i+h] / P - 1)
```

同时记录：

- `time_to_mfe_bars`、`time_to_mae_bars`；
- `direction_correct`；
- `target_touched`、`stop_touched`；
- `first_touch=target_first/stop_first/no_touch/ambiguous_same_bar`；
- `first_touch_bar`。

同一 OHLC bar 同时越过 target 和 stop 时无法知道先后，必须标记 `ambiguous_same_bar`，不得按有利顺序解释。

### 5.4 聚合指标

每个 horizon、BUY/SELL 和 ALL 分别统计：

```text
signal_count
evaluable_signal_count
directional_accuracy
mean/median directional_return
mean/median MFE
mean/median MAE
edge_ratio = mean(MFE) / mean(MAE)
target_touch_rate
stop_touch_rate
target_first_rate
stop_first_rate
ambiguous_same_bar_rate
```

策略选择不能只按 `directional_accuracy`。例如 70% 的微小正确方向可能被 30% 的大幅逆向波动抵消。至少联合查看：

```text
median directional return
MFE / MAE distribution
target-first vs stop-first
coverage
confidence monotonicity
```

## 6. 历史 Replay 数据结构

```json
{
  "run_meta": {
    "run_id": "t-wb-...",
    "engine_version": "macd_volume_momentum_v1",
    "security_id": 1,
    "symbol": "600183",
    "trade_date": "2026-07-29",
    "period": "min5",
    "persistence_mode": "ephemeral"
  },
  "bars": [],
  "signals": [],
  "signal_evaluation": {
    "evaluation_kind": "forward_event_study_v1",
    "summary": {},
    "by_horizon": [],
    "outcomes": []
  },
  "summary": {},
  "fills": [],
  "round_trips": [],
  "execution_summary": {
    "enabled": false
  },
  "data_quality": {}
}
```

Signal：

```text
signal_id, strategy, side, decision_time, decision_price,
confidence, confidence_kind=rule_score_v2,
reason_codes, features
```

默认 `fills=[]/round_trips=[]`。只有请求显式设置：

```text
include_execution_simulation=true
```

才运行 next-bar execution，并把结果放入 `execution_summary`。默认 `summary` 始终是信号事件评估，不是交易 PnL。

## 7. 实时 5 秒点流模式

### 7.1 两类输入，不做形态伪装

```text
A. 历史研究数据：SDK 原生分钟 K 线
   -> canonical closed bar
   -> historical bar strategy / replay

B. 盘中实时数据：新浪/腾讯等轮询快照
   -> QuotePoint every ~5s
   -> point-native state/features
   -> point-native signal
```

分钟 bar 是缺少完整 tick 历史时寻找候选规则的研究手段；QuotePoint 是盘中真实可观测输入。实时链路不把离散点合成 OHLC，也不为了复用历史 bar 策略而制造 provisional bar。

每个通过交易时段、去重、乱序和 stale 校验的新 QuotePoint 都可以触发一次状态更新和信号重算，因此新浪正常约 5 秒轮询时可以约每 5 秒计算一次。计算频率不等于信号频率：策略仍可用冷却、状态机、最小置信度变化或原因码变化抑制重复信号。

历史策略进入实时前必须有显式的 point-native 对应版本，例如：

```text
historical: VwapBollingerReversionV1 on closed min1 bars
realtime:   PointVwapDeviationReversionV1 on QuotePoint + cumulative amount/volume
```

两者可以共享经济直觉和参数命名，但必须使用不同 `strategy/version/input_mode`，分别统计，不能宣称历史 bar 回测已经验证实时点流版本。日内最高/最低等供应商快照字段只是截至当前时刻的累计状态，也不能拆成分钟 OHLC。

### 7.2 QuotePoint 最小契约

```text
security_id / symbol
source
source_time          # 源提供时优先
observed_at          # 本地收到时间
price                # latest/last
cumulative_volume    # 源提供时记录
cumulative_amount    # 源提供时记录
bid_price/ask_price  # 可选
bid_size/ask_size    # 可选
sequence/status
```

必须区分 `source_time` 与 `observed_at`，统计 polling latency、重复、乱序和 stale quote。策略使用 event time；source time 缺失时才退化到 observed time，并把质量降级写入信号。

累计量额通过相邻快照差分得到区间增量。出现跨日重置、负差、停牌或源回拨时不能简单当作真实负成交量。

### 7.3 新浪实时页实测与适配器

2026-07-30 使用用户已打开的[生益科技实时行情页](https://finance.sina.com.cn/realstock/company/sh600183/nc.shtml)做浏览器网络实测。页面实际读取的主行情请求是：

```text
GET https://hq.sinajs.cn/?rn=<epoch_ms>&list=sh600183
Referer: https://finance.sina.com.cn/realstock/
response charset: GB18030
```

页面主行情约每 5 秒刷新，局部快速组件约每 3 秒刷新；这是一次页面实测结果，不是新浪承诺的 SLA。该接口是网页使用的未公开 JavaScript 文本接口，不应把当前可访问等同于生产授权或长期稳定性。

单证券响应形如：

```text
var hq_str_sh600183="<comma-separated fields>";
```

已验证字段映射：

| 索引 | 含义 |
|---:|---|
| 0 | 证券名称 |
| 1 / 2 / 3 | 今开 / 昨收 / 最新价 |
| 4 / 5 | 日内最高 / 最低 |
| 6 / 7 | 当前买价 / 卖价 |
| 8 / 9 | 累计成交量（股）/ 成交额（元） |
| 10..19 | 买一至买五：数量、价格交替 |
| 20..29 | 卖一至卖五：数量、价格交替 |
| 30 / 31 / 32 | 交易日期 / 交易时间 / 状态 |

当前实现：

```text
RealtimeQuoteAdapter.fetch(symbols) -> list[QuotePoint]
SinaRealtimeQuoteAdapter
create_realtime_quote_adapter("sina")
```

`SinaRealtimeQuoteAdapter` 已实现：

- `sh/sz/bj + 6 位代码` 标准化；
- 请求 `Referer/User-Agent`、超时和 HTTP 状态校验；
- 按 GB18030 解码，不依赖 `response.encoding` 猜测；
- 当前价、累计量额、交易所时间及五档盘口解析；
- 缺证券、字段不足、非法时间/价格时 fail closed，不返回部分结果；
- 通过注入 session/clock 做无网络单元测试。

生产轮询器不能依赖浏览器页签，应直接在后端调用 adapter，并在 adapter 外统一实现：

```text
configurable interval (建议起点 3~5s，最终受授权/限频约束)
jitter + exponential backoff + circuit breaker
source_time staleness / duplicate / out-of-order detection
per-provider latency/error/schema-drift metrics
session heartbeat and graceful stop
```

供应商边界：

| provider | 当前状态 | 说明 |
|---|---|---|
| Sina | 解析适配器和真实响应离线测试已实现 | 未接 scheduler/sink；上线前需确认授权、频率和稳定性 |
| Tencent | 仅保留 adapter 扩展位 | 不复用或猜测新浪字段，必须用独立契约样本测试 |
| Eastmoney | 仅保留 adapter 扩展位 | 优先使用有正式授权与稳定 SLA 的接口 |
| SDK historical bar | 下载任务已实现 | 只进入历史研究/回放数据链路，不接入实时 QuotePoint runtime |

### 7.4 轻量持久化

不保存原始 5 秒行情点。信号产生时立即保存：

```text
signal_id
security_id/symbol
side
decision_source_time / observed_at
decision_price
strategy/version/config_hash
confidence/reason_codes/features
input_mode=point_native
source
quote_count/max_quote_gap/latency/staleness
created_at
```

每个后续快照只更新内存中的 active outcome：

```text
last observed price
MFE / MAE
time_to_MFE / time_to_MAE
target/stop first-touch
quote_count
```

到 1/3/5/15 分钟 deadline 时只保存 compact outcome。这样不保存 quote 历史，仍可得到接近 5 秒精度的信号效果。为应对进程重启，active outcome 的紧凑状态需要周期性 checkpoint；否则崩溃期间的结果必须标记 incomplete，不能用收盘分钟线悄悄补成同精度结果。

当前代码已提供：

```text
QuotePoint
QuoteBookLevel
OnlineSignalOutcomeTracker
RealtimeQuoteAdapter
SinaRealtimeQuoteAdapter
```

点流核心和新浪解析 adapter 已实现；实时 scheduler、signal sink、checkpoint、EOD projection，以及腾讯/东财 adapter 尚未接入。

### 7.5 收盘投射

收盘后获取权威日内分钟线，仅用于：

- 绘制当天 K 线；
- 把真实 signal time/price 画到图上；
- 对在线 outcome 做粗粒度审计；
- 在在线点流中断时生成明确标记为 `eod_bar_fallback` 的降级评估。

投射规则：

1. 信号时间和信号价格保持实时记录值，不替换成分钟 close；
2. 图上 x 坐标使用真实 signal time，y 坐标使用 decision price；
3. 包含信号时刻的分钟 bar 不用于事后 MFE/MAE，因为其 high/low 可能发生在信号之前；
4. fallback 从信号之后第一根完整 bar 开始；
5. 同 bar target/stop 顺序未知时仍标记 ambiguous；
6. 记录 projection method 和分钟数据完整性；canonical bars 不保存并行 source 版本。

## 8. 批量研究与“最佳买点”选择

### 8.1 默认批量输出

- `overall`：主 horizon 的全体信号效果；
- `by_security`；
- `by_day`；
- `by_side`；
- `by_horizon`；
- 后续增加 `by_time_bucket`、`by_regime`、`by_confidence_bucket`；
- `failures/skipped/config/generated_at`。

批量报告按信号效果排序，不按模拟净利润排序。

### 8.2 研究协议

寻找“最佳买点”必须采用冻结协议：

1. 先声明候选策略、参数网格和尝试次数；
2. development 区间只用于构造规则；
3. validation 区间选择少量稳健参数区间，不挑单点峰值；
4. final holdout 只打开一次；
5. walk-forward 按日期推进；
6. 重叠 horizon 的样本不得当作独立样本；
7. bootstrap/置信区间至少按交易日聚类，最好按 security-day 聚类；
8. 和匹配股票、时段、波动、方向的随机时点基线比较；
9. 同时报告失败策略和总尝试次数；
10. 多规则选择使用 White Reality Check、SPA/FDR 或等价校正。

单个策略进入候选 champion 至少要求：

- 足够的可评估信号数和多日覆盖；
- BUY/SELL 分侧不由极少数日期驱动；
- median directional return 为正；
- MFE/MAE、target-first/stop-first 具有稳定优势；
- confidence 分桶总体单调；
- 参数邻域而非单一参数点有效；
- 在不同股票、月份、波动和趋势状态下不过度反转；
- 1 分钟与 5 分钟结果差异可解释；
- holdout 未用于继续调参。

## 9. 因果性与测试门槛

### 9.1 历史信号

对固定 bars：

1. 全量计算特征；
2. 对每个 `i` 用 `bars[:i+1]` 重算；
3. 比较全量位置 `i` 与前缀末尾特征；
4. 修改 `bars[i+1:]`，确认 `<=i` 的 features/signals 不变；
5. opening range 在区间完成前必须为 NULL；
6. 信号模块不得 import evaluation/label 模块。

### 9.2 事件评估

- BUY/SELL 方向收益必须完全对称；
- horizon 不完整不得纳入分母；
- MFE/MAE 使用 decision 后窗口；
- OHLC 同 bar 双触达必须 ambiguous；
- evaluator 改动不得改变 signals；
- 默认请求不得调用 execution simulator。

### 9.3 实时点流

- 乱序/重复 event time fail closed；
- 非法价格/累计量拒绝；
- QuotePoint 去重、乱序、stale、累计量额回拨和最大报价缺口处理正确；
- point-native 特征只读取当前及历史已观察点，不读取未来点或收盘后 bar；
- 信号之前的点不进入 outcome；
- deadline 正确关闭 1/3/5/15 分钟窗口；
- BUY/SELL 方向对称；
- 不保存原始点时，重启缺口明确标记 incomplete；
- 收盘投射不使用包含信号的 bar 做无序 high/low 推断。

## 10. 已知限制

- 当前代码的三个新增策略仅通过固定样本、因果性和契约测试，不代表在真实市场已获利；
- AmazingData 的 `min1/min30/daily` 个股和 `min1/min5` 指数下载、存储与上下文装配已实现，但迁移需先应用且真实账号权限/覆盖范围仍需环境验收；
- time-of-day 基线和宽基市场同步上下文已实现；行业分钟上下文因接口能力不明确而有意不做；
- 新浪 adapter 可解析实时五档快照，但没有历史五档、逐笔成交、OFI 或 aggressor side，尚不能完成可重复的盘口策略历史评估；
- 轮询只能看到离散报价，会漏掉两次采集之间的价格路径与极值；系统如实统计已观察点结果，不用合成 bar 掩盖该限制；
- 事件评估从 decision close 起算，不等同于可成交收益；
- 交替状态机可能抑制独立 BUY/SELL 候选；
- 新浪接口未公开，授权、频率限制、可用性和字段变更均未形成生产 SLA；
- 实时 scheduler、signal sink、checkpoint、腾讯/东财 adapter 和 EOD projection API 仍待实现。
