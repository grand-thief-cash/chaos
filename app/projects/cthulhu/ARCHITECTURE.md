# cthulhu 项目架构设计 (初稿)

> 目标：建立一个可迭代、易维护、不过度设计的 Angular 17 前端骨架，用于个人金融量化与管理工具集合，支持大量数据展示与可视化。当前阶段只做结构与约定，不写具体业务实现。

## 1. 设计原则

1. 轻量起步：先用 Angular 17 原生能力（Standalone + Signals），避免过早引入复杂状态管理（如 NgRx）。如后续状态复杂，再平滑扩展。  
2. 垂直特性切片 (Feature First)：按业务域拆分 `features/`，每个特性自包含页面、局部组件与局部状态。  
3. 分层清晰：`core` 放全局单例与启动逻辑；`shared` 放纯复用组件/工具；`data-access` 处理外部数据访问；`features` 是业务外壳；`charts` 专注可视化封装。  
4. UI 抽象：对 Ant Design (ng-zorro-antd) 组件做最小包装形成领域可复用 UI（避免在业务层到处散落 `nz-` 属性）。  
5. 延迟复杂度：缓存、权限、国际化、插件化等后续按实际需要增量添加。  
6. 性能优先：懒加载路由 + 仅在需要时订阅数据源 + 使用 Signals 减少不必要变更检测。  
7. 面向扩展：留出扩展点（例如 data-adapters、chart-adapters、plugin 目录），不预先实现。  
8. 单一职责：目录与文件命名体现用途；避免“万能 util” 或“大杂烩 service”。

## 2. 推荐依赖（后续按需安装）

核心 UI / 交互：
- `ng-zorro-antd` (Ant Design Angular 实现) + `@angular/cdk`
- 图表：`echarts` + `ngx-echarts` （或后续可引入 `lightweight-charts` 用于金融 K 线）
- 可选：`@ngx-translate/core`（如需要多语言）

工具增强：
- 日期处理：`dayjs`（轻量）
- 数据校验：简单场景直接用 TypeScript 类型；复杂场景可选 `zod` 或 `class-validator`

状态与数据：
- 先不引入 NgRx；使用 Service + Signal / RxJS。后续若演变复杂可加 `@ngrx/signals` 或 Store。

分析 & 性能：
- 后续可添加 `@angular-architects/module-federation` 做微前端或插件化（非当前阶段）。

## 3. 目录骨架（建议初始结构）

```
src/
  app/
    core/                # 应用启动与全局单例层
      config/            # 读取环境、远端配置、feature flag
      services/          # 全局服务: AuthService, LayoutService, LoggingService
      interceptors/      # HTTP 拦截器: auth, error, loading
      guards/            # 路由守卫 (AuthGuard 等)
      state/             # 极少量全局信号状态 (如用户信息)
      error-handling/    # 全局错误边界 & handler
      init/              # 启动初始化逻辑 (AppInitializer)

    routing/             # 顶级路由与懒加载配置
      app.routes.ts

    shared/              # 纯复用，**无业务语义**
      ui/                # UI 设计系统封装
        layout/          # 基础布局包装 (AntD Layout, Header, SideNav)
        components/      # 通用组件 (TableWrapper, FormWrapper, LoadingSpinner)
        form/            # 表单封装 & 控件 (日期范围, 数值输入)
      charts/            # 图表基础组件 (EChartsWrapper, CandleChart)
      directives/        # 通用指令 (ResizeObserverDirective, DebounceClickDirective)
      pipes/             # 纯转换管道 (FormatNumberPipe)
      utils/             # 纯函数工具 (math, formatting)
      models/            # 跨 feature 的基础类型 (User, ApiError)

    data-access/         # 数据访问与 API 客户端封装
      http/              # 低层 HTTP 封装 (BaseHttpService)
      market-data/       # 行情数据适配器 (MarketDataApiService)
      portfolio/         # 账户/持仓相关 API
      backtest/          # 回测相关 API
      analytics/         # 指标/统计 API
      admin/             # 管理工具 API
      adapters/          # 如果需要对外部库或不同数据源做统一适配

    features/            # 垂直业务域切片（懒加载）
      dashboard/         # 总览仪表盘
        pages/           # 页面级组件 (DashboardPage)
        components/      # 局部组件 (PnLCard, MarketHeatMap)
        state/           # 局部 signal store / rx state
      market-data/
        pages/
        components/
        state/
      portfolio/
        pages/
        components/
        state/
      backtest/
        pages/
        components/
        state/
      analytics/
        pages/
        components/
        state/
      admin-tools/
        pages/
        components/
        state/
      cronjobs/          # 新增：定时任务管理
        pages/           # 页面级组件 (TaskListPage, TaskDetailPage)
        components/      # 局部组件 (TaskCard, TaskFilter)
        state/           # 局部 signal store / rx state

    plugins/             # 可选: 后续第三方/实验性功能的自包含包 (当前可留空)

  assets/
    styles/
      theme/             # Ant Design 主题变量、全局 SCSS、dark-mode
      mixins/            # SCSS mixins & functions
    i18n/                # 国际化资源 (未来需要再加)
    icons/               # SVG 图标
    mock/                # 如需本地 mock 数据 (开发阶段)

  environments/          # 环境配置 Angular 原生方式
    environment.ts
    environment.prod.ts
    environment.dev.ts   # 可增加自定义

  main.ts                # bootstrap, 提供全局 providers
  app.config.ts          # provideRouter 等 Angular 17 config 化配置
  styles.scss            # 全局样式入口
  theme.less             # 若采用 AntD less 变量自定义
```

### 命名约定
- 目录名使用 kebab-case；TypeScript 类型与类 PascalCase。  
- Feature 内页面组件使用后缀 `Page`；可复用局部组件后缀 `Card`, `Panel`, `Widget` 根据语义。  
- Signals state service 可命名 `XxxStore` 或 `XxxState`。  

## 4. 分层职责说明

| 层        | 职责 | 不做的事情 |
|-----------|------|------------|
| core      | 应用生命周期、全局服务、拦截器、守卫、配置整合 | 不放业务特定逻辑或特性页面 |
| shared    | 纯粹复用，无业务语义，UI 基础、工具、模型 | 不直接调用业务 API，不持久存状态 |
| data-access | 统一所有外部数据源的访问与适配 | 不进行复杂视图逻辑，不决定展示形式 |
| features  | 业务组合、页面、局部状态，协调 data-access 与 shared | 不包含跨域的全局单例 |
| charts    | 针对金融可视化的抽象层，封装图表库差异 | 不直接耦合业务 state | 

## 5. 路由与懒加载策略

- 使用 Angular 17 Standalone + `provideRouter()`，每个 Feature 暴露自身的 `routes`。  
- 顶级路由分组示例：
  - `/dashboard`
  - `/market` (market-data)
  - `/portfolio`
  - `/backtest`
  - `/analytics`
  - `/admin`
  - `/cronjobs` (新增：定时任务管理)
- 可选添加 preloading 策略：对常用模块使用自定义 Preload (后续再加)。

## 6. 状态管理策略（初期）

1. 局部状态：Feature 内通过 Service + `signal()` 管理。  
2. 全局状态：仅用户信息、主题、布局折叠状态等放 core/state。  
3. 数据流：API -> data-access service -> Feature store -> 视图组件。  
4. 后续增长：如果出现跨 Feature 复杂协作，再考虑引入 NgRx 或 Signals Store。  

示例（伪代码）：
```ts
@Injectable({ providedIn: 'root' })
export class PortfolioStore {
  private _positions = signal<Position[]>([]);
  readonly positions = computed(() => this._positions());

  constructor(private api: PortfolioApiService) {}

  load() {
    this.api.getPositions().subscribe(data => this._positions.set(data));
  }
}
```

## 7. Ant Design Layout 集成策略

- 在 `shared/ui/layout` 下封装基础布局：`AppLayoutComponent` (包含 `nz-layout`, `nz-sider`, `nz-header`, `nz-content`)。  
- 使用 Input/Content Projection 提供：菜单项、页头操作区、面包屑。  
- 全局样式中集中定义主题变量：`theme.less` 或 SCSS 覆盖。  
- 暗色/亮色：在 LayoutService 中维护一个 signal，利用 class 切换。  
- 只在布局层使用原始 AntD 组件；业务组件优先封装后再用。  

主题变量（示例）：
```less
@primary-color: #1677ff;
@border-radius-base: 4px;
@font-size-base: 14px;
```

## 8. 图表封装策略

`shared/charts` 提供最小包装：
- `BaseChartComponent`：输入 data / options。  
- `CandleChartComponent`：K 线专用，内部把外部 data 映射为 ECharts series。  
- 保持库替换可能性：对外暴露统一 Input 接口，不在业务中直接写 ECharts option。  

未来扩展：
- 指标计算（MA、MACD） -> 可在 `utils/math` 或 `features/analytics`。  
- 图表性能优化：虚拟滚动、增量更新、worker 计算。  

## 9. API 与数据访问规范

- 每个域一个 Service：`MarketDataApiService`、`PortfolioApiService` 等。  
- Service 返回 `Observable` 或直接 `Promise`（使用 `firstValueFrom`）视具体需求。大量实时行情可用 `websocket`/`SSE`。  
- 拦截器：统一添加认证头、错误处理、重试策略。  
- 数据模型放在 `shared/models` 或域内部 `features/<domain>/models`（如果仅域内使用）。  

接口定义示例：
```ts
export interface Position {
  symbol: string;
  quantity: number;
  avgPrice: number;
  pnl: number;
}
```

## 10. 错误与日志

- 全局错误处理：`GlobalErrorHandler` + HTTP 拦截器。  
- UI 提示：抽象一个 `NotificationService` 封装 AntD message/notification。  
- 后续需要时可将关键操作日志发送到后端。

## 11. 渐进增强清单（后续再做，不在当前骨架实现）

| 功能 | 触发条件 | 方案 |
|------|----------|------|
| 复杂跨域状态 | 多 Feature 协同、Undo/Redo 需求 | 引入 NgRx 或 Signals Store | 
| 插件机制 | 需要外部扩展或实验功能快速集成 | Module Federation 或动态导入 | 
| 国际化 | 需要多语言 | `@ngx-translate/core` + i18n 资源 | 
| 权限控制 | 角色多样化 | Route Guard + 指令 `*hasPermission` | 
| WebSocket 实时 | 行情与策略回测结果实时刷新 | 专用 `RealtimeService` + subject/signal | 
| Worker 计算 | 大量指标计算阻塞 UI | Web Worker + message channel | 

## 12. 初始创建建议脚本（可选执行）

安装依赖：
```
npm install ng-zorro-antd @angular/cdk echarts ngx-echarts dayjs --save
```

在 `main.ts` 中引入 AntD 所需的国际化与图标（后续再具体配置）。

## 13. 起步里程碑

1. 搭建基础目录与占位文件（空组件/空服务）。  
2. 建立 `AppLayoutComponent` + 顶级路由框架。  
3. 引入一个示例 Feature：`dashboard`（显示占位卡片 + 示例图表）。  
4. 接入一个简单 API（可用 mock），验证 data-access 流程。  
5. 确认主题与暗色模式切换机制。  

## 14. 不过度设计的边界说明

- 不提前放置未使用的状态管理框架。  
- 不创建抽象层级过多（例如 `Repository -> Service -> Adapter -> Mapper` 仅在确有差异时添加）。  
- 不实现复杂权限、国际化、插件系统等，除非业务触发。  
- 图表封装保持最小原则：先解决重复代码再抽象。  

## 15. 评审关注点建议

在你评审本架构时，可考虑：
- 是否需要再拆分 `charts` 为独立 library？（当前建议保留在 shared）  
- 管理工具（admin-tools）是否需要单独的访问控制层？  
- 是否需要现在就接入多语言？（如短期不需要，可延后）  
- 行情数据实时性是否决定我们尽早规划 WebSocket 目录？  

---

这是初稿，欢迎提出：要删减的部分 / 要加的部分 / 哪些目录你希望现在就创建。确认后我可以帮助生成占位文件与基础代码。

## 16. 多层级 pages 目录深度规范（针对方案 A 的疑问）

> 问题：在方案 A 中，如果后续子页面继续增加，直接在 `pages/` 下不断增加嵌套层级是否可以？

### 结论简述
- 建议最大“有效深度”不超过 2 层：`pages/<group>/...`。
- 第 3 层开始（例如 `pages/cronjob-detail/logs/raw/`）往往意味着应该拆分结构（分组、组件内 Tab、或抽为独立 Feature）。
- 深度的本质是认知与耦合成本，而不是技术不可行性。Angular 路由可以支持很深，但可维护性会下降。

### 为什么不鼓励无限嵌套
1. 认知负担：开发者需要记忆路径层次，跳转查找时间上升。  
2. 跨目录共享：深层页面往往需要访问浅层 state，产生向上依赖或把 state 拉成全局。  
3. 重构成本：一旦需要拆分懒加载，深度结构下文件分散难以批量移动。  
4. 路由耦合：深路径往往包含资源标识 + 语义片段，如 `/cronjobs/:id/logs/raw/error`; 业务变化时 URL 与目录耦合太紧难以重构。  
5. 测试与 Storybook 组织：storybook/测试样例路径冗长，影响可读性。  

### 合理的层级模式示例
```
features/cronjobs/
  pages/
    cronjobs-list.page.ts
    cronjob-create.page.ts
    cronjob-detail/            # 第 1 层分组（详情域）
      cronjob-detail.page.ts   # 详情容器 (含 router-outlet 或 tabs)
      cronjob-history.page.ts
      cronjob-logs.page.ts
      cronjob-metrics.page.ts  # 子页面（第 2 层）
```
保持分组目录只有一层；子页面文件直接放在该分组下，不再继续子分组。

### 何时需要考虑再深入一层（第 3 层）但仍保留在 A
仅当：
- 你的某个子域（例如 logs）内部存在多种呈现视图（列表 / 原始流 / 聚合统计），且这些视图之间共享专有局部状态不与其它详情子页共享。  
- 该子域内部仍很轻量（<4 文件），并且你确定短期不会再扩展。  

即便如此，也优先使用组件内 Tab 或 `components/` 拆分而非目录深度：
```
cronjob-logs.page.ts        # 页面容器 (Tab 切换)
components/
  cronjob-log-raw-panel.component.ts
  cronjob-log-aggregated-panel.component.ts
  cronjob-log-stream-panel.component.ts
```

### 拆分或重构的触发阈值（从继续嵌套 -> 结构调整）
| 触发条件 | 调整动作 |
|----------|----------|
| 分组目录下页面 >5 个 | 抽为独立 Feature 或使用 Tab 内聚集 | 
| 分组目录内出现第 3 层目录 | 评估改为组件 + Tab；或独立 Feature | 
| 子域需要额外第三方依赖 | 独立 Feature 懒加载 | 
| 子域有独立的复杂状态（多个 store） | 独立 Feature | 
| URL 要求可深链到多个子视图并分享 | 保留路由，但不要增加物理深度，使用扁平 children | 

### 改善深度的替代手段
1. Tab 组件：一个父页面 + 若干面板组件（不新增路由层级）。  
2. 路由 children 扁平化：路径深但目录不深。例如：
   - 目录：`pages/cronjob-detail/*` 扁平；
   - 路由：`/cronjobs/:id/logs/raw`、`/cronjobs/:id/logs/stream` 仍可存在。  
3. 独立 Feature：`features/cronjob-logs/` 与 `features/cronjob-detail/` 分离。  
4. 动态组件映射：用枚举或配置驱动不同视图在线加载，无需物理目录深度。  

### 推荐深度规则速记
- pages 根下：放 Feature 顶级页面。  
- 第 1 层分组：资源子域（detail、settings、wizard）。  
- 不新增第 2 层以上的分组目录；子页面文件直接放在分组下。  
- 若想再继续细分：优先使用组件目录或抽出子 Feature，而不是继续 `pages/.../.../`。  

### 演进示例：从 A 深化到 B
初始 (A)：
```
pages/
  cronjobs-list.page.ts
  cronjob-create.page.ts
  cronjob-detail/
    cronjob-detail.page.ts
    cronjob-history.page.ts
    cronjob-logs.page.ts
    cronjob-metrics.page.ts
```
增长后发现 logs 下还要 `raw`, `stream`, `error` 三种：
迁移 (B)：
```
features/
  cronjobs/...
  cronjob-detail/...
  cronjob-logs/   # 新 Feature, 专注日志子域
    cronjob-logs.routes.ts
    pages/
      cronjob-logs.page.ts
      cronjob-log-raw.page.ts
      cronjob-log-stream.page.ts
      cronjob-log-error.page.ts
```
路由调整：把原 `:id/logs` 的 children 指向新懒加载 Feature。

### Anti-Pattern 示例（应避免）
```
pages/
  cronjob-detail/
    logs/
      raw/
        raw-table.page.ts
        raw-detail.page.ts
      aggregated/
        aggregated-summary.page.ts
        aggregated-detail.page.ts
      stream/
        stream-live.page.ts
```
问题：目录过深、上下层状态难以清晰分配、文件查找困难。

### 决策流程（简单问答）
1. 新增子视图是否只是同类数据的展示形式切换？ → 用组件/Tab。  
2. 是否需要单独的路由 URL 分享？ → 用 children 路由但保持物理目录不加深。  
3. 是否有额外依赖 + 独立生命周期？ → 独立 Feature。  
4. 是否超过页面数量阈值？（>5） → 拆。  

### TL;DR
“能继续嵌套” ≠ “应该继续嵌套”。保持 2 层限制让迁移路径简单；超出时，通过组件、路由扁平化或独立 Feature 分解复杂度。

## 附录：Cron Jobs Feature 结构说明（新增）

本次实现将原先的 mock `overview` 页面移除，替换为：
- `TaskListPageComponent` (`pages/task-list.page.ts`): 列出后端 `Task`，支持启用/禁用、手动触发、刷新缓存。
- `TaskDetailPageComponent` (`pages/task-detail.page.ts`): 展示单个任务详情与最近运行 `TaskRun` 列表，支持刷新、手动触发、状态切换。
- 路由调整：`/cronjobs/tasks` 与 `/cronjobs/task/:id`，保持浅层级，后续如需扩展运行日志细分视图优先通过组件内 Tab 或拆分独立 Feature。
- 数据访问：`CronjobsApiService` 对接后端 REST `/api/v1/tasks` 与 `/api/v1/runs` 等端点，前端模型与 Go 结构体字段一一对应（使用 snake_case 保持兼容）。
- 状态管理：`CronjobsStore` 使用 Angular signals，以 task_id 为 key 缓存运行记录，避免重复请求；提供 `enable/disable/trigger/refreshCache` 操作方法。

后续可扩展项：
1. 创建/编辑任务表单（需要对 `headers_json` 与 `retry_policy_json` 做结构化编辑器）。
2. 运行记录过滤与分页（当前直接全量显示）。
3. 失败运行的高亮与统计（可在 store 中增加派生 computed）。
4. 长轮询或 SSE 实时刷新运行状态。
5. 权限与审计：操作（手动触发、启用/禁用）加入确认与权限校验。

设计守则回顾：保持 2 层 pages 深度；复杂子域（如 logs 未来细分）达到扩展阈值后抽取为新 Feature，而不是继续加深目录。
