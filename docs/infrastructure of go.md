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
| enable_pprof | 是否暴露 pprof |

### 8.3 HTTP Clients (`components/http_client`)
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
