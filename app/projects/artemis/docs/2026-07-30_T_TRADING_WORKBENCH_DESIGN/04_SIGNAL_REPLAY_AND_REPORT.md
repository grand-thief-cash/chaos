# 04. 信号、回放与报告

## 1. 第一轮策略：Causal Mean Reversion V1

第一轮目标是建立可解释、可审计的基准，不追求参数最优。

### 1.1 因果特征

对当前交易日按分钟顺序计算：

- `return_1`：当前 close / 前一 close - 1；
- `rolling_mean/std`：仅使用截至当前的 trailing window；
- `price_zscore`：close 相对 trailing mean 的标准化偏离；
- `rsi`：Wilder/EMA 形式，只使用历史差分；
- `session_vwap`：截至当前累计 amount / volume；
- `vwap_deviation`：close / VWAP - 1；
- `range_position`：close 在 trailing high/low 中的位置；
- `reversal_up/down`：当前实体方向及相对前一 close 的确认；
- `volume_ratio`：当前量 / trailing volume median。

禁止 centered rolling、`shift(-n)`、全日最大最小、全日均值标准化。

### 1.2 候选与确认状态机

BUY 候选：

```text
price_zscore <= -entry_z
AND rsi <= entry_rsi
AND close <= session_vwap
```

在 `confirmation_bars` 内满足以下条件才生成 BUY decision：

```text
close > previous_close
AND close >= open
AND rsi >= previous_rsi
```

SELL 候选和确认对称。候选超时、触发相反极端或处于 cooldown 时被清除。

### 1.3 方向

- `buy_first`：BUY fill 后等待 SELL，适合先低吸再卖出可用底仓的研究语义；
- `sell_first`：SELL fill 后等待 BUY，适合先卖底仓再低位买回；
- 第一轮每个方向最多 `max_round_trips`，防止噪声过度交易。

状态机保证信号交替，禁止连续 BUY/SELL 导致无法解释的持仓。

## 2. 置信度

第一轮使用可解释的规则分数，不宣称是真实概率：

```text
extremity_score   = normalized |zscore threshold excess|
rsi_score         = normalized oversold/overbought strength
vwap_score        = normalized VWAP deviation
reversal_score    = current reversal body / rolling volatility
confidence        = weighted clipped sum [0, 1]
```

返回字段必须命名 `confidence` 并附 `confidence_kind=rule_score_v1`，避免前端把它误解为已校准概率。后续 ML 通过 calibration 后再升级契约版本。

## 3. 成交模型

### 3.1 NextBarOpenExecution

- decision 在 bar `i` close 后产生；
- fill 使用 bar `i+1` open；
- buy 滑点向上，sell 滑点向下；
- fill price 四舍五入到 0.01；
- 数量按配置，默认 100 股；
- 最后一根 decision 标记 `unfilled`。

### 3.2 成本

配置：

```text
commission_rate
minimum_commission
stamp_duty_rate_on_sell
transfer_fee_rate
slippage_bps
quantity
```

第一轮默认值只用于研究，必须允许用户修改。成本在 fill 和 trade pair 中拆分记录，不只给净值。

### 3.3 配对

同一 replay 内按状态机天然配对：

- buy_first：BUY -> SELL；
- sell_first：SELL -> BUY。

报告包含：gross pnl、总成本、net pnl、return pct、holding bars、MAE、MFE。未配对成交单独列出，不算作已完成 round trip。

## 4. Replay 数据结构

```json
{
  "run_meta": {
    "run_id": "t-wb-...",
    "engine_version": "causal_mean_reversion_v1",
    "security_id": 1,
    "symbol": "600183",
    "trade_date": "2026-07-29",
    "period": "min5",
    "source": "baostock",
    "persistence_mode": "ephemeral"
  },
  "bars": [],
  "signals": [],
  "fills": [],
  "trades": [],
  "summary": {},
  "quality": {}
}
```

`ephemeral` 模式的 replay/report 不调用任何 strategy result sink，也不把 bars 复制到新的持久化表。响应在前端内存中展示，页面刷新即释放。日志只记录 run_id、耗时、数量和错误等操作元数据，不记录完整行情或信号 payload。

Signal 最少包含：

```text
signal_id, side, decision_time, decision_price,
confidence, confidence_kind, reason_codes,
feature_snapshot, status, fill_id
```

Fill 最少包含：

```text
fill_id, signal_id, side, fill_time, raw_price,
fill_price, quantity, commission, stamp_duty,
transfer_fee, slippage_cost, total_cost
```

## 5. 防未来函数测试

对固定 bars：

1. 全量计算特征；
2. 对每个 `i` 用 `bars[:i+1]` 单独计算；
3. 比较全量位置 `i` 与前缀末尾值；
4. 比较截至 `i` 的 signal 集合；
5. 修改 `bars[i+1:]`，确认 `<=i` 的 features/signals 完全不变。

该测试是 signal engine 发布的硬门槛。

## 6. 单日统计

- bars count、missing/duplicate/zero-volume bars；
- signal/fill/unfilled count；
- completed round trips；
- net pnl、return pct、win/loss count、win rate；
- gross profit/loss、profit factor；
- average pnl、average holding bars；
- max adverse/favorable excursion；
- first/last signal time；
- no-signal reason（warmup、无候选、候选未确认等）。

## 7. 批量报告

### 7.1 输入展开

```text
security_ids x trading_dates
```

第一轮同步执行并限制最大组合数，防止 HTTP 请求失控。大规模任务后续转 TaskEngine campaign。

### 7.2 输出

- `overall`：全体完成交易统计；
- `by_security`：每只股票聚合；
- `by_day`：每个证券日的摘要；
- `failures`：身份、无数据、质量或运行失败；
- `config`：完整冻结的信号与成交配置；
- `generated_at/engine_version`。
- `persistence_mode=ephemeral`，表明报告未保存。

### 7.3 核心指标

```text
total_days
days_with_signal
signal_coverage
completed_trades
win_rate
net_pnl
average_trade_pnl
profit_factor
max_daily_drawdown / worst_day_pnl
```

收益为 0 的交易既不算 win 也不算 loss。没有完成交易时 profit factor 返回 NULL，而不是无穷大。

## 8. 事后参考点

Oracle 层后续独立实现，输出灰色 local-low/local-high markers 和可行最优净收益。它必须：

- 使用不同 artifact key；
- UI 默认弱化显示；
- 禁止被 signal engine import；
- 报告明确标注 hindsight only。

第一轮可以不实现 oracle，不影响因果回放交付。

## 9. 后续机器学习

规则基线稳定后：

1. 规则生成候选点；
2. triple-barrier/first-touch 生成未来标签；
3. 按时间 walk-forward，标签窗口重叠处 purge/embargo；
4. Logistic/LightGBM 过滤候选点；
5. 概率校准；
6. 置信度阈值控制 coverage；
7. champion/challenger 与实时 shadow。

未通过扣费后样本外收益、置信度单调性和多市场状态稳定性门槛，不进入实时阶段。
