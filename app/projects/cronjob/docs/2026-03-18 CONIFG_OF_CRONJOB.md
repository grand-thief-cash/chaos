# CRONJOB CONFIG


Task: STOCK_ZH_A_HIST_PARENT

| Fields     | Type   | Required | Value                       |
|------------|--------|----------|-----------------------------|
| adjust     | string | T        | none/qfq/hfq                |
| period     | string | T        | daily/monthly/weekly/...    |
| code_list  | string | F        | 000001,000002               |
| exchange   | string | F        | SH,SZ,BJ                    |
| start_data | string | F        | 2026-01-01                  |
| end_data   | string | F        | 2026-12-31                  |
| fields     | string | F        | date,code,open,high,low,... |

```json
{"code_list":"000001", "exchange": "SH,SZ,BJ", "period": "daily", "adjust": "none","start_date":"2026-01-01"}
```

---

Task: BACKTRADER_CAMPAIGN

Cronjob 配置参数（body_template 字段）：

| Fields              | Type     | Required | Default       | Description                                        |
|---------------------|----------|----------|---------------|----------------------------------------------------|
| mode                | string   | T        | -             | 回测模式，Phase 1 仅支持 `historical`                |
| market              | string   | T        | -             | 市场标识，如 `CN_A`（A股）                           |
| timeframe           | string   | T        | -             | K线周期，如 `daily`                                 |
| adjust              | string   | F        | `nf`          | 复权方式：`nf`(不复权) / `qfq`(前复权) / `hfq`(后复权) |
| strategy_code       | string   | T        | -             | 已注册的策略代码，如 `sma_cross`                     |
| data_provider_code  | string   | T        | -             | 数据源标识，如 `phoenixa_hist_daily`                 |
| analyzer_profile    | string   | T        | -             | 分析器配置，如 `default_hist_v1`                     |
| symbols             | string[] | F*       | -             | 股票代码列表，如 `["000001","600000"]`，与 universe_code 二选一 |
| universe_code       | string   | F*       | -             | 股票池代码，如 `ALL`，与 symbols 二选一              |
| start_date          | string   | T        | -             | 回测起始日期，格式 `YYYY-MM-DD`                      |
| end_date            | string   | T        | -             | 回测结束日期，格式 `YYYY-MM-DD`                      |
| cash                | float    | F        | `100000.0`    | 初始资金                                            |
| commission          | float    | F        | `0.0`         | 手续费率                                            |
| strategy_params     | object   | F        | `{}`          | 策略参数，覆盖策略默认参数，如 `{"fast":3,"slow":8}`  |
| parameter_grid      | object[] | F        | -             | 参数网格，用于批量回测，如 `[{"fast":3},{"fast":5}]`  |
| persist_artifacts   | string[] | F        | -             | 需要持久化的制品类型                                 |

persist_artifacts 可选值：

| Artifact       | Description                                                      |
|----------------|------------------------------------------------------------------|
| `analyzers`    | backtrader Analyzer 分析结果（收益率、夏普比率、最大回撤等）        |
| `trades`       | 交易记录明细（买卖信号、订单状态、成交价格、盈亏）                   |
| `equity_curve` | 逐 bar 权益曲线（每根 K 线的资金和总资产变化）                       |
| `plot_manifest`| 绘图元数据清单（图表布局、指标配置，供前端渲染）                      |
| `plot_series`  | 绘图时序数据（价格序列、指标线、买卖标记点）                          |

Cronjob 配置参数（非 body_template 字段）：

| Fields             | Value                                  | Description                                |
|--------------------|----------------------------------------|--------------------------------------------|
| target_service     | `artemis`                              | 下游服务标识                                |
| target_path        | `/tasks/run/BACKTRADER_CAMPAIGN`       | Campaign 编排器入口                         |
| method             | `POST`                                 | HTTP 方法                                   |
| exec_type          | `SYNC`                                 | 同步执行，等待回测完成后返回结果              |
| concurrency_policy | `SKIP`                                 | 上一轮未完成时跳过本次执行                    |
| overlap_action     | `SKIP`                                 | 防止重叠执行                                 |
| failure_action     | `RUN_NEW`                              | 上轮失败后下一轮正常调度                      |
| max_concurrency    | `1`                                    | 单任务最大并发数                              |

示例 — 单股票 SMA 金叉回测：

```json
{
  "mode": "historical",
  "market": "CN_A",
  "timeframe": "daily",
  "adjust": "nf",
  "strategy_code": "sma_cross",
  "data_provider_code": "phoenixa_hist_daily",
  "analyzer_profile": "default_hist_v1",
  "cash": 100000.0,
  "commission": 0.001,
  "symbols": ["000001"],
  "start_date": "2020-01-01",
  "end_date": "2026-04-01",
  "persist_artifacts": ["analyzers", "trades", "equity_curve", "plot_manifest", "plot_series"]
}
```

示例 — 全市场 SMA 参数网格回测：

```json
{
  "mode": "historical",
  "market": "CN_A",
  "timeframe": "daily",
  "strategy_code": "sma_cross",
  "data_provider_code": "phoenixa_hist_daily",
  "analyzer_profile": "default_hist_v1",
  "cash": 100000.0,
  "commission": 0.001,
  "universe_code": "ALL",
  "start_date": "2020-01-01",
  "end_date": "2026-04-01",
  "parameter_grid": [
    {"fast": 5, "slow": 20},
    {"fast": 10, "slow": 30},
    {"fast": 20, "slow": 60}
  ],
  "persist_artifacts": ["analyzers", "trades"]
}
```