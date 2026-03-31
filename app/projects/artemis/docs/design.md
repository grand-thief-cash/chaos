# Artemis Python 多源异构数据拉取项目架构设计（调整：移除集中参数解析器，补充 Sources 说明，限定第一期范围）

## 变更摘要（2025-11-12）
- 移除集中 ParameterResolver 方案：每个 TaskUnit 自行完成参数获取/校验/补齐。
- 扩展 Sources 章节：阐述为何需要 Source 抽象（协议隔离/复用/测试/限流分页规范化）。
- 限定第一期范围：仅实现 HTTP Sink（带 traceparent 传播）、基础日志、简单错误处理、最小 Trace 生成/解析；不实现统计、插件、执行模式隔离、Kafka/gRPC/S3、重试/限流（保留 TODO）。
- 日志模块采用可配置 JSON/console 输出 + trace_id/span_id/caller 字段，参考 Go zap 配置（level/format/output/file轮转 设计预留）。
- 配置管理章节细化：server / logging / telemetry / tasks_defaults / outputs / http_client 超时。

## 1. 核心范围 (Phase 1)
- HTTP 入口：/tasks/{code}/run 触发 TaskUnit 同步执行并返回结果。
- TaskUnit：自行处理参数 -> 拉取数据（可内联或借助 Source）-> 处理 -> 发送 (HttpSink)。
- Sources：当前示例只给出 REST Source 占位，可选使用；任务可直接写 fetch 逻辑但推荐逐步迁移到 Source 抽象。
- Telemetry：轻量 trace 上下文（traceparent 解析 + 生成新 span id），未接入 OTLP 导出（留接口）。
- Logging：结构化 JSON（或 console），字段统一，支持 trace 关联。
- 错误：统一捕获，转换为结构化响应与日志。无重试机制（后续）。

## 2. Sources 抽象价值（为什么保留）
即便第一期任务可直接写 fetch 逻辑，抽象 Source 带来：
1. 协议解耦：REST / WebSocket / SDK / Crawler 行为差异集中在实现，不污染 TaskUnit。
2. 复用与组合：多个任务共享同一第三方接口调用策略（签名、分页、速率限制策略未来易加）。
3. 测试隔离：可对 Source 打桩（mock fetch）而不触及任务处理逻辑。
4. 分页/流式统一：约定 fetch(params, ctx) 可返回迭代器/生成器；未来可加入 async 版本只改基类。
5. 观测一致性：后续在 Source 基类集中加入计时、错误分类、trace child span，而不修改所有任务。
当前阶段：仅提供 BaseSource + RestSource 占位；分页/限流/重试保留 TODO 注释。

## 3. 参数处理策略（更新）
- 无全局 ParameterResolver 管线。
- 每个 TaskUnit.prepare_params:
  1. 读取配置默认值（task_defaults）
  2. 合并调用入参
  3. 校验/补齐（自行使用 pydantic 可选）
  4. 记录（敏感字段手动掩码 TODO）
- 未来若发现多任务重复，可再抽象局部解析工具，而非预置复杂框架。

## 4. Http Sink (Phase 1 目标)
- 发送批列表为 JSON 数组
- 在 Header 注入 W3C traceparent（继承当前 trace_id，新生成子 span id）
- 简单错误捕获 -> 日志 error，不重试（TODO）。

## 5. Telemetry (轻量实现)
- 解析入站 traceparent: `00-<trace_id>-<span_id>-flags` 若无则新建 trace_id。
- 创建当前请求 span_id（task.trigger）。
- HttpSink 发出新 span id（emit.http_sink）。
- 结构：不导出至 OTLP，仅本地构造，保留接口 `telemetry/tracing.py`：
  - `extract_trace(headers)` 返回 TraceContext(trace_id, parent_span_id)
  - `new_span(trace_id, parent_span_id, name)` 生成 (span_id, name)

## 6. Logging（参考 Go zap 配置）
字段：timestamp, level, logger, caller, message, trace_id, span_id, task_code, error(optional)
配置：
```
logging:
  level: INFO            # DEBUG/INFO/WARN/ERROR
  format: json           # json | console
  output: stdout         # stdout | stderr | file
  file:
    path: logs/runner.log
    max_size_mb: 50
    max_backups: 5
    max_age_days: 7
  include_caller: true
```
Phase 1 不实现文件轮转（TODO）。

## 7. 错误处理
- 捕获 TaskUnit.run 抛出的异常 -> 记录 error 日志 + HTTP 500 响应结构：{"error": {"type":..., "message":...}, "trace_id":...}
- 细分类（SourceError/SinkError/TaskError）仅做名称标记，不影响控制流；无重试。
- TODO：后续加入 Retryable/Fatal 分类与策略。

## 8. 配置管理（Phase 1 明确定义）
`config/config.yaml` 示例：
```
server:
  host: 0.0.0.0
  port: 8000
logging:
  level: INFO
  format: json
  output: stdout
telemetry:
  enabled: true
  service_name: artemis
  sampling: always
http_client:
  timeout_seconds: 5
  verify_ssl: true
  headers: {}
task_defaults:
  pull_stock_quotes:
    symbols: ["AAPL", "TSLA"]
    start: "2025-11-01"
output_defaults:
  pull_stock_quotes:
    sinks: ["http"]
    http_endpoint: "https://example.com/ingest"
```
加载策略：启动首次访问 config 获取并缓存；可支持环境变量覆盖（TODO）。

## 9. TODO 汇总（未在 Phase 1 实现）
- 任务统计细粒度（records_total/errors_total/batch_size）
- 执行模式隔离（线程/进程）
- Kafka / gRPC / S3 sinks
- 限流 / 重试 / 断路器
- OTel Exporter / Metrics
- 插件机制 / 动态加载
- 参数敏感字段掩码
- Source 分页与 async 支持
- 日志文件轮转

其余章节（未来扩展、风险、测试策略、插件等）保持原设计但暂不实现。

## BaseTaskUnit 方法详解（Phase 1 实际语义）

下表与后续小节详细描述 BaseTaskUnit 的每个生命周期方法。所有方法都接收 `ctx: TaskContext`，除特别说明外不应修改 `ctx.trace_id` 与 `ctx.span_id`。

| 方法 | 触发阶段顺序 | 主要职责 | 输入/输出 | 允许的副作用 | 典型错误 | 是否可选覆写 |
| ---- | ------------ | -------- | --------- | ------------- | -------- | ------------- |
| `prepare_params` | 1 | 合并默认参数与请求入参，做轻量校验 | 使用 `ctx.incoming_params`；写入 `ctx.params` | 读取配置/简单本地计算 | 参数缺失、类型不符 | 是 |
| `build_sources` | 2 (逻辑调用点在 `fetch` 前) | 构建数据来源对象列表 | 读取 `ctx.params`；返回 Source 列表 | 可缓存客户端实例 | 构造参数非法 | 是 |
| `fetch` | 3 | 产生原始数据记录（迭代器/生成器） | 读取 `ctx.params`；产出记录 | 网络调用 / I/O | 超时、网络错误 | 是（必须） |
| `process` | 4 | 对 `fetch` 结果进行转换、过滤、聚合 | 输入迭代器；返回 List 或 Iterable | 纯内存操作（推荐） | 数据格式错误 | 是 |
| `decide_sinks` | 5 | 根据任务/参数决定输出通道集合 | `ctx.params` 与配置 | 初始化 sink 实例 | 不支持的 sink 类型 | 是 |
| `emit` | 6 | 将处理后的数据批量发送到各 sink | List[记录] | 网络 I/O | 下游拒绝、序列化失败 | 是（建议覆写） |
| `finalize` | 7 | 收尾、统计、资源清理 | 访问 `ctx.stats` 更新状态 | 关闭内部对象 | 清理失败（通常忽略） | 是 |
| `run` | 封装整体 | 串起上述调用；可自定义执行拓扑 | 无直接返回（返回值由 TaskEngine 组装） | 调整流程、细粒度拆批 | 任意内部异常 | 可覆写（需保持语义） |

### 1. prepare_params(ctx)
职责：
- 读取任务默认参数（`task_defaults`）与外部触发请求里的 `params` 合并。
- 做最小必要的合法性校验（如必填字段、基本类型）。
- 可以推导/补齐派生参数（例如根据 `start` 自动填 `end=今天`）。
- 将最终字典写入 `ctx.params`。

注意点：
- 不做重逻辑（复杂远程依赖调用放在 fetch 前也可，但最好包装成 Source）。
- 避免记录敏感值（后续会加掩码策略）。

### 2. build_sources(ctx)
职责（扩展详解）：
- “Source” 是对具体数据获取协议的一个对象封装（REST API、WebSocket、第三方 SDK、爬虫页面解析等）。它将底层请求细节（URL 组装、认证、分页、重试、速率限制、连接管理）与任务的业务逻辑分离。
- build_sources 的目的，就是根据本次任务的参数构造出一个或多个 Source 实例列表，交给后续 `fetch` 阶段统一迭代。

为什么要先 build 而不是在 fetch 里直接写：
1. 关注点分离：TaskUnit 的 fetch 更聚焦“获取并产出记录”，而 Source 负责“怎么调用外部数据源”。
2. 多源组合：同一个任务可能需要同时从多个数据端抓取（如 股票行情 + 交易日历 + 新闻）；提前构建列表方便在 fetch 中统一遍历与合并。
3. 复用与测试：Source 可被多个不同任务复用；单元测试时可以替换为 MockSource，不动任务代码。
4. 生命周期管理：复杂长连接（WebSocket）或需要预热（SDK 客户端初始化）时，可在 build_sources 阶段集中初始化与缓存。
5. 动态策略：可以根据参数动态决定使用哪一类 Source（例如当 `params['realtime']=True` 选 WebSocket，否则选 REST）。

常见模式：
- 单源：返回一个列表只含单个 Source；fetch 直接 `yield from source.fetch()`。
- 多源串行：返回多个 Source，fetch 中依次迭代；数据顺序不敏感的场景（例如先基础信息后补充扩展字段）。
- 多源合并：返回多个 Source，fetch 中同时拉取（未来可并发）并对结果做合并/去重。
- 条件构建：根据参数/环境选择不同实现（测试环境用 MockSource，生产用真实 RestSource）。
- 分片构建：将大批量标的拆分生成多个 Source（例如每个 Source 负责一组 symbols，便于后续并发或限流控制）。

与 fetch 的分工：
- build_sources：只“构造对象和准备状态”，不发起实际网络 I/O。
- fetch：真正调用 Source.fetch 并生成记录流；处理分页、错误、重试（未来）。

示例：根据参数控制 Source 类型
```python
class QuotesTask(BaseTaskUnit):
    def build_sources(self, ctx):
        symbols = ctx.params.get('symbols', [])
        realtime = ctx.params.get('realtime', False)
        if realtime:
            return [WebSocketQuoteSource(symbols)]  # 假设后续实现
        return [RestPriceSource(symbols)]

    def fetch(self, ctx):
        for src in self.build_sources(ctx):
            yield from src.fetch(ctx.params, ctx)
```

示例：多源合并（行情 + 交易日历）
```python
class MarketTask(BaseTaskUnit):
    def build_sources(self, ctx):
        symbols = ctx.params.get('symbols', [])
        return [RestPriceSource(symbols), TradingCalendarSource()]
    def fetch(self, ctx):
        price_source, cal_source = self.build_sources(ctx)
        # 先产出交易日历（可能为后续过滤价格数据所需）
        calendar = list(cal_source.fetch(ctx.params, ctx))
        for rec in price_source.fetch(ctx.params, ctx):
            if rec.timestamp in calendar:  # 过滤非交易日
                yield rec
```

示例：按分片拆分 Source 提前为并发做准备（当前 Phase 1 不并发，只示意）
```python
class ShardedQuotesTask(BaseTaskUnit):
    SHARD_SIZE = 100
    def build_sources(self, ctx):
        symbols = ctx.params.get('symbols', [])
        shards = [symbols[i:i+self.SHARD_SIZE] for i in range(0, len(symbols), self.SHARD_SIZE)]
        return [RestPriceSource(shard) for shard in shards]
    def fetch(self, ctx):
        for src in self.build_sources(ctx):
            yield from src.fetch(ctx.params, ctx)
```

最佳实践：
- Source 构造轻量化：避免在 __init__ 中做耗时操作（连接建立可延迟到第一次 fetch 调用）。
- 参数下推：在 build_sources 中对公共参数（如 auth token）注入 Source，减少后续重复。
- 错误早发现：如果关键参数缺失（symbols 空），可在 build_sources 就抛出异常，而不是等到 fetch。
- 不做数据转换：数据清洗、过滤放到 process；build_sources 只管“准备访问通道”。

常见错误与规避：
| 场景 | 问题 | 规避 |
| ---- | ---- | ---- |
| 在 build_sources 就发 HTTP 请求 | 提前产生副作用，重载配置或重试困难 | 推迟到 Source.fetch 中再请求 |
| 构建超大数量 Source 对象 | 内存占用、迭代效率低 | 做分片但限制总 Source 数量；或在 fetch 中按需懒加载 |
| Source 内部持有不可重用的巨大对象 | 重复执行任务导致内存泄漏 | 设计清理方法（后续 finalize 可调用）或使用弱引用缓存 |
| 动态决定 sink 而放在 build_sources | 职责混淆 | sink 相关逻辑保持在 decide_sinks |

何时可不覆写 build_sources：
- 任务只需一个简单数据抓取，且协议逻辑极少；可以直接在 `fetch` 内部完成。
- 但是一旦出现第二类数据源、或需要分页/限流封装，就应迁移到独立 Source 并通过 build_sources 构造。

### 3. fetch(ctx)
职责：
- 作为“数据产生”阶段。返回值通常是一个可迭代对象：生成器 / 列表 / 迭代器。
- 可以：
  - 直接 `yield` 记录（流式）
  - 收集到本地列表再返回（小数据量）

建议：
- 单条记录对象统一为 pydantic 模型（如 `Record`）；若是原始结构可用 dict，在 `process` 中规范化。
- 处理分页：逐页调用第三方 API，分页边界出错要捕获并日志化。

错误处理：
- 抛出异常（如网络错误）会被 TaskEngine 捕获并转为结构化错误响应；如可预见的可恢复错误可先记录再跳过该页。

### 4. process(records, ctx)
职责：
- 纯数据层处理：映射字段、过滤无效记录、做轻量聚合或排序。
- 输出 List（Phase 1 中 emit 假设是可一次性遍历的集合）。

扩展：
- 后续可支持返回一个流式可迭代对象，Sink 自己分批（需要在 Sink 层调整）。

### 5. decide_sinks(ctx)
职责：
- 根据配置（`output_defaults`）与 runtime 参数（例如请求体里期望输出格式或 override）决定要使用的 sink 列表。
- 可在此添加：
  - 多 sink 分流（例如 http + 未来 kafka）
  - 动态调整输出端点（按 env / symbols / 数据量）

返回：
- Sink 实例列表（每个实例实现 `emit(List[Any], ctx)`）。

### 6. emit(processed, ctx)
职责：
- 调用 `decide_sinks` 获取 sink 实例列表并执行发送。
- 处理发送结果：日志记录成功数量 / 下游状态码 / 失败信息。

可覆写场景：
- 需要分批（batch size）发送。
- 需要多 sink 并行（后续引入并发工具时）。
- 需要在不同 sink 之间实现“优先 / 回退”策略（例如主 sink 失败后写备用存储）。

### 7. finalize(ctx)
职责：
- 补充统计数据（运行时长、记录数——后续 TODO）。
- 关闭本地资源、清理临时缓存对象。
- 可以设置 `ctx.stats['status']`（如 ok / partial / failed）。

不建议：
- 抛出致命异常；如清理失败只记录警告日志。

### 8. run(ctx)
默认实现执行顺序：
```
prepare_params -> fetch -> process -> emit -> finalize
```
覆写场景：
- 需要：分阶段增量提交（fetch 一批 -> process -> emit -> 下一批）。
- 双源对齐：交替从两个 Source 读取并合并按时间序排序后输出。
- 流式大数据：边 fetch 边 emit（减少内存峰值）。

覆写注意：
- 必须保证最终一定调用 `finalize`（建议使用 try/finally）。
- 如改变调用次序，要自我保证依赖前置关系仍成立（例如先构建参数再构建 Source）。

### 9. 典型实现模板（参考）
```python
class MyTask(BaseTaskUnit):
    def prepare_params(self, ctx):
        super().prepare_params(ctx)
        if 'symbols' not in ctx.params:
            raise ValueError('symbols required')

    def build_sources(self, ctx):
        return [RestPriceSource(ctx.params['symbols'])]

    def fetch(self, ctx):
        for src in self.build_sources(ctx):
            yield from src.fetch(ctx.params, ctx)

    def process(self, records, ctx):
        out = []
        for r in records:
            # 过滤价格为 0 的无效记录
            if getattr(r, 'price', 0) > 0:
                out.append(r)
        return out

    # emit 可复用基类；如需分批可覆写：
    # def emit(self, processed, ctx): ...
```

### 10. 异常与日志最佳实践
- 参数错误：`prepare_params` 直接抛出 ValueError，日志事件建议 `param_error`。
- 外部依赖（HTTP / SDK）错误：在 `fetch` 中捕获并包装为清晰 message（例如 `source_timeout`，含 endpoint、page 等字段）。
- 处理阶段错误：尽量定位到具体记录（添加 `record_index`），可选择跳过单条并继续后续。
- 输出阶段错误：记录下游响应（status_code, snippet），避免整个任务静默成功。

### 11. 幂等性与可重入
- TaskUnit 默认一次执行即完成，不做状态恢复；若任务可能被重复触发，需在 `prepare_params` 或 `emit` 中自行实现去重逻辑（如生成幂等键）。

### 12. 后续扩展点（预留）
| 未来能力 | 最佳插入点 | 说明 |
| -------- | ---------- | ---- |
| 分批策略 | emit/process | process 切片或 emit 内分批发送 |
| 限流     | fetch / Source | 在 Source 内部统一控制 QPS |
| 重试策略 | Source.fetch / Sink.emit | 装饰器或统一重试包装 |
| 指标采集 | run 包装 / 各阶段入口 | new_span 或计数器 |
| Trace 子 span | fetch / emit | new_span(trace_id, parent_span, name) |

## 13 更新：Cron 调用协议调整
- 调用请求体采用 `{"meta": A, "body": B}` 结构；A 包含 run_id/task_id/exec_type 等运行元数据，B 为任务业务参数（dict 或原始字符串）。
- 回调策略简化：不再有全局 mode/auto_finalize/节流配置；是否发送进度取决于任务代码自身调用 `ctx.callback.progress()`；终态回调需任务显式调用 `ctx.callback.finalize_success()` 或在异常时引擎调用 `finalize_failed()`。
- Artemis 配置只保留 `callback.override_host/override_port` 用于强制指定 CronJob 服务地址。

### 13.1 设计目标
为长周期 / 需阶段汇报进展的任务提供一个在 Artemis 内部易用、可选的回调机制, 将任务执行进度与最终结果异步通知给 CronJob 的 Run 管理 API (`run_controller.go`).

满足:
1. 易集成: TaskUnit 内一句 `ctx.callback.progress(...)` / `ctx.callback.finalize_success(...)` 即可。
2. 非侵入: 不使用回调时零开销 (NoopClient)。
3. 可靠性: 最终结果回调具备最少重试与明确日志; 进度支持节流 (throttle)。
4. 可观测: 透传 traceparent 到回调请求; 失败有结构化日志。
5. 安全: 支持令牌 / Header 注入, 避免伪造回调。
6. 顺序与状态契合 CronJob 当前 API 行为 (progress 接口允许 Running/CallbackPending; finalize 仅允许 CallbackPending)。

### 13.2 传入参数约定 (HTTP /tasks/{code}/run 请求体 params 内)
引入可选 `callback` 字段:
```json
{
  "params": {
    "symbols": ["AAPL"],
    "callback": {
      "override_host": "<host 可选>",
      "override_port": 9999
    }
  }
}
```
说明:
- `run_id` 与 `base_url` 同时存在才启用回调。
- 删除的旧参数：`mode`, `progress_min_interval_ms`, `auto_finalize`, `finalize_body_field`（统一交由任务实现控制进度与终态内容）。

### 13.3 Artemis 内部组件
新增 `CallbackClient` & `NoopCallbackClient`:
接口:
```python
class CallbackClient:
    def progress(self, current: int, total: int, message: str | None = None) -> bool: ...
    def finalize_success(self, code: int = 200, body: str | None = None) -> bool: ...
    def finalize_failed(self, error_message: str) -> bool: ...
    def finalize_timeout(self, error_message: str = 'callback_deadline_exceeded') -> bool: ...
```
返回值: bool 表示本次 HTTP 调用是否成功 (>=200 <300)。失败不抛异常, 仅记录日志。

内部字段:
- `run_id`
- `endpoints`: 拼接自 `base_url` -> progress: `"{base_url}/{run_id}/progress"`, finalize: `"{base_url}/{run_id}/callback"`
- `auth_header` + `auth_token`
- `mode`
- `progress_min_interval_ms`
- `last_progress_ts`
- `traceparent` (从当前 span 上下文提取, 若可用)
- `finalized` 标志避免重复 finalize

### 13.4 构建与注入生命周期
1. `TaskEngine.run` 在创建 `TaskContext` 后解析 `incoming_params.get('callback')`。
2. 若合法 -> 构建 `CallbackClient` 并 `ctx.callback = client`; 否则注入 `NoopCallbackClient`。
3. BaseTaskUnit 可选添加辅助方法:
```python
class BaseTaskUnit:
    def update_progress(self, ctx, current, total, message=None):
        if hasattr(ctx, 'callback'): ctx.callback.progress(current, total, message)
```
4. TaskEngine 在任务成功结束时: 若 `callback.mode` 包含 finalize 且 `auto_finalize=True` 且未明确调用 finalize -> 自动调用 `finalize_success`:
   - `body` 构建策略: 若 `finalize_body_field` 存在于 `ctx.stats` -> JSON 序列化该字段值; 否则使用汇总 JSON (如 `{"records_emitted": N, "status": ctx.stats.get('status','ok')}`)。
5. 失败时 (捕获异常): 若启用 callback 并 `mode` 含 finalize -> 调用 `finalize_failed(error_message)`。

### 13.5 进度上报策略
- 本地端校验: 若 `total==0 && current>0` 不发送 (与 CronJob 校验一致) 并记录 warn。
- 节流: 两次调用间隔 < `progress_min_interval_ms` -> 忽略除非 `current==total` (最终进度确保发送)。
- 日志字段: `event=callback_progress`, `run_id`, `current`, `total`, `percent`, `skipped_due_to_throttle`。
- 百分比计算: 若 `total>0` -> `current/total*100` 向下取整。

### 13.6 Finalize 回调策略
- 仅首次发送; 后续重复调用直接返回 False 不发 HTTP 并记录 warn。
- 成功日志: `event=callback_finalize_success`, code, run_id
- 失败日志: `event=callback_finalize_failure`, run_id, error, attempt
- 重试: finalize 系列方法进行最多 3 次指数退避 (500ms, 1s, 2s) 重试, 仅针对网络/5xx。4xx 不重试。
- 若最终失败: 记录 `event=callback_finalize_gave_up`, run_id。

### 13.7 Trace 透传
- 从 OpenTelemetry 当前 span 获取 `trace_id`/`span_id` 构建 W3C `traceparent` header: `00-{trace_id_hex}-{span_id_hex}-01`。
- progress & finalize 请求都带该 header, 便于 CronJob 侧日志/链路聚合。
- 若无法获取 (未启用 telemetry) 则忽略。

### 13.8 安全与鉴权
- 简单令牌 Header 注入; 配置来源优先顺序:
  1. `callback.auth_header` / `callback.auth_token` 参数
  2. 全局配置 `config.yaml` 增加可选:
     ```yaml
     callback:
       default_auth_header: X-Callback-Token
       default_token: "${CALLBACK_TOKEN:-}"   # 后续支持 env 覆盖
     ```
- 若存在 token 则附加; 否则匿名调用。

### 13.9 错误处理与回退
- 进度发送失败: 不影响主任务, 不重试, 仅 warn。
- Finalize 失败: 重试后仍失败 -> 任务仍返回本地成功/失败响应, 外部需通过轮询 `runs/{run_id}` 来发现状态未更新。
- 参数缺失: 缺少 run_id 或 base_url -> 自动降级到 NoopClient 并写 debug log (不报错)。
- 无效 finalize 时机 (CronJob 未处于 CallbackPending): 返回 400 -> 记录 warn 并不再重试。

### 13.10 Artemis HTTP 接口响应行为调整 (未来实现范围)
当启用 `mode=progress_and_finalize` 时, 初始 `/tasks/{code}/run` 响应建议改为:
```json
{
  "task_code": "pull_stock_quotes",
  "accepted": true,
  "run_id": 123456,
  "callback_mode": "progress_and_finalize"
}
```
原同步结构中的 `duration_ms` 与 `stats` 由 finalize 成功时通过 CronJob 
`/runs/{run_id}/callback` 内容 `body` 字段传递; 本地仍记录日志以便追踪。若后续需要向调用方立即返回初步统计, 可在响应里添加 `estimated_records`。

Phase 1 实现可保持现状 (仍同步返回完整结果) 并附加回调, 由使用方决定是否忽略同步结果。

### 13.11 使用示例
任务内部:
```python
class LongTask(BaseTaskUnit):
    def fetch(self, ctx):
        items = range(0, 1000)
        total = 1000
        for i in items:
            # ... do work ...
            if i % 100 == 0:
                ctx.callback.progress(i, total, message=f"processed {i}")
            yield {"index": i}

    def finalize(self, ctx):
        super().finalize(ctx)
        ctx.stats['status'] = 'ok'
        # 可选手动 finalize (若 auto_finalize=False)
        # ctx.callback.finalize_success(body=json.dumps(ctx.stats))
```
调用方 (CronJob 调度器) 期望顺序:
1. 创建 run 记录 -> 得到 run_id, 置状态 CallbackPending (或 Running 然后转 CallbackPending)。
2. POST Artemis `/tasks/{code}/run` 携带 `callback` 参数。
3. 监听回调: `POST {base_url}/{run_id}/progress` 若干次。
4. 结束: `POST {base_url}/{run_id}/callback` 标记 success/failed。

### 13.12 与 CronJob API 对应关系
| CronJob Endpoint | Artemis 调用方法 | 条件 | 请求体字段映射 |
| ---------------- | ---------------- | ---- | -------------- |
| `/runs/{id}/progress` | `CallbackClient.progress` | 任务执行中; 节流通过 | `{current,total,message}` |
| `/runs/{id}/callback` | `CallbackClient.finalize_*` | mode 包含 finalize & 未重复 | `{result, code, body, error_message}` |

`finalize_success` 发送:
```json
{"result":"success","code":200,"body":"{...}"}
```
`finalize_failed` 发送:
```json
{"result":"failed","error_message":"<detail>"}
```
`finalize_timeout` 发送:
```json
{"result":"failed_timeout","error_message":"callback_deadline_exceeded"}
```

### 13.13 可扩展点 (未来)
| 能力 | 规划 | 说明 |
| ---- | ---- | ---- |
| 进度细粒度指标 | ctx.stats 聚合 | records_processed / error_count |
| 多租户鉴权 | 令牌分层 | 不同任务使用不同 token |
| gRPC 回调 | 新 Client 实现 | 与 HTTP 并存, 接口抽象 CallbackTransport |
| 幂等防重 | 回调携带 request_id | CronJob 侧去重, Artemis 侧日志保留 |
| 自动退避进度 | 动态调节节流 | 根据失败/拥塞情况增大 interval |

### 13.14 风险与规避
| 风险 | 场景 | 规避 |
| ---- | ---- | ---- |
| finalize 重复发送 | 任务 finalize 与 auto_finalize 双重触发 | `finalized` 标志位 + 仅首次成功发送 |
| 进度洪泛 | 任务高频循环调用 | 节流参数 + 仅关键里程碑调用 |
| 回调阻塞主流程 | 网络超时阻塞 fetch | 使用短超时 (如 2s) + 异常吞掉仅日志警告 |
| CronJob 状态不匹配 | finalize 时 run 不在 CallbackPending | 检测 400 -> warn -> 停止重试 |
| trace 泄漏 | 外部伪造 traceparent | 不做安全敏感使用, 仅观测; 安全靠 token |

### 13.15 最小实现范围 (Phase 1 扩展)
- 新增 CallbackClient / NoopCallbackClient (HTTP 实现 + requests 简单封装)。
- `TaskContext` 增加 `callback` 属性。
- `TaskEngine.run` 构建并注入 + 成功/失败路径自动 finalize (可配置)。
- BaseTaskUnit 保持不变; 示例任务可展示 progress 使用。
- 不修改现有同步响应结构 (可选后续迭代)。

### 13.16 验收标准
1. 未传 callback 参数时行为与当前完全一致。
2. 传递合法参数时日志含 `callback_progress` 与 `callback_finalize_success` 事件。
3. 进度节流生效 (连续快速 progress 仅发送首个与最终)。
4. finalize 失败时进行重试, 超过次数后放弃但任务仍返回本地成功结构。
5. traceparent header 出现在回调请求 (可通过抓包或 CronJob 侧日志确认)。

---
