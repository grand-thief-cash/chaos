# Artemis 股票行情下载（baostock）功能规划

## 目标
- 在 Artemis 内通过 baostock SDK 下载股票行情数据（支持日/周/月/分钟线）。
- 通过 PhoenixA 进行数据存储与查询。
- 使用现有任务系统：父任务（Orchestrator）+ 子任务（Child）。

## 现有依赖与可用能力
- Artemis 任务框架：`BaseTaskUnit` / `ChildTaskUnit` / `OrchestratorTaskUnit`。
- PhoenixA 股票列表 API（查询所有股票 code）：
  - `GET /api/v1/zh/stock_list/`（支持分页与过滤）
  - `GET /api/v1/zh/stock_list/count`（可用于分页总数）
- Artemis -> PhoenixA 客户端：`artemis.core.clients.phoenixA_client.PhoenixAClient`
- baostock SDK：`artemis.core.sdk.baostock_sdk.BaostockSDK`

## 需求拆解
1. 新增父级任务：负责规划子任务与动态参数加载。
2. 父任务在 `load_dynamic_parameters` 阶段：
   - 从 PhoenixA 拉取所有股票 code（必要时分页）。
   - 查询 PhoenixA 中每只股票的最近一次更新日期（需要新增 PhoenixA 查询接口）。
3. 生成每只股票的子任务参数：
   - `start_date = max(config.start_date, last_update_date) + 1*interval`
   - `end_date` 可由任务入参，若为空默认当天
4. 子任务执行：调用 `bs.query_history_k_data_plus` 拉取行情。
5. 子任务 `sink`：调用 PhoenixA 写入行情数据（需要新增 PhoenixA CRUD）。
6. 支持 `frequency + adjustflag` 作为任务变体（task.yaml）。
7. 分钟线本次不实现，但保留接口与数据设计可扩展性。

## Artemis 侧设计
### 1) 新任务结构
- `OrchestratorTaskUnit`：
  - 文件建议：`artemis/task_units/zh/stock_kline_parent.py`
  - 核心逻辑：
    - `load_dynamic_parameters` 拉取 code 列表 + last_update_date
    - `plan()` 输出每只股票的子任务 spec
- `ChildTaskUnit`：
  - 文件建议：`artemis/task_units/zh/stock_kline_child.py`
  - `execute()` 调用 baostock 下载
  - `sink()` 调用 PhoenixA 批量 upsert

### 2) PhoenixA 交互点（Artemis 客户端）
- 复用 `PhoenixAClient`，新增方法：
  - `list_stock_codes(exchange, limit, offset)` 或 `list_stocks`（分页抓取全部）
  - `get_last_kline_date(code, frequency, adjustflag)`
  - `batch_upsert_kline(records, dataset_key)`

### 3) task.yaml 配置
新增任务配置（示例结构）：

- task_code: `stock_kline_download`
- match 维度：`frequency` + `adjustflag`
- config：
  - `fields`: `[date,code,open,high,low,close,preclose,volume,amount,turn,pctCh,peTTM,pbMRQ,psTTM,pcfNcfTTM]`
  - `adjustflag`: `1|2|3`
  - `interval`: `d|w|m|5|15|30|60`
  - `start_date`: `20100101`

> 备注：分钟线本次不实现，但保持字段/接口可扩展。

### 4) 数据流
1. 父任务 `load_dynamic_parameters`：
   - PhoenixA 拉取 stock_list（code + exchange）。
   - PhoenixA 查询每只股票最近一次的 kline 日期。
2. 父任务 `plan()`：为每只股票输出子任务（含调整后的 start_date）。
3. 子任务 `execute()`：调用 baostock 拉取 kline。
4. 子任务 `sink()`：调用 PhoenixA 批量 upsert。

## PhoenixA 侧设计（建议）
> PhoenixA 目前仅有 stock_list 相关 CRUD，需要新增行情数据存储。

### 1) 数据模型/表设计（确认方案）
- 按 **频率 + 复权** 拆分表：
  - `stock_zh_a_hist_daily_none`
  - `stock_zh_a_hist_weekly_hfq`
  - `stock_zh_a_hist_monthly_qfq`
  - （分钟线预留：`stock_zh_a_hist_min_5_none` 等）
- 主键：`(code, trade_date)`，不设置自增 id。
- 索引建议：
  - `PRIMARY KEY (code, trade_date)`
  - 若存在“只按日期范围扫描”的查询，再加 `KEY idx_trade_date (trade_date)`
  - 不需要再单独添加 `(code, trade_date)` 的索引，因为主键已覆盖
- 分区建议：
  - 可按 `trade_date` 年度分区（`PARTITION BY RANGE (YEAR(trade_date))`）。

### 2) 统一 CRUD 逻辑
- DAO/Service 复用：参数化表名/字段集合（如 `dataset_key`）。
- API 设计建议：
  - `POST /api/v1/zh/stock_kline/{dataset}/batch_upsert`
  - `GET /api/v1/zh/stock_kline/{dataset}/last_date?code=...`
  - `GET /api/v1/zh/stock_kline/{dataset}/list?code=...&start=...&end=...`
- `last_date` 语义：
  - 以“某 dataset 某 code 的最新交易日”为准；无数据返回空。

### 3) 批量写入策略（性能考虑）
- 首次全量拉取：允许大批量 `batch_upsert`（建议 200~500/批）。
- 日常更新（~5k code / 天）：
  - 默认 **子任务直接 sink**，避免父任务聚合导致内存压力。
  - 可选：父任务提供“有界聚合”能力（例如每累计 N 支股票或 M 行就 flush 到 PhoenixA）。
  - 仅在行数很小且网络调用成本明显时，才启用父任务聚合。
- 具体策略：实现时增加 `sink_mode`（child/parent/hybrid）与 `parent_batch_threshold`。

## 边界与异常处理
- PhoenixA 不可用：父任务应失败并记录错误（保持一致性）。
- 无 last_update_date：使用配置中的 `start_date`。
- 任务频率不匹配字段：需在子任务中做字段映射或按频率切换。
- 分页拉取 code：处理 stock_list 大量数据（分页 + limit/offset）。
- 任务可重入：基于 `last_update_date` + upsert 保障幂等。

## 待确认问题（需要你确认）
1. `last_update_date` 当前不做批量接口，单条查询 + 索引优化即可（5k code 可接受）。

## 下一步
- 你确认以上设计后，我会开始：
  1) 更新 `task.yaml`。
  2) 新增 Artemis 任务（parent/child）。
  3) 扩展 PhoenixA 的模型/DAO/Service/Controller + 路由 + openapi。
  4) 添加最小可运行的测试与样例调用。
