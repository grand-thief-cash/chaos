# 日内做 T 买卖点研究报告：从对称规则转向两阶段独立点位模型

> 日期：2026-08-16  
> 状态：单股探索性实验已完成；数据扩样与文件型 Level-1 pilot 已落地；两阶段模型、30 股滚动样本外和 LOSO/LOIO 尚未执行
> 范围：A 股日内 BUY/SELL 点位研究，不连接券商，不自动下单  
> 关联设计：[04_SIGNAL_REPLAY_AND_REPORT.md](04_SIGNAL_REPLAY_AND_REPORT.md)

## 1. 结论先行

当前 `macd_volume_momentum_v1` 暴露的“单边下跌中连续 BUY”不是把
`max_round_trips` 从 10 改成 1 或 2 就能解决的问题。限流只会截掉后面的错误信号，
不能让第一个 BUY 更接近反转点；在回测上看起来变好，属于选择/截尾效应，不是买点
预测能力变强。

本轮实验支持以下结论：

1. **当前对称 MACD + 量能 + EMA 偏离回归不具备可用的样本外优势。** 它把
   “偏离更深”当作“更可能反转”，在持续负漂移中会反复接飞刀。
2. **分钟 OHLCV 不是完全没有研究价值，但只适合做候选点和状态基线。** 单股、单日、
   对称规则的信息不够；宽基市场残差和跨股票样本带来了目前最接近正结果的增量。
3. **Level-1 不是自动解药。** 五档盘口能提供 OFI、queue imbalance、micro-price、spread
   和深度恢复等更直接的供需信息，但当前生益科技小样本的 Level-1 结果仍不稳定，不能
   因为数据更细就默认会提高收益。
4. **日内做 T 仍有条件研究价值，但目标必须改成“少而准、允许空仓”。** 系统首先判断
   当前状态是否允许找 BUY/SELL；强单边下跌时可以整天不发 BUY。之后 BUY 和 SELL 使用
   不同模型，分别预测未来路径，而不是把一套均值回归规则镜像。
5. **主评估继续采用信号后的前瞻事件，不以成交配对 PnL 排名。** 成交模拟、费用和持仓
   配对保留为第二层可选诊断；第一层回答点位本身有没有预测力。

因此，下一阶段不再继续围绕当前 MACD 规则寻找一组“漂亮的单日参数”，而是执行：

```text
Stage 1: causal regime / eligibility gate
    -> BUY eligible / SELL eligible / abstain

Stage 2A: independent BUY forward-path model
Stage 2B: independent SELL forward-path model
    -> P(target first), MFE, MAE, time-to-event, calibrated score

Frozen signal
    -> forward event evaluator
    -> optional execution simulator
```

## 2. 已完成实验与证据

### 2.1 实验边界

- 标的：生益科技（`security_id=4889`，`symbol=600183`）。
- 因果边界：特征只使用判断时刻及以前的数据；session VWAP、opening range、日内高低按
  交易日重置；跨日 EMA/MACD 使用历史 warm-up。
- 为减少开盘预热边界干扰，比较实验只允许 10:01 以后发信号。
- 主要 horizon：1/3/5/15 分钟；BUY/SELL 分侧统计。
- 约 0.145% 的往返费用门槛只作次级经济性检查，不替代点位事件评估。
- 所有“V 形”描述只表示理想的事后价格路径，不存在也不新增 `VShapeStrategy`。

### 2.1.1 实验可复现性边界

本节必须区分“已经留存的实验事实”和“下一轮应执行的正式协议”。本轮单股机器学习、
市场残差与 Level-1 数字来自远程开发机上的一次性离线探索；仓库只保留了结果摘要，没有
保留完整实验脚本、逐 fold 日期、精确特征列、模型超参数、随机种子、候选总数和模型文件。
本次也已检查远程 `/tmp`、仓库与相关命令历史，没有找到可以恢复这些信息的实验产物。

因此：

- 下表数字可用于判断“旧规则失败”“某类数据值得/不值得扩样”，但不是可由当前仓库一键
  重跑的正式 benchmark；
- 下文对旧实验只写能够从结果和现有引擎确认的方法，不补造未知的模型类型或超参数；
- 所有后续正式实验必须把数据快照、候选定义、特征清单、fold 边界、模型版本、参数、随机
  种子和逐事件预测保存为只读 manifest，才能升级为可复核证据；
- 在正式复跑之前，`n=15、正确率 60%` 只能读成“15 次里 9 次方向正确”，不能读成模型
  已达到 60% 的稳定预测能力。

### 2.2 结果摘要

| 实验 | 最终样本外结果 | 判断 |
|---|---|---|
| 当前 MACD + 量能 + EMA，5 分钟 | `n=105`，方向正确率 37.14%，平均方向收益 -0.0430%，中位数 -0.1445%，target-first 27.62%，stop-first 48.57% | 明确失败 |
| 当前 MACD + 量能 + EMA，15 分钟 | `n=101`，方向正确率 44.55%，平均 -0.0628%，中位数 -0.1354% | 明确失败 |
| 深偏离 + MACD 转折 + 量能 + 两 bar 结构突破，5 分钟 | `n=65`，正确率 52.31%，平均 -0.0156%，中位数 +0.0683%，edge ratio 0.8918 | 中位数改善但整体无优势 |
| 同一手工过滤，15 分钟 | `n=61`，正确率 40.98%，平均 -0.1698%，中位数 -0.1920% | 明确失败 |
| 单股 OHLCV 机器学习，5 分钟 | `n=22`，正确率 40.91%，平均 -0.0619%，费用门槛后 -0.2069% | 过拟合 |
| 单股 OHLCV 机器学习，15 分钟 | `n=15`，正确率 60.00%，平均 +0.1003%，费用门槛后 -0.0447% | 样本少且无经济优势 |
| OHLCV + 上证指数残差，稀疏 BUY，5 分钟 | validation `n=14`、平均 +0.4293%；final `n=7`、平均 +0.4673%、中位数 +0.0089%；去掉最佳样本后平均 +0.2047% | 当前最有希望，但证据不足 |
| Level-1 ridge BUY，1 分钟 | final `n=12`，正确率 66.67%，平均 +0.1248%，中位数 +0.1716% | 低于 0.145% 门槛，也未越过随机 p95 |
| Level-1 ridge BUY，3/5 分钟 | validation 为正、final 分别转为 -0.4974% / -0.7098% | 不稳定 |

市场残差 BUY 的 final 平均 +0.4673%，但匹配同股票、日期、方向和数量的随机时点基线
95% 分位为 +0.4732%，观测值仍略低于该门槛；而且只有 7 个事件。它说明“市场状态和
残差值得继续”，不构成策略已验证。该模型在 2026-08-14 的持续下跌阶段没有发 BUY，
方向上符合本报告主张的 abstention，但样本量还不能证明稳定性。

### 2.3 各实验具体怎么做、怎样判定

#### 2.3.1 公共事件研究流程

所有实验都把信号时刻冻结为 `t`，只用 `t` 及以前的输入计算信号，再观察
`t+1 ... t+h` 的未来路径。BUY 的方向收益为 `close[t+h] / P_t - 1`，SELL 为
`1 - close[t+h] / P_t`；MFE/MAE、目标先到/风险先到的定义见 4.2。单股探索中把 10:01
作为最早候选时刻，以减轻开盘 warm-up 和集合竞价量对短窗口的影响。

判断不是只看“正确率”，而按以下优先级：

1. **最终时间外样本优先。** validation 用来选候选阈值，final 只能读取一次；训练内或
   validation 的漂亮结果不能当结论。
2. **收益分布优先于命中数。** 同看方向收益的均值、中位数、MFE、MAE、target-first、
   stop-first；60% 小涨、40% 大跌可能有高正确率但仍无优势。
3. **稀疏模型必须对照同覆盖率随机时点。** 固定股票、日期、side、时段和信号数量重复
   抽样；只有超过随机分布 95% 分位才算发现超出“碰巧买在反弹前”的证据。
4. **检查集中度。** 去掉最佳事件或最佳 `security-day` 后结果仍应同号；否则均值可能只由
   一个极端反弹贡献。
5. **0.145% 往返成本只作第二层门槛。** 第一层先证明点位有预测力；若平均毛空间连研究
   成本门槛都覆盖不了，也不能进入交易价值讨论。
6. **样本量是硬约束。** 本轮 `n=7/12/15/22` 只能形成假设，不能因点估计为正而通过。
   正式最低门槛见 6.4。

#### 2.3.2 当前 MACD + 量能 + EMA 规则

这是仓库中可以精确复核的规则。每根完整分钟 bar 计算：慢 EMA、ATR、MACD 柱、过去
截至当前的 `window` 根成交量中位数和 `volume_ratio = 当前量 / 滚动成交量中位数`。BUY 候选必须同时
满足：价格仍低于慢 EMA、`(close - EMA_slow) / ATR <= -ema_deviation_atr`、负 MACD 柱连续
收敛指定根数或刚由负转正，以及最近 `volume_confirmation_window` 根中的最大量比不低于
`min_volume_ratio`；SELL 镜像。确认、冷却和每侧上限只改变发出时机/数量，不改变候选是否
真的接近反转。

实验在冻结信号后分别评估 5/15 分钟路径。5 分钟 `n=105` 与 15 分钟 `n=101` 的均值、
中位数和正确率都为负面，因此不是“成本吃掉了小优势”，而是点位方向本身失败。

#### 2.3.3 深偏离 + MACD 转折 + 量能 + 两 bar 结构过滤

该实验在原规则外增加更严格的候选交集：更深的 ATR 标准化偏离、MACD 柱收敛/过零、近期
量能确认，以及 BUY 需要后续完整 bar 突破前一 bar 的局部结构（SELL 反向）。目的不是拟合
成交配对，而是验证“先出现超卖，再出现可见转折”能否减少接飞刀。

留存结果表明 5 分钟中位数从负转为 `+0.0683%`，说明结构确认有筛选作用；但平均仍为
`-0.0156%`、MFE/MAE 低于 1，15 分钟再次明显为负，所以判为“局部改善、没有整体优势”。
该一次性实验没有留下精确阈值与逐事件清单，不能继续围绕这组数字调参；正式复跑应把它
作为一个固定、透明的 rule baseline，而不是 champion。

#### 2.3.4 单股 OHLCV 机器学习

这一路线的目标是让模型从因果 OHLCV 派生状态中学习非线性交互，而不是硬编码一组
MACD 阈值。能够确认的输入范围是生益科技 min1 OHLCV/amount 可派生的信息，例如多窗口
收益、EMA slope/偏离、MACD、RSI、ATR、VWAP 偏离、bar range/wick、量比、日内时刻和
realized volatility；标签仍是独立 BUY/SELL 的 5/15 分钟未来方向/路径，数据按时间先后
分为训练、validation 和最终片段，最终仅保留高分稀疏事件。

但仓库没有保存该次单股实验采用的具体 estimator、特征子集、超参数、fold 日期和阈值，
所以不能把下列内容写成已执行事实：它究竟是 logistic、ridge、树模型还是集成模型，以及
每列特征的系数/重要性。正式复跑必须先用正则化 logistic/ridge 作为可解释 baseline，再以
GBDT 作为非线性 challenger；两者使用相同 folds、候选全集和 coverage 比较，不能只报告
胜出的一个。

为什么 15 分钟 60% 仍判“样本少且无经济优势”：

- `n=15` 只有 9 次方向正确，二项抽样误差极大；相差一两个事件就会显著改变比例；
- 平均毛方向收益只有 `+0.1003%`，低于 `0.145%` 的次级成本门槛，成本后为 `-0.0447%`；
- 同一模型在 5 分钟 `n=22` 上只有 40.91%、平均 `-0.0619%`，没有跨 horizon 稳定性；
- 单股票会把某几天的价格尺度、波动和特定行情记成模式，无法证明跨日期、跨股票迁移；
- 未保留 matched-random、校准曲线和完整尝试次数，无法排除阈值选择与数据窥探。

机器学习路线仍有探索空间，但研究对象应从“单股模型”升级为“跨股票、分 side、带状态
gate 的概率模型”。继续的条件不是把单股 60% 调到更高，而是完成 30 股 walk-forward、
LOSO/LOIO、概率校准、随机基线和集中度检查；若正则化 baseline 与 GBDT 都不能在相同
coverage 下越过这些门槛，应停止这条路线。

#### 2.3.5 OHLCV + 上证指数残差的稀疏 BUY

该实验先用截至 `t` 的滚动窗口估计个股对上证指数的 beta，再构造
`stock_return - beta * index_return`，把市场共振与个股相对卖压加入 OHLCV 候选，BUY 与
SELL 不强制配对。模型/阈值只保留少量高分 BUY，所以 validation 只有 14 个、final 只有
7 个事件。它在 2026-08-14 的单边下跌段选择 abstain，是相比无条件超卖规则更合理的行为。

它是当前最有希望的**研究假设**，不是当前最好策略：final 平均 `+0.4673%` 虽高，但中位数
只有 `+0.0089%`，且没有超过 matched-random p95 `+0.4732%`。去掉最佳事件仍为正只能说明
结果并非完全由单点贡献，不能补足 `n=7` 的不确定性。下一次必须扩大到至少 20 只股票、
3 个自然月和每侧至少 200 个 final OOS 事件，并比较上证/沪深300/中证500/中证1000中按
训练期确定的 benchmark，才能判断残差是真增量还是样本偶然。

#### 2.3.6 Level-1 ridge BUY

该实验从文件型 Snapshot 派生 spread、五档深度、queue imbalance、micro-price 偏移、
累计量额/成交笔数差分和短窗口变化，使用带 L2 正则的线性 ridge 类 baseline 预测稀疏 BUY
的未来路径；按时间顺序分 validation/final，并与相同数量随机时点比较。1 分钟 final
`n=12` 虽有 8 次方向正确、平均 `+0.1248%`，仍低于成本研究门槛且未超过随机 p95；3/5
分钟从 validation 正转为 final 大幅负，属于明显的时间不稳定。

这说明盘口特征可能描述极短期供需，但不能自动解决日内 5/15 分钟反转。该实验同样未保留
完整特征 manifest 和逐 fold 模型，下一轮只能作为待复现的 pilot；只有在相同股票、日期、
gate 和 coverage 下稳定优于 min1-only，才值得扩大文件留存，更不应现在写入数据库。

### 2.4 单边行情的结构性问题与解决方向

当前规则同时存在四个结构性问题。这里没有任何指标能在实时中确定“卖压已经结束”；可做的
是用因果证据提高结束/衰减的条件概率，并在不确定时 abstain。

1. **卖压结束不能被单点确认。** `close < EMA` 和负 MACD 柱收敛只说明跌速可能变慢。
   min1-only 至少应等待个股/市场残差不再创新低、1 分钟价格重新站回短窗口结构、3 分钟
   下行动量衰减且 spread proxy/价格冲击没有恶化；有 Level-1 时再看 OFI 从极端卖压回归、
   bid depth 停止撤退、spread 收窄和 micro-price 回到 mid 上方。它们是概率证据，不是
   “底部确认函数”。
2. **偏离必须条件化于 regime。** EMA/ATR 偏离在趋势状态中不是平稳量。先由 5 分钟状态
   gate 识别强下跌/市场共振并硬 veto BUY，再在 range/reversal-eligible 状态里解释偏离；
   还可用训练期内的同股票、同波动、同时段条件分位数代替全局固定阈值。解决办法是允许
   `no_signal`，不是把偏离阈值不断加深。
3. **加入原始 volume 不能解决方向归因，但可改善刻度信息。** `volume_ratio` 只描述相对异常，
   原始 volume 又强烈受股票规模和开盘/收盘季节性影响。两者都应保留，并与价格方向组合成
   `signed bar-volume proxy`、收盘在 bar range 的位置、amount/range、Amihud price impact、
   同分钟相对量和放量后价格是否继续创新低等交互；真正更接近供需方向的是 Level-1 OFI，
   但 Snapshot 仍不能精确还原逐笔主动买卖。
4. **BUY/SELL 从候选到验证全部拆开。** 分别定义候选全集、未来标签、状态 veto、模型、
   概率校准、发信号阈值和报告；BUY 学“卖压衰减后向上路径”，SELL 学“买压衰减/流动性
   撤退后的向下路径”，不共享符号镜像参数。最后只有 execution simulator 才处理先买后卖、
   先卖后买和底仓约束。

### 2.5 1/3/5 分钟如何组合

可以组合，但必须按已完成窗口因果聚合，而不是让三个周期各自投票后取多数：

```text
5 分钟：regime / market alignment / 强趋势 veto（是否允许找 BUY 或 SELL）
3 分钟：impulse deceleration / residual pressure（卖压或买压是否衰减）
1 分钟：entry timing / structure reclaim / Level-1 recovery（精确触发时刻）
```

在时刻 `t`，只使用截至 `t` 已闭合的滚动 3/5 分钟窗口；不能把尚未结束的自然 5 分钟 bar
最终 OHLC 泄漏给 1 分钟决策。5 分钟强下跌 veto 的优先级高于 1 分钟 MACD 转折；只有
5 分钟允许、3 分钟衰减、1 分钟触发三层依次通过才发 BUY。第一版可直接从 min1 因果滚动
聚合得到 3/5 分钟特征，避免三套 bar 时间戳错位；后续再验证交易所 3/5 分钟成品 K 线是否
带来不同的信息。15/30 分钟或日线只作更慢背景，不参与抢反转点。

`cooldown_bars` 和 `max_round_trips` 只能控制信号数量；它们不能作为趋势识别器，也不能
进入“最佳点位”证据。

## 3. 数据现状与本轮落地

### 3.1 min1 覆盖与任务修复

本轮使用开发 Cronjob 完成了历史区间补齐：任务 24 的 run 54 回填生益科技；任务 27 的
run 55 同步四个宽基；由于上证指数已有较新的 watermark，另用一次性
`replay_from_start=true` 任务 30（run 58）修复旧区间缺口。核验结果如下：

| 标的 | `security_id` | 请求区间行数 | 交易日数 | 首个 bar | 最后 bar |
|---|---:|---:|---:|---|---|
| 生益科技 600183.SH | 4889 | 94,080 | 392 | 2025-01-02 09:31 | 2026-08-14 15:00 |
| 上证指数 000001.SH | 10520 | 94,080 | 392 | 2025-01-02 09:31 | 2026-08-14 15:00 |
| 沪深300 000300.SH | 10663 | 94,080 | 392 | 2025-01-02 09:31 | 2026-08-14 15:00 |
| 中证500 000905.SH | 10725 | 94,080 | 392 | 2025-01-02 09:31 | 2026-08-14 15:00 |
| 中证1000 000852.SH | 10705 | 94,080 | 392 | 2025-01-02 09:31 | 2026-08-14 15:00 |

2025-01-01 为休市日，所以第一个有效 bar 是 2025-01-02。上证指数表中另有一个既存的
2024-07-01 交易日，整表为 94,320 行/393 日；上表只统计本次要求的 2025-01-01 起区间。

首次把生益科技从 2025-01-01 回填时，AmazingData 单次结果在约 30,000 行处截断，并且
触发 Artemis child timeout。本轮已修改股票专用 `STOCK_ZH_A_KLINE_PARENT`：根据周期、单批证券数
和 `max_rows_per_child` 自动切分日期窗口，默认把单 child 估算行数压到 12,000 以下；同时
增加显式 `replay_from_start=true`，只用于修复“表内已有新 watermark、但旧区间有缺口”的
场景。普通定时执行仍从 watermark 增量，不反复全量回放。

### 3.2 约 30 只跨行业高流动性样本股

不能凭主观印象直接写 30 个代码，也不能用 2026-08-14 才知道的流动性排名去解释更早的
历史样本。本轮选择流程为：

1. 补 2026-04-17 至 2026-08-14 的全市场不复权日线；
2. 补 AmazingData 申万行业成分映射；
3. 只保留 `security_registry` 中 active 的沪深北 A 股，排除 ST、近 120 日交易日不足 40、
   成交额为空或长期停牌标的；
4. 流动性分数以近 120 个自然日内有效交易日的 `median(amount)` 为主、`mean(amount)` 为辅，避免单日爆量
   主导排名；
5. 生益科技作为既有问题标的强制作为电子行业样本；其余已分类行业各取成交额中位数最高的
   标的，按流动性取前 29 个行业；未映射申万一级行业的证券不进入本轮名单；
6. 因而每个申万一级行业恰好 1 只，不让电子、金融等高成交行业挤占跨行业验证配额；
7. 样本池在研究启动时冻结并写入报告。后续历史 walk-forward 若需要重新选股，必须在每个
   fold 的训练截止日按当时可见数据重算，不能使用本次冻结名单制造生存者偏差。

冻结名单如下：

| # | `security_id` | 标的 | 申万一级行业 | 交易日 | 成交额中位数（亿元） |
|---:|---:|---|---|---:|---:|
| 1 | 4889 | 生益科技 600183.SH | 电子 | 82 | 97.65 |
| 2 | 2327 | 中际旭创 300308.SZ | 通信 | 82 | 339.27 |
| 3 | 1571 | 宁德时代 300750.SZ | 电力设备 | 82 | 143.77 |
| 4 | 1881 | 华工科技 000988.SZ | 机械设备 | 82 | 106.43 |
| 5 | 4269 | 紫金矿业 601899.SH | 有色金属 | 82 | 89.57 |
| 6 | 3338 | 中国巨石 600176.SH | 建筑材料 | 82 | 83.56 |
| 7 | 896 | 紫光股份 000938.SZ | 计算机 | 82 | 74.63 |
| 8 | 2205 | 多氟多 002407.SZ | 基础化工 | 82 | 64.18 |
| 9 | 489 | 东方财富 300059.SZ | 非银金融 | 82 | 63.69 |
| 10 | 4654 | 药明康德 603259.SH | 医药生物 | 82 | 59.96 |
| 11 | 4485 | 贵州茅台 600519.SH | 食品饮料 | 82 | 56.60 |
| 12 | 2394 | 蓝色光标 300058.SZ | 传媒 | 82 | 54.49 |
| 13 | 4066 | 太极实业 600667.SH | 建筑装饰 | 82 | 52.68 |
| 14 | 2344 | 三花智控 002050.SZ | 家用电器 | 82 | 47.01 |
| 15 | 3820 | 大唐发电 601991.SH | 公用事业 | 82 | 45.60 |
| 16 | 925 | 菲利华 300395.SZ | 国防军工 | 82 | 41.90 |
| 17 | 35 | 比亚迪 002594.SZ | 汽车 | 82 | 38.22 |
| 18 | 5139 | 招商银行 600036.SH | 银行 | 82 | 32.35 |
| 19 | 2897 | 东阳光 600673.SH | 综合 | 82 | 24.52 |
| 20 | 3520 | 万通发展 600246.SH | 房地产 | 82 | 23.62 |
| 21 | 2956 | 中国中免 601888.SH | 商贸零售 | 82 | 20.50 |
| 22 | 3536 | 招商轮船 601872.SH | 交通运输 | 82 | 20.27 |
| 23 | 2059 | 牧原股份 002714.SZ | 农林牧渔 | 82 | 19.75 |
| 24 | 3451 | 中国石油 601857.SH | 石油石化 | 82 | 17.69 |
| 25 | 4544 | 中国神华 601088.SH | 煤炭 | 82 | 16.36 |
| 26 | 1280 | 盈峰环境 000967.SZ | 环保 | 82 | 13.38 |
| 27 | 4408 | 包钢股份 600010.SH | 钢铁 | 82 | 13.07 |
| 28 | 1156 | 顺灏股份 002565.SZ | 轻工制造 | 82 | 9.61 |
| 29 | 2851 | 信测标准 300938.SZ | 社会服务 | 82 | 7.91 |
| 30 | 505 | 探路者 300005.SZ | 纺织服饰 | 82 | 7.13 |

开发 Cronjob 任务 28 的 run 65 已完成 211/211 个 child；日线表核验为 497,375 行、7,723 个
registry identity。冻结名单的每只股票在本次选择窗均有 82 个有效交易日。

这 30 只是研究样本，不是推荐买入名单，也不是永久业务白名单。

### 3.3 Level-1 先落文件，不进数据库

已新增 `STOCK_ZH_A_LEVEL1_FILE`，首轮边界为：

- 只接受 `security_registry` 中最多 10 只 A 股；禁止 `all_registered`；
- 单次最多 31 个自然日；按证券和交易日查询历史 Snapshot；
- 原始快照写 ZSTD Parquet，不写 PhoenixA，不新增事实表；
- 每个分区使用原子替换，并写 `manifest.json`；只有 manifest、文件大小和 SHA-256 都匹配时
  才视为已完成，后续增量自动跳过；
- `force=true` 时若供应商返回空数据，不覆盖已经验证完整的旧分区；
- 原始文件不做 5 秒重采样、不合成 K 线，研究派生特征另写文件，禁止覆盖原始快照。

目录结构：

```text
runtime/artemis/level1_snapshot/
  security_id=4889/
    trade_date=2026-08-14/
      snapshot.parquet
      manifest.json
```

manifest 至少记录：数据源、`security_id/symbol/exchange/vendor_code`、交易日、行数、列和
dtype、首末时间、重复时间数、cadence 中位数/p95/max、字节数、SHA-256 和完成时间。

2026-08-14 生益科技单股真实 smoke test（Cronjob 任务 29、run 64）先落 5,770 行；随后用冻结
名单前八个行业样本执行真实多证券 smoke test（run 66）：600183、300308、300750、000988、
601899、600176、000938、002407 共 42,613 行、2,377,818 bytes，八个分区的中位 cadence 均为
3 秒，每个文件的 SHA-256 均已写 manifest。字段包含 last、累计量额/成交笔数、五档 bid/ask
价量和交易阶段码。供应商原始数据覆盖到 16:29/17:00，因此训练视图必须结合交易阶段码和
A 股 session 过滤，不能把盘后快照当作连续竞价。

AmazingData 实际返回结构为“交易日 → 证券代码 → DataFrame”，适配器与多证券回归测试已
覆盖该嵌套结构。试跑后保持 `force` 关闭，完整分区会自动跳过。

这次 smoke test 只生成 Parquet 和 manifest；PhoenixA 数据库表、迁移和写入调用均未增加。

后续 Level-1 pilot 建议从冻结名单中选 5–10 只，覆盖不同价格、tick size、行业和流动性，
只下载相同的滚动训练/验证/测试日期。若 Level-1 模型不能在同一 OOS fold 上显著优于
min1-only champion，就停止扩容，不讨论数据库持久化。

## 4. 两阶段独立点位模型

> **执行状态：方案设计，尚未训练或接入 Signal Engine。** 当前 Artemis 已有因果分钟特征、
> 多策略 Signal Engine 和 Forward Event Evaluator，可复用为实验底座；但本章所写的 Stage-1
> regime gate、Stage-2 BUY/SELL 概率模型、概率校准与 expected-edge 发射条件均未实现，
> 也没有产生本章模型的样本外结果。

### 4.1 第一阶段：状态识别与发信号资格

第一阶段不预测“这里就是最低点”，而是回答：**在当前可见状态下，未来 1/3/5/15 分钟
是否值得让 BUY 模型参与；SELL 模型是否值得参与；还是两边都 abstain。**

建议输出以下互不要求完全排他的概率：

```text
P(downtrend_continuation)
P(uptrend_continuation)
P(market_bearish_shock)
P(market_bullish_shock)
P(liquidity_sell_shock)
P(liquidity_buy_shock)
P(range_or_reversal_eligible)
```

第一版先用透明规则/逻辑回归形成可审计 baseline，再比较带概率校准的 GBDT。不能直接用
复杂模型掩盖标签和验证问题。

### 4.1.1 因果输入

| 状态维度 | min1 输入 | Level-1 可选增量 | 用途 |
|---|---|---|---|
| 个股趋势 | 1/3/5/15 分钟收益、EMA slope、VWAP/ATR 偏离、日内新高低、realized volatility | last/mid 事件收益 | 识别趋势延续，不把深偏离直接当反转 |
| 市场共振 | 上证、沪深300、中证500、中证1000同步收益、波动和 breadth proxy | 指数快照 | 区分个股残差与系统性下跌 |
| 个股残差 | 只用过去窗口估计 beta；`stock_return - beta * benchmark_return` | 同步 mid residual | 捕捉相对卖压和卖压衰减 |
| 时段季节性 | 同一分钟过去 20–60 日量能/波动基线 | 同时段 spread/depth 基线 | 避免把开盘常规放量误判成冲击 |
| 流动性 | bar amount、range、wick、Amihud proxy | spread、五档深度、OFI、queue imbalance、micro-price、成交笔数增量 | 区分恐慌卖出与承接恢复 |
| 慢状态 | 前一日收盘、跳空、point-in-time 日线趋势/波动 | 无 | 防止只看当日局部窗口 |

行业分钟指数仍不作为依赖；供应商只明确提供行业日行情。跨行业股票样本用于模型稳健性，
不等于已经有行业分钟残差。

### 4.1.2 可执行 gate

BUY 资格的 baseline 可以写成：

```text
buy_eligible =
    P(downtrend_continuation) < threshold_down
    AND P(market_bearish_shock) < threshold_market
    AND residual_selling_pressure_is_decelerating
    AND liquidity_is_normal_or_recovering
    AND expected_5m_volatility_is_sufficient
```

其中“卖压衰减”至少要求残差收益不再连续创新低，或 Level-1 OFI/queue imbalance 从极端卖压
回到中性；“流动性恢复”要求 spread 没有继续扩大、bid depth 不再持续撤退。任一硬 veto
触发时 BUY 模型不运行，因此单边下跌可以得到 `no_signal`，而不是换一组超卖参数继续 BUY。

SELL 资格单独训练和设阈值。它不是 BUY 条件简单乘以 -1；例如快速下跌后的 SELL 可能已经
面临反弹风险，而缓慢上涨中的流动性撤退也可能产生独立 SELL 机会。

状态标签必须来自未来路径，但状态特征只能来自 `t` 及以前。不能用事后 V 形、当日最终
最低点或完整日内高低反标实时状态。

### 4.2 第二阶段：BUY/SELL 独立预测未来路径

对每个通过 gate 的时刻 `t`、判断价 `P_t` 和 horizon `h ∈ {1,3,5,15}`，生成以下标签。

BUY：

```text
directional_return_h = close[t+h] / P_t - 1
MFE_h = max(high[t+1:t+h]) / P_t - 1
MAE_h = 1 - min(low[t+1:t+h]) / P_t
time_to_MFE_h
time_to_MAE_h
target_first / stop_first / no_touch / ambiguous_same_bar
time_to_first_touch_h
```

SELL 使用独立标签和模型：

```text
directional_return_h = 1 - close[t+h] / P_t
MFE_h = 1 - min(low[t+1:t+h]) / P_t
MAE_h = max(high[t+1:t+h]) / P_t - 1
```

同一 OHLC bar 同时触达 target 和 stop 时仍记为 `ambiguous_same_bar`。Level-1 研究可用未来
mid 做微观预测标签，并另设基于可执行 bid/ask 的次级标签；不能把 mid 优势直接当成可成交
收益。

### 4.2.1 模型输出

BUY 和 SELL 各自训练一组多任务或分任务模型：

- 分类：`P(target_first_h)`、`P(stop_first_h)`、`P(direction_correct_h)`；
- 回归/分位数：`E[MFE_h]`、`E[MAE_h]`、MFE/MAE 的 p25/p50/p75；
- 生存/离散 hazard：目标或止损在第几分钟首次触达；
- 概率校准：按日期外样本做 isotonic 或 Platt calibration，不能在 final test 校准。

第一版不要求神经网络。逻辑回归/GBDT + quantile regression 已足以验证数据有没有增量。

信号分数示意：

```text
expected_edge_h =
    P(target_first_h) * target_return
    - P(stop_first_h) * stop_return
    + P(no_touch_h) * E[directional_return_h | no_touch]

emit BUY only if:
    stage1.buy_eligible
    AND calibrated P(target_first_h) >= probability_threshold
    AND expected_edge_h >= research_hurdle
    AND predicted_MFE_p50 / predicted_MAE_p50 >= payoff_threshold
else:
    abstain
```

模型输出的是独立点位。T+0 配对、已有底仓、先买后卖/先卖后买、费用、滑点和最小手数在
下游 execution simulator 处理，不反过来污染点位标签。

## 5. 训练所需数据

> **执行状态：原始数据准备部分完成，模型数据集未构建。** 生益科技、四个宽基 min1、30 股
> 冻结样本选择和八股单日 Level-1 文件 pilot 已完成；30 股全区间 min1 的质量验收、同步
> 特征矩阵、point-in-time fold 数据集和标签 manifest 尚未完成。下列清单是正式实验输入
> 合同，不表示已经全部可训练。

### 5.1 必需数据

1. 30 只样本股 2025-01-01 至今的 `min1/nf` OHLCV + amount；
2. 上证指数、沪深300、中证500、中证1000同区间同步 `min1/nf`；
3. 目标日前已完成的日线、前收盘、跳空和滚动波动；
4. 至少 20–60 个历史交易日的同分钟量能/波动基线；
5. `security_registry` 身份与 point-in-time 上市/退市状态；
6. 申万一级行业只用于样本分层和报告，不用于伪造行业分钟特征。

### 5.2 可选 Level-1 数据

每个 Snapshot 保留：交易所时间、last、累计量/额/成交笔数、五档 bid/ask 价量、交易阶段码。
派生特征包括：

```text
spread / relative_spread
depth_bid_1_5 / depth_ask_1_5
queue_imbalance_1 / queue_imbalance_1_5
micro_price - mid
OFI over 3s/15s/30s/60s
delta cumulative volume / amount / trades
cancel-like depth withdrawal proxy
spread/depth recovery time
```

Snapshot 是离散状态，不声称能精确还原逐笔委托和 aggressor side。累计量差分不能等价为
Level-2 主动买卖流；跨日重置、午休、停牌和源回拨必须标记质量状态。

## 6. 滚动样本外与跨股票验证

> **执行状态：验证协议，尚未执行。** 本轮单股探索没有完成本章定义的 walk-forward、
> LOSO、LOIO、clustered bootstrap 和每侧至少 200 个 final OOS 事件门槛；因此第二章中的
> 正结果都只能视为待复现假设。

### 6.1 Walk-forward

建议最小 fold：

```text
train: 至少 120 个交易日
validation: 20 个交易日
test: 20 个交易日
step: 20 个交易日
max horizon purge: 15 分钟
same-security embargo: 至少 15 bars
```

每个 fold 只在 train 拟合特征标准化、beta、time-of-day baseline 和模型；validation 选择
少量阈值区间并做校准；test 只评估一次。随后向前滚动。不得用 8 月 14 日的表现回头修改
7 月模型，再把整个区间称作样本外。

### 6.2 Leave-one-stock-out / leave-one-industry-out

需要两类交叉验证：

1. **LOSO：** 每次用 29 只股票训练/校准，在完全未见过的第 30 只上测试，轮换 30 次；
2. **LOIO：** 每次留出一个申万一级行业，检查模型是否只记住行业或价格尺度。

日期和股票维度必须同时隔离。只做“随机拆 bar”会让同一天相邻样本和同股票状态泄漏到
训练集，是无效验证。

### 6.3 固定报告

每个 side、horizon、regime、股票和月份至少报告：

```text
eligible timestamp count
signal count / coverage / no-signal rate
directional return mean / median / clustered bootstrap CI
MFE / MAE distribution and edge ratio
target-first / stop-first / ambiguous rate
time-to-target / time-to-stop
calibration curve / Brier score
matched random-time baseline
mean without best security-day
estimated cost hurdle pass rate
```

不得只展示总体平均，也不得隐藏失败股票、失败月份、失败 side 和总尝试次数。

### 6.4 进入实时影子的最低门槛

以下门槛是研究治理起点，不是收益承诺：

- BUY 和 SELL 分别至少 200 个最终 OOS 可评估事件，并覆盖至少 20 只股票、3 个自然月；
- median directional return 为正，clustered bootstrap 置信区间不长期跨越明显负值；
- 平均方向收益高于匹配随机时点 95% 分位，且去掉最佳 security-day 后仍为正；
- target-first 高于 stop-first，MFE/MAE 在相邻参数区间稳定；
- 费用门槛后的次级结果为正，但不以费用参数反向挑信号；
- 至少 70% 的股票不为负，且任何单一股票/日期贡献不超过总体 edge 的 20%；
- 概率分桶基本单调；低置信度扩容不会让结果突然翻转；
- Level-1 候选必须在相同 fold、相同 coverage 或相同阈值约束下优于 min1-only baseline。

未达到门槛时保留 `research_only`，不进入实时提醒，更不连接交易。

## 7. 后续实验是否还需要继续

**需要。** 当前单股结果只能否定旧策略，不能证明两阶段方案有效。下一轮实验按以下顺序，
每一步都有停止条件：

1. 数据质量：完成 30 股 + 4 指数同步 min1，检查缺分钟、重复、午休、复权、价格尺度和
   provider truncation；失败则不训练。
2. Stage-1 baseline：只做状态/gate，验证它能否显著降低强下跌中的 BUY coverage，同时不把
   所有信号过滤掉。
3. Stage-2 min1-only：BUY/SELL 独立建模，完成 walk-forward + LOSO；若仍不优于随机基线，
   暂停日内做 T 模型研究。
4. Level-1 A/B：在相同股票、日期和 gate 上只增加盘口特征；若 OOS 增量不稳定，删除 pilot
   文件或缩短保留期，不建数据库表。
5. 实时影子：只有历史门槛通过后，才用实时 QuotePoint/Level-1 记录信号和 compact outcome；
   不合成 bar，不下单。

这套流程允许最终结论是“在当前数据、费用和市场结构下，单股日内做 T 没有足够稳定的研究
价值”。停止一个无效方向本身也是有效产出，不能为了页面必须显示 BUY/SELL 而强造信号。

## 8. 研究依据

- Cont, Kukanov and Stoikov, *The Price Impact of Order Book Events*：短期价格变化与
  order-flow imbalance 的关系比原始成交量更直接。[arXiv](https://arxiv.org/abs/1011.6402)
- Gould and Bonart, *Queue Imbalance as a One-Tick-Ahead Price Predictor*：队列不平衡对
  下一次 mid-price 方向有预测力，但效果依赖市场微观结构。[arXiv](https://arxiv.org/abs/1512.03492)
- Stoikov, *The Micro-Price: A High Frequency Estimator of Future Prices*：micro-price 将
  spread 和盘口不平衡合并为短期价格估计。[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694)
- Gao et al., *Market Intraday Momentum*：日内可预测性具有明显的时段、成交量和波动状态
  依赖。[论文信息与 DOI](https://www.researchwithrutgers.org/en/publications/market-intraday-momentum/)
- 中国股市的短期反转研究显示，反转强弱依赖流动性、波动和换手，不能把均值回归作为
  无条件规律。[NBER working paper](https://www.nber.org/papers/w30917)
- 中国 A 股截面反转研究强调成交量与订单不平衡的条件作用；它是跨股票证据，不能直接
  外推成单股 5 分钟 alpha。[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2214845023000029)
- Sullivan, Timmermann and White, *Data Snooping, Technical Trading Rule Performance, and
  the Bootstrap*：大量规则中挑 champion 必须校正数据窥探。
  [LSE](https://researchonline.lse.ac.uk/119144/)
- Bailey and López de Prado, *The Deflated Sharpe Ratio*：多次策略/参数尝试会制造选择偏差，
  必须保留尝试次数与最终 holdout。[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)

这些论文用于形成可证伪假设，不表示论文中的市场、时期和成本条件可以直接外推到 A 股单股
日内做 T。
