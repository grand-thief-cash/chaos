# Infrastructure

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

### 未来增强建议 (与职责边界相关)
1. 可插拔组件白名单/黑名单 (在配置或 CLI 添加 include/exclude，registry 过滤)。
2. Builder 支持返回“软依赖”提示（例如某组件启用但其可选依赖未启用时输出 WARN）。
3. 分层启动与并行：拓扑排序后按层并发启动，进一步与生命周期解耦（可引入 `StartStrategy`）。
4. `Component` 接口拆分：`Starter`, `HealthProvider` 等，避免必须实现无意义方法。
5. 在 registry 增加 `Describe()` 接口（文档与自发现）。

### 典型扩展步骤 (新增组件 Foo)
1. 创建 `components/foo/`：配置结构 `FooConfig` + `FooComponent` (实现 `core.Component`) + `factory.go`。
2. 在 `registry/foo.go`：调用 `registry.Register("foo", builder)`。
3. 在主配置文件添加 `foo:` 块 (`enabled: true`)。
4. (可选) 在其它组件 `Dependencies()` 增加 `"foo"`。
5. 启动应用：若缺少 `foo` 却被依赖，会在启动前被 `ValidateDependencies` 拦截。

### 约束 & 准则
- Builder 必须“纯”：不做 IO/网络连接，只准备 `Component`（连接延后到 `Start`）。
- Builder 报错 = 视为 fatal，阻断启动。
- 如果组件需要共享其它组件资源（比如 logger），在 `Start` 中使用 `container.Resolve`（保持构造阶段无副作用）。
- 严禁在 `init()` 中启动 goroutine 或做外部调用；只能注册 builder / hook。

---

## core
(待补充：更细粒度的并发与状态机设计说明，可后续迭代)

## hooks
(保持与原文一致，可择机补充 hook 优先级规范与命名约定)

## components

### Prometheus 

#### Configuration
1. enabled: Whether the Prometheus component starts (collector registry + HTTP exposure).
2. address / host / port: The listening address (e.g. :9090) for the metrics HTTP endpoint.
3. path: The HTTP route under which metrics are exposed (here /metrics).
4. namespace: Optional prefix for all metric names to avoid collisions.
5. subsystem: Optional second prefix (often the component/module name).
6. const_labels / labels: Key/value labels automatically attached to every metric.
7. pushgateway / push_interval: (Only if you support push mode) configuration to push metrics instead of (or in addition to) pull. If only path is shown, it just controls the URL where Prometheus scrapes.

#### Usage

prometheus.C() appears to be a global accessor returning the (already initialized) Prometheus component or a wrapper around a global registry.
NewCounter with []string{"route"} creates a counter vector; you must later use .WithLabelValues("xxx").Inc().
```golang
package demo

import (
	"context"

	appmetrics "github.com/grand-thief-cash/chaos/app/infra/go/application/components/prometheus"
)

var (
	reqCounter = appmetrics.C().NewCounter(
		"requests_total",
		"Total incoming requests",
		[]string{"route"},
	)
)

func HandleEcho(ctx context.Context, route string) {
	// Increment labeled counter
	reqCounter.WithLabelValues(route).Inc()
	// ... actual logic
}
```


# Common

