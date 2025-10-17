# Infrastructure

> 本文档详细说明 Go Infra 子项目的架构设计、模块职责、组件关系、生命周期、配置规范、使用方式、扩展模式与最佳实践。
>
> This document is a definitive guide to the Go infrastructure layer: architecture, modules, components, lifecycle, configuration, usage, extension and best practices.

---

## 目录 (Table of Contents)
1. 背景 & 设计目标 (Background & Goals)
2. 架构总览 (High-Level Architecture)
3. 核心模块职责 (Core Modules Responsibilities)
4. 组件模型 (Component Model)
5. 依赖与生命周期 (Dependencies & Lifecycle)
6. Registry 机制 (Self-Registration Builders)
7. 配置系统 (Configuration System)
8. 组件目录与配置详解 (Component Catalog & Config Fields)
9. 启动流程 (Boot & Run Flow)
10. 优雅停机 (Graceful Shutdown / Windows 支持)
11. 健康检查 & 监控 (Health / Metrics / Telemetry)
12. 测试与可替换性 (Testing & Replace)
13. 扩展示例：新增组件 (How to Add a Component)
13.1 用户自定义业务组件 (taskDao / taskService)
13.2 使用 App.RegisterCustomBuilder 动态注册组件
13.3 使用 ProvideComponent 直接提供实例
13.4 Service 业务服务组件示例 (依赖多个 DAO / 分层依赖实践)
14. 常见错误与排查 (Troubleshooting)
15. 环境变量与运行参数 (Environment Variables)
16. 最佳实践 (Best Practices)
17. 未来增强路线 (Future Enhancements)

---
## 1. 背景 & 设计目标
| 目标 | 说明 |
|------|------|
| 模块化 | 各基础设施能力（日志、HTTP、gRPC、DB、缓存、监控）独立、按需启用 |
| 可组合 | 组件之间声明依赖，由框架统一拓扑排序启动/停止 |
| 自描述装配 | 组件自注册 (registry + `init()`)，新增能力无需修改集中式启动文件 (OCP) |
| 可测试 | 支持在激活前替换组件，实现依赖隔离测试 (`Container.Replace`) |
| 确定性 | 启动顺序、注册顺序、失败回滚策略全部确定且可预测 |
| 平台友好 | Windows / *nix 均支持优雅停机，Windows 控制台事件捕获 |
| 可 observability | Prometheus 指标 + Telemetry (Tracing/OTLP/Stdout) 组件内聚 |

---
## 2. 架构总览
```
+-------------------- Application Layer --------------------+
|                      application.App                      |
|  - parse env & config path                                 |
|  - load & validate config                                  |
|  - trigger registry.BuildAndRegisterAll                    |
|  - delegate start/stop to LifecycleManager                 |
+------------------------+----------------------------------+
                         v
+-------------------- Core Layer ---------------------------+
|  Container  |  LifecycleManager  |  Hooks Manager         |
|   - DI map  |  - start/stop seq  |  - phase -> hooks      |
|   - dep topo|  - rollback on fail|  - priority ordering   |
+-------+-------------+------------+------------------------+
        |             | (uses hooks) 
        v             v
+-------------------- Components Layer ---------------------+
| logging | http_server | http_clients | grpc_server | ...  |
|  each: config struct + builder + component impl           |
|  declare Dependencies() -> other component names          |
+-----------------------------------------------------------+
```

---
## 3. 核心模块职责 (Responsibilities & Boundaries)
(与原表一致并补充细节)

| 模块 | 职责 | 关键点 | 不做的事 |
|------|------|--------|----------|
| `application.App` | 启动编排入口 | 只关心“何时”而非“如何”创建组件 | 不直接 new 具体组件 |
| `registry` | 维护 name->BuilderFunc；按名字排序构建 | builder 返回 (enabled bool)；失败立即终止 | 不做启动 / 停止 |
| `core.Container` | 保存组件实例；依赖完整性校验；拓扑排序 | 支持 `Replace` 用于测试 | 不管理生命周期细节 |
| `core.LifecycleManager` | Start/Stop 顺序、钩子执行、失败回滚 | 启动前调用 `ValidateDependencies` | 不解析配置 / 不创建组件 |
| `hooks.Manager` | 生命周期四阶段 hook 注册与调度 | 优先级整数越小越先 | 不包含业务逻辑 |
| `components/*` | 各自协议/资源初始化、内部健康逻辑 | Start 时才做 I/O | 不感知全局结构 |
| `config/*` | 读取/反序列化/结构校验/未来 env merge | 可添加缺省填充 | 不创建资源连接 |

> 详见下节组件模型与生命周期说明。

---
## 4. 组件模型 (Component Model)
接口：
```
type Component interface {
  Name() string
  Start(ctx context.Context) error
  Stop(ctx context.Context) error
  HealthCheck() error
  Dependencies() []string
  IsActive() bool
}
```
规范：
- Start 必须做到“幂等多次调用只激活一次/或快速返回错误”。
- Stop 忽略已经停止状态，避免二次错误。
- HealthCheck 语义：仅在 `IsActive()==true` 时保证核心依赖可用；未激活时可返回错误或特定 sentinel。
- Dependencies 列出硬依赖（缺失即无法启动）。软依赖由组件在 Start 中自行探测并降级。
- BaseComponent 提供 active 状态字段 & 默认 HealthCheck；业务组件可组合嵌入。

状态流转（简化）：
```
Registered -> (Start OK) -> Active -> (Stop) -> Inactive
                      (Start Fail) -> Error + Rollback others
```

---
## 5. 依赖与生命周期 (Dependencies & Lifecycle)
启动顺序 = `container.ValidateDependencies()` 得到的拓扑序列。校验包括：
1. 缺失依赖收集：若 A 声明依赖 B 但 B 未注册 => 启动前失败。
2. 环检测：DFS during topo 排序发现回路即失败。
3. 顺序确定性：先按组件名排序再 DFS，保证相同集合顺序一致。

启动算法：
```
validate deps -> ordered components -> foreach:
  ctx = timeout wrapper
  comp.Start(ctx)
  if error: (a) attempt comp.Stop if partially active
            (b) reverse-started-list Stop
            (c) return error
```
停止算法：
```
resolve order (topo) -> reverse iterate; only active components Stop
hooks: before_start, after_start, before_shutdown, after_shutdown
```

Hooks 优先级：数值越小越先执行。失败立即中断当前阶段并返回错误（启动阶段）。

---
## 6. Registry 机制 (Self-Registration)
Builder 签名：
```
type BuilderFunc func(cfg *config.AppConfig, c *core.Container) (enabled bool, comp core.Component, err error)
```
约束：
- “纯” 构建：不做外部 I/O；仅准备内存结构和必要的函数闭包。
- enabled=false 或 comp=nil => 跳过注册。
- err!=nil => 视为 fatal，App 启动终止。
- 注册表按组件名排序，提供确定性。

示例（Logging 已实现）：
```
func init(){
  registry.Register(consts.COMPONENT_LOGGING, func(cfg *config.AppConfig, c *core.Container)(bool, core.Component, error){
    if cfg.Logging==nil || !cfg.Logging.Enabled {return false,nil,nil}
    comp, err := logging.NewFactory().Create(cfg.Logging)
    if err!=nil {return true,nil,err}
    return true, comp, nil
  })
}
```

---
## 7. 配置系统 (Configuration System)
组成：`Loader` + `Validator` + `ConfigManager` + `schema.go`。

流程：
1. Loader 读取 YAML / JSON (根据扩展名)。
2. 反序列化到 `AppConfig`。
3. (未来) 合并环境变量覆盖；当前留空位。
4. Validator 基础合法性校验（文件存在、结构非空）。
5. 成功后 `ConfigManager.appConfig` 可供组件 builder 使用。

文件选择逻辑：
- env 为空时默认 `development`。
- configPath 为空时默认 `config.yaml`。
- 支持 `.yaml` / `.yml` / `.json`。

示例顶层结构 (YAML)：
```yaml
app_info:
  app_name: example-service
  env: development
logging:
  enabled: true
  level: info
  format: json
  output: stdout
http_server:
  enabled: true
  address: ":8080"
  enable_health: true
  enable_pprof: false
prometheus:
  enabled: true
  address: ":9090"
  path: /metrics
telemetry:
  enabled: true
  exporter: stdout
mysql:
  enabled: true
  data_sources:
    main:
      host: 127.0.0.1
      port: 3306
      user: root
      password: secret
      database: appdb
redis:
  enabled: true
  mode: single
  addresses: ["127.0.0.1:6379"]
```

---
## 8. 组件目录与配置详解 (Component Catalog)
以下字段均来源于实际源码 config structs，未擅自虚构。

### 8.1 Logging (`components/logging`)
| 字段 | 类型 | 说明 |
|------|------|------|
| enabled | bool | 启用日志组件 |
| level | string | 日志等级 (info/debug/warn/error...) |
| format | string | 输出格式 (json / text) |
| output | string | 输出目标 (stdout / file / 自定义 writer) |
| file_config.dir | string | 文件目录 |
| file_config.filename | string | 文件名前缀 |
| rotate_config.enabled | bool | 是否启用滚动 |
| rotate_config.rotate_daily | bool | 是否按日滚动 |
| rotate_config.max_age | duration | 保留时长 |
| rotate_config.cleanup_enabled | bool | 是否清理 |

### 8.2 HTTP Server (`components/http_server`)
| 字段 | 说明 |
|------|------|
| enabled | 是否启动 HTTP 服务 |
| address | 监听地址，如 `:8080` |
| read_timeout / write_timeout / idle_timeout | 服务端超时保护 |
| graceful_timeout | 停机等待正在处理请求的上限 |
| enable_health | 内置 `/healthz` |
| enable_pprof | 是否暴露 pprof *(当前版本仅预留配置字段，尚未在组件内自动注册，需要后续实现或手动注册)* |

#### 8.2.1 快速启用示例
```yaml
http_server:
  enabled: true
  address: ":8080"
  enable_health: true
  enable_pprof: false
```
启动后（`enable_health: true`）自动暴露：`GET /healthz -> 200 ok`。

#### 8.2.2 路由注册模型概览
HTTP Server 使用 `github.com/go-chi/chi/v5` 作为路由，支持两种“预启动”注册方式：
1. 全局注册：`http_server.RegisterRoutes(fn)` （推荐，简单直接）
2. 实例注册：通过生命周期 `BeforeStart` Hook 获取组件实例并调用 `AddRouteRegistrar(fn)`（适合需要按条件动态注册或依赖其他已构造组件但尚未启动的场景）

组件在 `Start()` 阶段会：
- 构造新的 `chi.NewRouter()`
- 安装中间件（RealIP / Recoverer / Timeout / otelchi tracing / 访问日志）
- 注入健康检查路由（可选）
- 汇总所有注册器：`global snapshot()` + `extras`（由 `AddRouteRegistrar` 添加）并依次执行，将路由写入该 Router。

> 注意：`AddRouteRegistrar` 若在组件启动后调用会返回错误：`cannot register route: http_server already started (use BeforeStart hook)`。

#### 8.2.3 全局注册示例（在 `init()` 中）
```go
// controllers/user_controller.go
func init() {
  http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
    // 解析其他组件（例如 mysql）
    comp, err := c.Resolve("mysql")
    if err != nil { return err }
    mysqlComp := comp.(*appmysql.MysqlComponent)
    db, err := mysqlComp.GetDB("primary")
    if err != nil { return err }

    // 路由分组
    r.Route("/users", func(r chi.Router) {
      r.Get("/{id}", getUserHandler(db))
    })
    return nil
  })
}
```
特点：
- 写法最简单；只要文件被编译，`init()` 执行即完成注册。
- 与业务控制器代码自然耦合，方便查看。
- 需保证在 `application.App.Run()` 触发组件启动前完成（Go 的 `init()` 顺序满足这一点）。

#### 8.2.4 通过 Hook 动态注册示例
当需要按运行参数或外部条件决定是否注册路由，可使用生命周期钩子：
```go
app.AddHook("register_extra_routes", hooks.BeforeStart, func(ctx context.Context) error {
  comp, err := app.GetComponent(consts.COMPONENT_HTTP_SERVER)
  if err != nil { return err }
  h := comp.(*http_server.HTTPServerComponent)
  return h.AddRouteRegistrar(func(r chi.Router, c *core.Container) error {
    r.Get("/version", func(w http.ResponseWriter, r *http.Request) {
      w.Write([]byte("1.0.0"))
    })
    return nil
  })
}, priority /* 数值越小越先执行 */)
```
特点：
- 适用于需要读取配置、环境变量或构造复杂依赖后再决定路由的场景。
- 仍保证在 HTTP 服务器真正 `ListenAndServe` 前注册。

#### 8.2.5 中间件管理与顺序
框架内置以下中间件（顺序固定）：
1. `middleware.RealIP` — 解析真实客户端 IP
2. `middleware.Recoverer` — panic 保护
3. `middleware.Timeout(60s)` — 请求超时（顶层）
4. `otelchi.Middleware(serviceName)` — 分布式追踪（提取/创建 Span）
5. 自定义访问日志包装器（写入 traceparent/header + zap 结构化日志）

在你的路由注册函数中可以添加额外中间件：
```go
http_server.RegisterRoutes(func(r chi.Router, c *core.Container) error {
  r.Use(customAuthMiddleware)
  r.Get("/ping", func(w http.ResponseWriter, r *http.Request){ w.Write([]byte("pong")) })
  return nil
})
```
若只想作用于子路由：
```go
r.Route("/api", func(sr chi.Router){
  sr.Use(perRouteMiddleware)
  sr.Get("/items", listHandler)
})
```
> 建议：认证/限流/业务统计等放在更靠近业务的分组上，避免对所有内部健康或指标端点造成开销。

#### 8.2.6 访问日志与 Trace 头
访问日志字段：`method,path,remote,status,dur,trace_id,span_id`。
框架额外设置响应头：`traceparent`（W3C 格式），便于无 OTel 客户端调试。
自定义返回头部或日志附加字段：在你自己的中间件中读取 `trace.SpanContextFromContext(r.Context())` 并添加。

#### 8.2.7 依赖其他组件
在路由注册器中通过 `c.Resolve(name)` 获取其他已注册组件（它们尚未启动，但可读取配置或准备数据结构）。
避免耗时外部 I/O（例如主动查询数据库）——建议放到请求处理阶段或组件自身 `Start` 中。

#### 8.2.8 常见错误与排查
| 场景 | 现象 | 解决 |
|------|------|------|
| 注册函数返回错误 | 启动失败并回滚已启动组件 | 检查依赖组件名称或类型断言是否正确 |
| 在组件启动后调用 `AddRouteRegistrar` | 报错 `cannot register route...` | 改为在 `init()` 或 `BeforeStart` Hook 中注册 |
| 路由未匹配 | 404 | 确认分组前缀与最终请求路径拼接是否正确（`r.Route("/users"...)` + `GET /{id}` => `/users/{id}`） |
| trace 字段缺失 | 日志中无 `trace_id` | 确认 Telemetry 组件已启用 & 客户端是否传递 `traceparent` 头 |
| pprof 无效 | 访问 `/debug/pprof` 404 | 当前实现未自动注册，需要自行在注册器中 `import _ "net/http/pprof"` 并手动挂载 |

#### 8.2.9 最佳实践
- 单一控制器文件只注册相近资源（RESTful 分组）。
- 使用 `Route("/resource", func(r chi.Router){ ... })` 代替硬编码重复前缀。
- 将可复用中间件封装为函数（避免闭包捕获过多变量导致 GC 压力）。
- 避免在注册阶段做阻塞 I/O；启动速度更快，可观测性更好。
- 如果需要延迟加载较大数据，可在首次请求处理时通过 `sync.Once` 初始化。

#### 8.2.10 何时使用 AddRouteRegistrar vs RegisterRoutes
| 方式 | 适用场景 | 优点 | 注意 |
|------|------|------|------|
| RegisterRoutes | 绝大多数静态路由 | 简洁；文件即注册 | 不易按条件跳过（需在函数内部判断） |
| AddRouteRegistrar | 条件/动态、插件式扩展 | 可根据运行态决定是否添加 | 必须在启动前（Hook）调用；多次调用顺序由添加先后决定 |

#### 8.2.11 获取 Router（高级用法）
在 `AfterStart` Hook 中可以访问已启动的 Router（不推荐再增删路由，只做只读或调试）：
```go
app.AddHook("inspect_routes", hooks.AfterStart, func(ctx context.Context) error {
  comp, _ := app.GetComponent(consts.COMPONENT_HTTP_SERVER)
  h := comp.(*http_server.HTTPServerComponent)
  router := h.Router()
  // 只能做只读反射 / 输出调试，不要再注册新路由（运行期修改可能产生竞态）。
  _ = router
  return nil
}, 100)
```

#### 8.2.12 后续增强计划（与该组件相关）
- 自动挂载 pprof (`/debug/pprof/*`)。
- 支持请求指标（如 active requests、latency histogram、status codes）。
- 内置限流/熔断可选中间件。
- 热更新路由（需配合读写锁与版本切换）。

---
## 8.3 HTTP Clients (`components/http_client`)
| 层级 | 字段 | 说明 |
|------|------|------|
| root | enabled | 是否启用统一客户端管理 |
| root | default | 默认客户端名字 |
| client | base_url | 基础 URL（结尾 `/` 自动剔除） |
| client | timeout | 超时默认 10s |
| client | max_idle_conns / max_idle_conns_per_host | 连接池配置 |
| client | idle_conn_timeout | 空闲连接回收 |
| client | default_headers | 附加默认头 |
| client.retry | enabled | 是否启用重试 |
| client.retry | max_attempts | 重试次数 (>=1) |
| client.retry | initial_backoff / max_backoff | 回退窗口 |
| client.retry | backoff_multiplier | 指数递增倍数 |

### 8.4 gRPC Server (`components/grpc_server`)
| 字段 | 说明 |
|------|------|
| enabled | 是否启动 gRPC 服务 |
| address | 监听地址，如 `:50051` |
| max_recv_msg_size / max_send_msg_size | 消息大小限制 |
| graceful_timeout | 停机优雅等待 |
| enable_reflection | 是否注册 reflection 服务 |
| enable_health | 是否注册健康服务 |

---

当前使用 OTel StatsHandler + 自定义 Unary 拦截器链：
- grpc.StatsHandler(otelgrpc.NewServerHandler()) 负责生成/传播 trace + metrics。
- 自定义 Unary 拦截器顺序：
    1. recoveryInterceptor (panic 保护)
    2. traceHeaderInjectorInterceptor (在 handler 执行后注入非标准 trace_id 响应头)
    3. loggingInterceptor (访问日志，自动携带 trace_id/span_id)

说明：
- 由于当前依赖版本未暴露 `otelgrpc.UnaryServerInterceptor`，使用 StatsHandler 方式同样可以获得 trace 与基础指标。
- 如果未来升级依赖并提供官方 Unary 拦截器，可把 tracing 逻辑迁移到拦截器层（可获得更细粒度控制）。

#### 客户端 (grpc_client)
- 拨号时安装：
    - grpc.WithChainUnaryInterceptor(loggingUnaryClientInterceptor)
    - grpc.WithStatsHandler(otelgrpc.NewClientHandler())
- StatsHandler 生成 / 关联 span 并处理上下游 context 传播；logging 拦截器记录 method/duration/status。

#### Telemetry 依赖
- grpc_server / grpc_client 都声明依赖 telemetry + logging，保证全局 TracerProvider 在建连或接受请求之前已注册。

#### trace_id 响应头
- 非标准 `trace_id` header 由 traceHeaderInjectorInterceptor 写入，便于非 OTel 客户端快速调试。
- 正式链路依赖 W3C traceparent / baggage（由 StatsHandler 自动处理）。

#### 上下文 (context) 策略
- 组件内部操作（健康检查、延迟拨号）使用启动时捕获的 baseCtx，避免滥用 context.Background()。
- 业务调用必须传入入口 ctx 以延续调用链；客户端延迟拨号时也在该 ctx 上派生 span（由 StatsHandler 处理）。

#### 访问日志字段
- 已输出: method, dur, grpc_status, trace_id, span_id。
- 可扩展: peer_ip, req_size, resp_size, user_agent。

---
#### FAQ
**如何验证 trace 关联?** 在客户端 request 日志与服务端访问日志中查看相同 trace_id；导出到后端后查看同一 trace 内是否含 client->server 两段 span。

**StatsHandler 与拦截器能否同时使用?** 可以；当前未使用 OTel Unary 拦截器（版本缺失），StatsHandler 已足够。升级后若添加官方 Unary 拦截器，请移除重复的 StatsHandler（避免重复 span）。

**traceHeaderInjectorInterceptor 可否删除?** 纯 OTel 客户端环境可删；删除后只保留标准 traceparent。

---
#### 后续可选改进（未在本次实现）
1. Streaming (Server/Client) 拦截器 + 日志。
2. 更丰富的 span attributes（消息大小、peer 信息）。
3. 统一重试策略使用 ServiceConfig。
4. 指标：请求数/错误数/直方图分桶自定义。

---
#### 升级注意
- 升级 otelgrpc 后若出现 `UnaryServerInterceptor` / `UnaryClientInterceptor` 可用，可将 StatsHandler 替换为拦截器方式（避免重复）。
- 确保 Telemetry 组件仍最先初始化。


### 8.5 gRPC Clients (`components/grpc_client`)
根结构：

| 字段 | 说明 |
|------|------|
| enabled | 是否启用管理器 |
| clients | map[name]*clientConfig |
| default_timeout | 默认调用超时 |
| enable_health_check | 是否启用周期健康检查 |
| health_check_interval | 健康检查间隔 |

单 client：

| 字段 | 说明 |
|------|------|
| name | 客户端标识 |
| host / port | 目标地址 |
| secure | 是否 TLS |
| credentials_path | 证书路径 (可选) |
| max_receive_message_length / max_send_message_length | 限制 |
| compression | 压缩算法 (可选) |
| timeout | 单独超时覆盖 |
| retry_policy.* | 重试策略 |
| keepalive_options.* | KA 选项 |
| connect_on_start | 启动时就拨号（否则 lazy） |

### 8.6 MySQL (`components/mysql`)
顶层：

| 字段 | 说明 |
|------|------|
| enabled | 是否启用 |
| data_sources | 多数据源 map |

DataSource：

| 字段 | 说明 |
|------|------|
| dsn | 完整 DSN（存在则优先） |
| host/port/user/password/database | 连接组件 |
| params | 额外参数键值 |
| max_open_conns / max_idle_conns | 连接池 |
| conn_max_life / conn_max_idle | 生命周期控制 |
| ping_on_start | 启动是否 ping 验证 |

### 8.7 MySQL GORM (`components/mysqlgorm`)
与原生 mysql 类似 + GORM 级别拓展：

| 字段 | 说明 |
|------|------|
| enabled | 启用 |
| log_level | gorm 日志等级 |
| slow_threshold | 慢查询阈值 |
| data_sources.* 与 mysql 相同 |  |
| per-ds: skip_default_tx | 跳过默认事务 |
| per-ds: prepare_stmt | 预编译缓存 |

### 8.8 Redis (`components/redis`)

| 字段 | 说明 |
|------|------|
| enabled | 启用 |
| mode | single / cluster / sentinel |
| addresses | 地址数组（cluster/sentinel 多个） |
| username/password | 认证 |
| db | DB index (single 模式) |
| sentinel_master | sentinel 主名 |
| pool_size / min_idle_conns | 连接池参数 |
| conn_max_lifetime / conn_max_idle_time | 连接生命周期 |
| dial_timeout / read_timeout / write_timeout | 操作超时 |

### 8.9 Prometheus (`components/prometheus`)
| 字段 | 说明 |
|------|------|
| enabled | 启用指标暴露 |
| address | 监听地址 (":9090") |
| path | 指标路由 (默认 /metrics) |
| namespace / subsystem | 前缀分类 |
| collect_go_metrics / collect_process | 是否采集 Go / 进程默认指标 |

### 8.10 Telemetry (Tracing) (`components/telemetry`)
| 字段 | 说明 |
|------|------|
| enabled | 启用追踪 |
| service_name | 服务标识 (resource attr) |
| exporter | stdout / otlp |
| sample_ratio | 采样率 (0<ratio≤1) |
| stdout_pretty | stdout exporter 是否格式化 |
| stdout_file | 输出到文件（非空表示追加文件） |
| otlp.endpoint | OTLP gRPC/HTTP 端点 |
| otlp.insecure | 是否跳过 TLS |
| otlp.timeout | OTLP 发送超时（默认 5s） |

---
## 9. 启动流程 (Boot Sequence)
时序（伪代码）：
```
App.Run():
  if enhanced -> runEnhanced() else runBasic()
    create context (signal or enhanced loop)
  RunWithContext(ctx):
    boot():
      ConfigManager.LoadConfig()
      registry.BuildAndRegisterAll(cfg, container)
    lifecycleManager.StartAll(ctx):
      hooks.BeforeStart
      container.ValidateDependencies() // topo
      for comp in ordered: comp.Start()
      hooks.AfterStart
  <-ctx.Done()
  lifecycleManager.StopAll()
```

Enhanced 模式特性 (Windows 默认 / 或强制变量)：
- 支持第二次信号强制退出
- 支持超时强制退出 (默认 30s)
- 支持 Windows Console Control Events (CTRL_C / CLOSE / LOGOFF / SHUTDOWN)
- 可通过环境变量禁用强退或设置退出码

---
## 10. 优雅停机 (Graceful Shutdown)
Basic 模式：监听 `SIGINT` / `SIGTERM`。
Enhanced 模式：
1. 首次信号 => 取消根 context -> 触发 StopAll
2. 启动超时计时器（`shutdownTimeout`）到期可强制退出（可禁用）
3. 第二次信号 => 立即强制退出
4. Windows 控制台事件统一映射为首次取消

相关环境变量：见 §15。

---
## 11. 健康检查 & 监控
- 每组件 `HealthCheck()`：框架当前未集中轮询；可由上层 HTTP `/healthz` 组合调用（HTTP Server 组件可集成）。
- Prometheus：提供注册器 + 自定义 Counter/Gauge/Histogram 创建；可按 namespace/subsystem 加前缀。
- Telemetry：为库调用、外部请求添加 Trace；采样率控制 QPS 开销。
- 日志组件：提供统一 logger（细节依赖实现）。

示例使用指标：
```go
var requestCounter = prometheus.C().NewCounter("requests_total", "Total incoming requests", []string{"route"})
func handler(route string){
  requestCounter.WithLabelValues(route).Inc()
}
```

---
## 12. 测试与可替换性 (Testing & Replacement)
场景：在单元测试中希望替换真实 MySQL / Redis 为内存实现。
步骤：
1. 启动前调用 App.boot()（或间接通过 RunWithContext 触发）之前不需要替换——你需要组件已注册但未激活状态。
2. 使用 `container.Replace(name, fakeComponent)` 替换（要求原组件 `IsActive()==false`）。
3. 调用 StartAll；框架按顺序启动 fake。

Fake 组件实现：
```
type FakeStore struct{ core.BaseComponent }
func NewFake(){ return &FakeStore{*core.NewBaseComponent("mysql")} }
func (f *FakeStore) Start(ctx context.Context) error { f.SetActive(true); return nil }
func (f *FakeStore) Stop(ctx context.Context) error  { f.SetActive(false); return nil }
```

---
## 13. 扩展示例：新增组件 Foo
步骤（总结 + 代码要点）：
1. 创建目录 `components/foo/`：`config.go`, `component.go`, `factory.go`。
2. 定义配置：
   ```go
   type FooConfig struct { Enabled bool `yaml:"enabled"`; Endpoint string `yaml:"endpoint"` }
   ```
3. 实现组件：
   ```go
   type FooComponent struct { core.BaseComponent; cfg *FooConfig }
   func (f *FooComponent) Start(ctx context.Context) error { /* dial */ f.SetActive(true); return nil }
   func (f *FooComponent) Stop(ctx context.Context) error { /* close */ f.SetActive(false); return nil }
   func (f *FooComponent) Dependencies() []string { return []string{"logging"} }
   ```
4. Builder 注册 (`registry/foo.go`):
   ```go
   func init(){ registry.Register("foo", func(cfg *config.AppConfig, c *core.Container)(bool, core.Component, error){
       if cfg.Foo==nil || !cfg.Foo.Enabled { return false,nil,nil }
       return true, NewFooComponent(cfg.Foo), nil
   }) }
   ```
5. 在 `AppConfig` 加字段 `Foo *foo.FooConfig`（修改 schema.go）。
6. 在 YAML 添加：
   ```yaml
   foo:
     enabled: true
     endpoint: http://...
   ```
7. 启动；若其它组件 Dependencies 包含 "foo" 但 YAML 未启用，将提前失败。

---
## 13.1 用户自定义业务组件 (示例: taskDao / taskService)
很多业务方需要在基础设施组件 (logging, mysql_gorm, redis 等) 之上再封装自己的 DAO / Service 组件，并希望：
- 声明依赖后自动按顺序构建、启动、停止
- 复用统一生命周期与优雅停机
- 使用统一、标准、可测试的组件定义方式（结构体 + builder）

本框架已引入两项能力：
1. registry.RegisterWithDeps(name, deps, fn)  —  Builder 级别的“构建顺序”依赖
2. App.RegisterCustomBuilder / App.ProvideComponent —  业务在启动前动态扩展组件

注意：
- Builder 的 deps 只影响“构建顺序”，运行期 Start/Stop 顺序仍由 Component.Dependencies() 决定；两者都需要正确声明。
- 这样可以在 Builder 中安全地 Resolve 依赖组件（因为其 Builder 已执行并注册进 Container）。

### A. 通过 Builder 定义 taskDao 组件
```go
// components/taskdao/task_dao.go
package taskdao

import (
    "context"
    "fmt"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
    mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
    "gorm.io/gorm"
)

type TaskDAO struct {
    *core.BaseComponent
    gormComp *mg.GormComponent // 注入的 mysql_gorm 组件实例（尚未启动时也可以拿到指针）
    db       *gorm.DB          // 启动后绑定的具体数据源句柄
    dsName   string            // 数据源名称（示例用 "main"）
}

// New 仅做结构体初始化，不访问外部资源
func New(gormComp *mg.GormComponent, dsName string) *TaskDAO {
    return &TaskDAO{
        BaseComponent: core.NewBaseComponent("task_dao", consts.COMPONENT_MYSQL_GORM, consts.COMPONENT_LOGGING),
        gormComp:      gormComp,
        dsName:        dsName,
    }
}

func (d *TaskDAO) Start(ctx context.Context) error {
    // 标记 active（也可以先做依赖检查，再 SetActive）
    if err := d.BaseComponent.Start(ctx); err != nil { return err }
    // 到这里 mysql_gorm 已经被框架保证先启动（因为 Dependencies 中声明）
    db, err := d.gormComp.GetDB(d.dsName)
    if err != nil { return fmt.Errorf("get gorm db %s failed: %w", d.dsName, err) }
    d.db = db
    return nil
}

func (d *TaskDAO) Stop(ctx context.Context) error { return d.BaseComponent.Stop(ctx) }

// 示例 DAO 方法
func (d *TaskDAO) FindTask(ctx context.Context, id int64) (*Task, error) {
    var t Task
    if err := d.db.WithContext(ctx).First(&t, id).Error; err != nil { return nil, err }
    return &t, nil
}

type Task struct { ID int64 `gorm:"primaryKey"` Name string }
```

```go
// registry/taskdao.go  (业务侧放在任意被编译到的包内)
package registry_ext

import (
    "fmt"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/config"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
    mg "github.com/grand-thief-cash/chaos/app/infra/go/application/components/mysqlgorm"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
    "github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
    "github.com/your/module/components/taskdao"
)

func init() {
    // RegisterWithDeps 确保构建顺序：mysql_gorm/logging 先被构建并注册
    registry.RegisterWithDeps("task_dao", []string{consts.COMPONENT_MYSQL_GORM, consts.COMPONENT_LOGGING}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
        // 1. 可选启用判断（这里简单直接启用）
        // 2. 构建期 Resolve：拿到尚未启动但已构造的 mysql_gorm 组件实例
        comp, err := c.Resolve(consts.COMPONENT_MYSQL_GORM)
        if err != nil { return true, nil, fmt.Errorf("resolve mysql_gorm failed: %w", err) }
        gormComp, ok := comp.(*mg.GormComponent)
        if !ok { return true, nil, fmt.Errorf("mysql_gorm type assertion failed") }
        // 3. 仅注入引用，不获取具体 *gorm.DB（必须留到 Start 之后）
        dao := taskdao.New(gormComp, "main")
        return true, dao, nil
    })
}
```

> 关键点：
> - RegisterWithDeps 保证 mysql_gorm builder 先执行，因此 Resolve 一定成功。
> - Start 顺序再由 TaskDAO.Dependencies() 决定（运行期拓扑），mysql_gorm 会先启动，
>   所以在 TaskDAO.Start 中调用 gormComp.GetDB() 才能得到已初始化的 *gorm.DB。
> - 构建期不要访问对方启动后才会准备的资源（如连接池），否则会得到空/未初始化状态。

## 13.2 使用 App.RegisterCustomBuilder 动态注册组件
当你不想写 `init()`（例如：根据启动参数 / 环境变量 / 运行时逻辑决定是否注册）时，可以在调用 `app.Run()` 之前显式注册自定义组件 builder。

特点：
- 仍然走标准 builder 流程（可声明构建期依赖、可在 builder 内 Resolve）。
- 代码集中在 main（或组装层），便于条件控制与调试。
- 与 `init()` 自注册方式互斥或并存（同名二次注册会 panic）。

示例：动态注册一个简单的 `reporter` 组件，它依赖 `logging`。
```go
// main.go
package main

import (
  "context"
  "os"
  "github.com/grand-thief-cash/chaos/app/infra/go/application"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/config"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
)

type Reporter struct { *core.BaseComponent }
func NewReporter() *Reporter { return &Reporter{core.NewBaseComponent("reporter", consts.COMPONENT_LOGGING)} }
func (r *Reporter) Start(ctx context.Context) error { return r.BaseComponent.Start(ctx) }
func (r *Reporter) Stop(ctx context.Context) error  { return r.BaseComponent.Stop(ctx) }

func main(){
  app := application.GetApp()
  if os.Getenv("ENABLE_REPORTER") == "1" { // 条件启用
    app.RegisterCustomBuilder("reporter", []string{consts.COMPONENT_LOGGING}, func(cfg *config.AppConfig, c *core.Container)(bool, core.Component, error){
      // 可选：_ , _ = c.Resolve(consts.COMPONENT_LOGGING) 做构建期 wiring
      return true, NewReporter(), nil
    })
  }
  if err := app.Run(); err != nil { panic(err) }
}
```
行为说明：
- 如果未设置 ENABLE_REPORTER=1，组件不注册；任何声明依赖 reporter 的组件会在启动前依赖校验直接失败。
- 测试中可直接调用 RegisterCustomBuilder 注入 mock 实现。

## 13.3 使用 ProvideComponent 直接提供实例
`ProvideComponent` 适合“已存在实例”或“非常简单无需构建期依赖注入”的场景。

限制与注意：

| 项目 | 说明 |
|-----|------|
| 不支持构建期 Resolve | 没有 builder 回调，无法在提供时通过容器 Resolve 其它组件实例。 |
| 仍需声明运行期依赖  | 结构体内嵌 `BaseComponent` 时把硬依赖名称放进去，保障启动顺序。 |
| 必须在 boot 前调用 | `app.Run()` / `RunWithContext()` 触发 boot 后再调用会失败。 |
| 无 enabled 语义 | 是否注册完全由你代码逻辑决定。 |
| 不适合复杂初始化 | 需要依赖其它组件资源/引用的建议使用 builder。 |


示例：内存缓存组件（依赖 logging）。
```go
// cache/cache.go
package cache

import (
  "context"
  "sync"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
)

type MemoryCache struct {
  *core.BaseComponent
  mu   sync.RWMutex
  data map[string]string
}

func NewMemoryCache() *MemoryCache {
  return &MemoryCache{BaseComponent: core.NewBaseComponent("memory_cache", consts.COMPONENT_LOGGING), data: make(map[string]string)}
}
func (m *MemoryCache) Start(ctx context.Context) error { return m.BaseComponent.Start(ctx) }
func (m *MemoryCache) Stop(ctx context.Context) error  { return m.BaseComponent.Stop(ctx) }
func (m *MemoryCache) Get(k string) (string, bool) { m.mu.RLock(); v, ok := m.data[k]; m.mu.RUnlock(); return v, ok }
func (m *MemoryCache) Set(k, v string) { m.mu.Lock(); m.data[k]=v; m.mu.Unlock() }
```

注册与访问：
```go
// main.go
package main
import (
  "github.com/grand-thief-cash/chaos/app/infra/go/application"
  "github.com/your/module/cache"
)
func main(){
  app := application.GetApp()
  if err := app.ProvideComponent(cache.NewMemoryCache()); err != nil { panic(err) }
  if err := app.Run(); err != nil { panic(err) }
}
```
使用：
```go
comp, _ := app.GetComponent("memory_cache")
mc := comp.(*cache.MemoryCache)
mc.Set("k","v")
```
何时不要用：
- 需要构建期注入其它组件引用（改用 RegisterCustomBuilder）。
- 需要 enabled=false 条件配置化跳过。
- 未来会演进成复杂生命周期。

迁移策略：默认优先“struct + builder”；仅在组件完全无构建期依赖且逻辑极简单时考虑 ProvideComponent，否则容易形成隐式耦合。

---
## 13.4 Service 业务服务组件示例 (依赖多个 DAO / 分层依赖实践)
很多用户还会继续在 DAO 之上抽象 Service 层（聚合多表、多 DAO、封装业务事务、编排调用），希望 Service 也能作为一个标准组件被生命周期管理，并被上层 HTTP / gRPC Server 使用。

目标：
- Service 作为组件受统一 Start / Stop 管控；可替换 / 可测试。
- 明确分层： Infra (mysql_gorm / logging) -> DAO 组件 -> Service 组件 -> 接入层 (http_server / grpc_server)。
- 避免环：Service 不依赖 http_server；路由注册由 server 侧在启动阶段 Resolve Service。

典型依赖拓扑：
```
logging ─┬─> mysql_gorm ─> task_dao ─> task_service ─> (used by http_server handlers)
         └───────────────────────────────────────────┘ (logging 也被 service 使用)
```

### 13.4.1 定义 Service 组件
```go
// components/taskservice/task_service.go
package taskservice

import (
  "context"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
  td "github.com/your/module/components/taskdao" // 业务侧 DAO 包
)

type TaskService struct {
  *core.BaseComponent
  dao *td.TaskDAO // 已在 builder 注入 (构建期引用)，Start 时可直接使用其公开方法
}

func New(dao *td.TaskDAO) *TaskService {
  // 运行期依赖：task_dao + logging (如果内部直接打日志)
  return &TaskService{BaseComponent: core.NewBaseComponent("task_service", "task_dao", consts.COMPONENT_LOGGING), dao: dao}
}

func (s *TaskService) Start(ctx context.Context) error { return s.BaseComponent.Start(ctx) }
func (s *TaskService) Stop(ctx context.Context) error  { return s.BaseComponent.Stop(ctx) }

// 业务方法示例
type TaskDTO struct { ID int64; Name string }
func (s *TaskService) GetTask(ctx context.Context, id int64) (*TaskDTO, error) {
  t, err := s.dao.FindTask(ctx, id)
  if err != nil { return nil, err }
  return &TaskDTO{ID: t.ID, Name: t.Name}, nil
}
```

### 13.4.2 注册 Service Builder
Service 需要在构建期 Resolve task_dao，因此使用 `RegisterWithDeps` 并声明构建期依赖。
```go
// registry/taskservice.go
package registry_ext

import (
  "fmt"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/config"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/registry"
  td "github.com/your/module/components/taskdao"
  ts "github.com/your/module/components/taskservice"
)

func init() {
  registry.RegisterWithDeps("task_service", []string{"task_dao"}, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
    comp, err := c.Resolve("task_dao")
    if err != nil { return true, nil, fmt.Errorf("resolve task_dao failed: %w", err) }
    dao, ok := comp.(*td.TaskDAO)
    if !ok { return true, nil, fmt.Errorf("task_dao type assertion failed") }
    return true, ts.New(dao), nil
  })
}
```
关键点：
- 构建期依赖只写 `[]string{"task_dao"}`；`logging` 不需要放在构建期（除非构建期要 Resolve logger）。
- 运行期依赖在 `New()` 里通过 BaseComponent 声明：`task_dao`, `logging`。
- 这样保证：task_dao builder -> task_service builder -> 拓扑排序启动时：logging -> mysql_gorm -> task_dao -> task_service。

### 13.4.3 在 HTTP / gRPC Server 中使用 Service
不建议让 Service 依赖 http_server（那会造成“业务层依赖接入层”反向依赖），应由 http_server 侧（或其路由注册钩子）在 Start 之后 Resolve Service。

方案 A：在 http_server 组件的 Start 内追加“路由注册回调”列表（如果已有可扩展点），遍历时 Resolve。

方案 B：使用 Hook：注册 `hooks.AfterStart` 钩子，里边 Resolve `http_server` + `task_service`，再把 handler 绑定。

示例（伪代码 Hook）：
```go
// registry/http_routes.go
package registry_ext
import (
  "github.com/grand-thief-cash/chaos/app/infra/go/application/hooks"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/core"
  "github.com/grand-thief-cash/chaos/app/infra/go/application/consts"
)

func init(){
  hooks.DefaultManager().RegisterAfterStart(100, func(c *core.Container) error {
     srvComp, err := c.Resolve(consts.COMPONENT_HTTP_SERVER)
     if err != nil { return err }
     svcComp, err := c.Resolve("task_service")
     if err != nil { return err }
     srv := srvComp.(interface{ RegisterGET(path string, h func(ctx Context)))
     taskSvc := svcComp.(*taskservice.TaskService)
     srv.RegisterGET("/tasks/:id", func(ctx Context){ /* 调用 taskSvc.GetTask */ })
     return nil
  })
}
```

### 13.4.4 DAO / Service 的接口抽象建议
- 导出 DAO / Service interface（放在更高层 pkg），组件内部持有实现，外部依赖 interface 便于测试替换。
- 在测试中使用 `container.Replace("task_service", fakeServiceComp)` 直接替换整块逻辑。

### 13.4.5 何时将 Service 做成组件？
| 场景 | 建议 |
|------|------|
| Service 需要被多个接入层（HTTP + gRPC + cron）共享 | 做成组件，集中生命周期管理 |
| Service 需要依赖其它组件并在 Start 进行预热 / 缓存加载 | 做成组件 |
| Service 逻辑纯计算，无外部依赖 | 可直接普通 struct，不必组件化 |
| 需要在测试中替换 Service 实现 | 组件 + Replace 更方便 |

### 13.4.6 常见错误
| 错误 | 说明 | 解决 |
|------|------|------|
| 在 Service Start 中访问尚未启动的 DAO 资源 | 运行期依赖未声明导致启动顺序错误 | 确认 BaseComponent 里包含 DAO 名称 |
| Service Builder 中访问事务 / 连接池 | 构建期过早访问启动才准备的资源 | 延迟到 Start 或 AfterStart Hook |
| Service 依赖 http_server | 反向耦合导致拓扑复杂 | 把路由注册放在 server 或 Hook 中 |
| Builder 漏写构建期 deps 直接 Resolve | Resolve 失败或返回 nil | 使用 RegisterWithDeps 并加上 task_dao |

### 13.4.7 结构检查总结
| 阶段 | 使用的依赖描述来源 | 目的 |
|------|--------------------|------|
| 构建期 (builder) | RegisterWithDeps([...]) | 允许 Resolve 已构建组件引用 |
| 运行期 Start/Stop | Component.Dependencies() -> BaseComponent | 决定启动拓扑、停机逆序 |

---
## 14. 常见错误与排查 (Troubleshooting)
| 症状 | 可能原因 | 排查步骤 |
|------|----------|----------|
| missing component dependencies | 组件 Dependencies 指向未注册名 | 检查拼写 / 对应 builder 是否 enabled |
| circular dependency detected | A->B->A 等环 | 重新评估组件边界，拆出独立抽象 |
| failed to start component X | Start 内部资源失败（网络/认证） | 查看日志；确保 Start 做最小连接数；重试放业务层 |
| after_start hooks failed | Hook 函数返回 error | 降级/增加日志，必要时调整优先级 |
| Replace active component | 在 Replace 时组件已 Start | 移动 Replace 调用到 StartAll 前 |
| 强制退出 (graceful-timeout) | shutdown 超时 | 增大 `SetShutdownTimeout` 或优化 Stop 实现 |

日志级别建议：
- Start 成功：INFO
- Start 失败：ERROR + 返回
- Stop 错误：WARN（继续其他组件）

---
## 15. 环境变量与运行参数 (Environment Variables)
| 变量 | 作用 | 默认 |
|------|------|------|
| GOINFRA_DISABLE_ENHANCED | 设为 1 禁用增强模式 | unset |
| GOINFRA_FORCE_ENHANCED | 设为 1 强制增强模式 | unset |
| GOINFRA_DISABLE_FORCE_EXIT | 设为 1 在增强模式下不在超时/二次信号强退 | unset |
| GOINFRA_FORCE_EXIT_CODE | 强制退出时的进程退出码 | 1 |
| (未来) 覆盖配置字段 | 预留：如 GOINFRA_MYSQL_MAIN_HOST | N/A |

`App.SetShutdownTimeout(d)` 可在代码中调整优雅停机等待时长。

---
## 16. 最佳实践 (Best Practices)
- Builder 零副作用：所有外部连接延迟到 Start。
- 小接口化：若组件提供多职责，内部再拆分子接口导出（未来可通过接口分裂）。
- 明确依赖：仅声明硬依赖；软依赖通过运行时探测。
- 健康探针轻量：HealthCheck 做轻量校验（ping 或状态位），避免阻塞主循环。
- 指标命名：`<namespace>_<subsystem>_<metric>`；统一维度标签顺序。
- 避免 `init()` 中启动 goroutine（文档级强制）。
- Stop 必须幂等，允许多次调用不 panic。
- 配置默认值：在各组件 `applyDefaults()` (如 HTTP Clients) 中集中设置。

---
## 17. 未来增强路线 (Future Roadmap)
(c.f. 原文 “未来增强建议”) 补充：
1. 分层并发启动：根据拓扑层级并行提升冷启动性能。
2. 组件白/黑名单运行：通过 CLI / 配置 include / exclude 列表。
3. 可观测性增强：统一 metrics + tracing 注入中间件（HTTP/gRPC）。
4. Describe/Introspect API：运行期输出组件状态、依赖图、版本信息。
5. 动态重载：监听配置变更 -> 选择性 Restart 可热更新配置（需明确降级策略）。
6. Health 聚合器：核心统一路由 /healthz 汇总所有组件 HealthCheck。
7. Start Strategy 插件：顺序 / 分层并行 / 全并行(with dependency readiness barrier)。
---

HTTP Server Component 相关增强：
1. 在 HTTP Server 组件中实现 enable_pprof 自动挂载（/debug/pprof/*）。
2. 增加路由列表调试输出（仅开发环境）以便确认注册结果。 
3. 增加一个示例 metrics 中间件（记录请求耗时直方图）。

## 附：原始职责边界表 (保留)

## 架构职责与边界 (Architecture Responsibilities & Boundaries)

| 层/模块 | 职责 | 不应该做的事 | 说明 |
|---------|------|--------------|------|
| `application.App` | 1) 解析启动参数 (env, config path) 2) 加载 & 验证配置 3) 触发组件注册 (registry) 4) 调用 Lifecycle 启停 | 不直接创建具体组件实例 (已下放到 registry) | 现在唯一需要了解的是 `registry.BuildAndRegisterAll` 的调用时机 |
| `registry` | 维护 (组件名 -> BuilderFunc) 注册表；按确定性顺序构建 & 注册启用的组件 | 不处理启动/停止；不做日志/钩子 | 每个组件包通过 `init()` 调用 `registry.Register` 实现“自描述式”装配 |
| `core.Container` | 保存已构建组件实例；依赖关系拓扑排序；依赖完整性验证 | 不负责组件生命周期；不感知配置结构 | 新增 `ValidateDependencies` + `Replace` (测试替换) |
| `core.LifecycleManager` | 统一 Start/Stop 顺序、钩子执行、失败回滚 | 不直接创建组件；不读配置 | Start 前先做依赖完整性校验；失败自动回滚已启动组件 |
| `hooks.Manager` | 生命周期阶段 hook 注册 & 调度 | 不含业务逻辑 | 默认全局 hooks 在 `hooks/default.go` 注册 |
| `components/*` | 组件内部配置解释、资源连接、健康检查实现 | 不感知全局应用结构 | 每个组件决定是否启用 (cfg.Enabled) 并在 builder 中返回 (enabled bool) |
| `config/*` | 配置文件读取、格式解析、校验占位 | 不做组件实例化 | 后续可增强：env 覆盖、必填校验、分层合并 |

### 新的组件注册流程
1. 组件包在其 `registry/*.go` 中：
   ```go
   func init() {
       registry.Register(consts.COMPONENT_LOGGING, func(cfg *config.AppConfig, c *core.Container) (bool, core.Component, error) {
           if cfg.Logging == nil || !cfg.Logging.Enabled { return false, nil, nil }
           comp, err := logging.NewFactory().Create(cfg.Logging)
           if err != nil { return true, nil, err }
           return true, comp, nil
       })
   }
   ```
2. `App.registerComponents()` 只做一件事：`registry.BuildAndRegisterAll(cfg, container)`。
3. 注册表按名称排序保证确定性；builder 返回 `(enabled=false)` 则跳过。
4. 失败立即中止，错误向上抛出，启动终止。

### 依赖与生命周期
- 启动顺序 = `container.ValidateDependencies()` 的拓扑排序结果。
- 启动失败：
  - 尝试 Stop 失败组件（若部分激活）
  - 按已完成的逆序逐个 Stop 已启动组件
  - 返回首个失败错误
- 正常 Stop：逆拓扑顺序停止；忽略未激活组件。

### 边界改进收益
| 问题 (原) | 改进 | 收益 |
|-----------|------|------|
| `app.go` 硬编码 if/else 组件构造 | registry + init 自注册 | 新增组件无需修改集中式文件 (OCP) |
| 组件构建与启动杂糅 | 构建只在 register 阶段；启动在 Lifecycle | 更清晰的单一职责 |
| 缺乏依赖完整性提前失败 | `ValidateDependencies()` 启动前执行 | 早期快速失败，避免半启动状态 |
| 测试难以替换组件 | `Container.Replace` (未激活) | 提升可测试性 |

(以上为原始摘录，已在前文展开。)

---
## 结束语
该基础设施层旨在提供一个可演进、可观测、可测试的统一启动骨架。后续演进请保持：最小耦合 + 明确边界 + 可恢复失败三项核心原则。
