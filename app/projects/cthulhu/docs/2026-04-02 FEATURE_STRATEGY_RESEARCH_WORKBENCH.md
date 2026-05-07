# FEATURE: Strategy Research Workbench（策略研发工作台）

> 日期：2026-04-02
> 状态：设计阶段
> 影响项目：Cthulhu（前端）、Artemis（后端）

---

## 0. 文档目标

本文档描述 Cthulhu 前端策略研发工作台的设计与实施计划。工作台是一个交互式页面，让用户可以快速选择策略、配置参数、运行回测并查看结果。

---

## 1. 背景与目标

### 1.1 用户场景

研发人员需要快速验证一个策略想法：
1. 选择策略（如 SMA 均线交叉）
2. 输入股票代码（如 sh600519）
3. 选择时间范围（如 2024 全年）
4. 配置策略参数（如快线 10 天、慢线 30 天）
5. 点击运行
6. 立即看到权益曲线、买卖信号、统计数据

### 1.2 核心需求

- **策略参数动态化**：不同策略有不同参数，页面根据后端返回的 `param_schema` 动态渲染表单
- **即时反馈**：同步请求，运行后直接展示结果
- **可视化**：权益曲线 + 买卖信号 + 统计卡片
- **MVP 不落库**：结果仅在页面展示

---

## 2. 前端架构

### 2.1 功能模块结构

```
src/app/features/workbench/
  workbench.routes.ts                    -- 路由定义
  index.ts                               -- barrel export
  pages/
    workbench-shell.component.ts         -- 路由外壳 (router-outlet)
    workbench-research.page.ts           -- 主页面（配置 + 结果）
  models/
    workbench.model.ts                   -- TypeScript interfaces
  services/
    workbench-api.service.ts             -- HTTP API 调用
  state/
    workbench.store.ts                   -- Signals-based 状态管理
  ui/
    strategy-config.component.ts         -- 策略选择 + 动态参数表单
    backtest-chart.component.ts          -- ECharts 权益曲线 + 信号散点
    backtest-stats.component.ts          -- 统计卡片
```

### 2.2 数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Workbench   │────>│  Workbench   │────>│  Artemis     │
│  Research    │     │  Api Service │     │  Backend     │
│  Page        │     │              │     │              │
│              │<────│  (Observable)│<────│  (JSON)      │
│  (Store)     │     └──────────────┘     └──────────────┘
└──────────────┘
       │
       ├──> strategy-config  (输入)
       ├──> backtest-chart    (图表)
       └──> backtest-stats    (统计)
```

---

## 3. 路由设计

### 3.1 路由注册

**修改：`src/app/routing/app.routes.ts`**

```typescript
{
  path: 'workbench',
  loadChildren: () => import('../features/workbench/workbench.routes').then(m => m.WORKBENCH_ROUTES)
}
```

### 3.2 路由定义

**新文件：`workbench.routes.ts`**

```typescript
export const WORKBENCH_ROUTES: Routes = [
  {
    path: '',
    component: WorkbenchShellComponent,
    data: {
      breadcrumb: 'Workbench',
      menuGroup: { title: 'Workbench', icon: 'line-chart' }
    },
    children: [
      {
        path: '',
        redirectTo: 'research',
        pathMatch: 'full'
      },
      {
        path: 'research',
        component: WorkbenchResearchPageComponent,
        data: {
          breadcrumb: 'Strategy Research',
          menu: { label: 'Strategy Research', order: 1 }
        }
      }
    ]
  }
];
```

### 3.3 导航栏

**修改：`src/app/core/services/top-nav.service.ts`**

添加 Workbench 导航项：

```typescript
{ key: 'workbench', label: 'Workbench', icon: 'line-chart', path: '/workbench' }
```

需要在 `app.config.ts` 中注册 `LineChartOutline` 图标。

---

## 4. Models

**新文件：`models/workbench.model.ts`**

```typescript
// ===== 策略相关 =====

export interface StrategyParamSchema {
  type: 'int' | 'float' | 'string' | 'bool';
  min?: number;
  max?: number;
  required?: boolean;
}

export interface WorkbenchStrategy {
  code: string;
  default_params: Record<string, any>;
  supported_modes: string[];
  supported_timeframes: string[];
  param_schema: Record<string, StrategyParamSchema>;
}

export interface WorkbenchStrategiesResponse {
  strategies: WorkbenchStrategy[];
}

// ===== 请求 =====

export interface WorkbenchRunRequest {
  strategy_code: string;
  symbol: string;
  start_date: string;          // YYYY-MM-DD
  end_date: string;            // YYYY-MM-DD
  timeframe: string;
  adjust: string;
  cash: number;
  commission: number;
  strategy_params: Record<string, any>;
}

// ===== 响应 =====

export interface EquityPoint {
  timestamp: string;
  close: number;
  cash: number;
  value: number;
}

export interface SignalEvent {
  timestamp: string;
  signal: 'BUY' | 'SELL';
  close: number;
}

export interface TradeEvent {
  timestamp: string;
  size: number;
  price: number;
  pnl: number;
  pnlcomm: number;
  barlen: number;
}

export interface OrderEvent {
  timestamp: string;
  status: string;
  order_type: 'BUY' | 'SELL';
  size: number;
  price: number;
  value: number;
  commission: number;
}

export interface BacktestSummary {
  strategy_code: string;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  start_cash: number;
  end_value: number;
  pnl: number;
  pnl_pct: number;
  max_drawdown: number;
  sharpe: number;
  bars_processed: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
}

export interface BacktestArtifacts {
  equity_curve: EquityPoint[];
  signals: SignalEvent[];
  trades: TradeEvent[];
  orders: OrderEvent[];
  positions: any[];
}

export interface BacktestResult {
  run_meta: {
    run_id: string;
    parent_run_id: string | null;
    task_code: string;
  };
  summary: BacktestSummary;
  artifacts: BacktestArtifacts;
}
```

---

## 5. API Service

**新文件：`services/workbench-api.service.ts`**

```typescript
@Injectable({ providedIn: 'root' })
export class WorkbenchApiService {
  private API_BASE = environment.artemisApiBase;

  constructor(private http: HttpClient) {}

  /** 获取策略列表（含参数 schema） */
  getStrategies(): Observable<WorkbenchStrategiesResponse> {
    return this.http.get<WorkbenchStrategiesResponse>(`${this.API_BASE}/workbench/strategies`);
  }

  /** 运行回测 */
  runBacktest(req: WorkbenchRunRequest): Observable<BacktestResult> {
    return this.http.post<BacktestResult>(`${this.API_BASE}/workbench/run`, req);
  }
}
```

---

## 6. State Management (Store)

**新文件：`state/workbench.store.ts`**

遵循项目现有的 `CronjobsStore` 模式（injectable + signals）：

```typescript
@Injectable({ providedIn: 'root' })
export class WorkbenchStore {
  // --- State signals ---
  private readonly _strategies = signal<WorkbenchStrategy[]>([]);
  private readonly _selectedStrategy = signal<WorkbenchStrategy | null>(null);
  private readonly _result = signal<BacktestResult | null>(null);
  private readonly _loading = signal(false);         // 加载策略列表
  private readonly _running = signal(false);          // 回测运行中
  private readonly _error = signal<string | null>(null);

  // --- Public readonly ---
  readonly strategies = computed(() => this._strategies());
  readonly selectedStrategy = computed(() => this._selectedStrategy());
  readonly result = computed(() => this._result());
  readonly loading = computed(() => this._loading());
  readonly running = computed(() => this._running());
  readonly error = computed(() => this._error());

  constructor(private api: WorkbenchApiService) {}

  /** 页面初始化时加载策略列表 */
  loadStrategies(): void {
    this._loading.set(true);
    this.api.getStrategies().subscribe({
      next: (resp) => {
        this._strategies.set(resp.strategies);
        this._loading.set(false);
      },
      error: (err) => {
        this._error.set('加载策略列表失败');
        this._loading.set(false);
      }
    });
  }

  /** 选择策略 */
  selectStrategy(code: string): void {
    const strategy = this._strategies().find(s => s.code === code) ?? null;
    this._selectedStrategy.set(strategy);
    this._result.set(null);  // 切换策略时清空上次结果
  }

  /** 运行回测 */
  runBacktest(req: WorkbenchRunRequest): void {
    this._running.set(true);
    this._error.set(null);
    this.api.runBacktest(req).subscribe({
      next: (result) => {
        this._result.set(result);
        this._running.set(false);
      },
      error: (err) => {
        this._error.set(err.error?.detail ?? err.message ?? '回测运行失败');
        this._running.set(false);
      }
    });
  }

  /** 清空结果 */
  clearResult(): void {
    this._result.set(null);
    this._error.set(null);
  }
}
```

---

## 7. UI 组件设计

### 7.1 Strategy Config Component

**文件：`ui/strategy-config.component.ts`**

布局：使用 `nz-card` 包裹，`nz-form` 布局

```
┌─────────────────────────────────────────────────────────────┐
│ 策略配置                                                     │
├─────────────────────────────────────────────────────────────┤
│ 策略选择：[ ▼ SMA Cross ]                                    │
│                                                             │
│ ── 策略参数 ──────────────────────────────────               │
│ 快线天数 (fast)：  [  10  ]  (min: 1)                        │
│ 慢线天数 (slow)：  [  30  ]  (min: 1)                        │
│ 手数 (stake)：     [   1  ]  (min: 1)                        │
│                                                             │
│ ── 数据与时间 ────────────────────────────────               │
│ 股票代码：  [ sh600519     ]                                 │
│ 开始日期：  [ 2024-01-01 ]                                   │
│ 结束日期：  [ 2024-12-31 ]                                   │
│                                                             │
│ ── 资金设置 ────────────────────────────────                 │
│ 初始资金：  [  100000  ]                                     │
│ 手续费率：  [    0    ]                                      │
│                                                             │
│                      [ 运行回测 ]                             │
└─────────────────────────────────────────────────────────────┘
```

**动态参数表单逻辑：**

当用户选择不同策略时，从 `store.selectedStrategy().param_schema` 读取参数定义，动态渲染表单控件：

- `type: 'int'` → `nz-input-number`，`[nzMin]` 来自 schema 的 `min`
- 默认值来自 `default_params`
- 参数数量和名称完全由后端 `param_schema` 决定

**这意味着添加新策略时，前端代码不需要修改。**

### 7.2 Backtest Chart Component

**文件：`ui/backtest-chart.component.ts`**

使用 `ngx-echarts` 渲染，接受 `BacktestArtifacts` 作为 `@Input()`。

**图表布局：**

```
┌─────────────────────────────────────────────────────────────┐
│ ┌─ Tooltip ──────────────┐                                  │
│ │ 2024-06-15             │                                  │
│ │ Value: ¥103,200        │                                  │
│ │ Signal: BUY @ 1750.0   │                                  │
│ └────────────────────────┘                                  │
│  ¥105k ┤                                          ▲         │
│        │                              ╱  ╲       ╱  ╲       │
│  ¥102k ┤          ╱  ╲           ╱  ╱    ╲    ╱      ╲     │
│        │     ╱  ╱      ╲    ╱  ╱           ╲╱          ╲   │
│  ¥100k ┤╱  ╱              ╲╱                                │
│        │ △                          ▽                        │
│   ¥98k ┤                                                   │
│        ├──────┬──────┬──────┬──────┬──────┬──────┬──────┤   │
│       Jan    Mar    May    Jul    Sep    Nov    Jan        │
│  ════════════════════════════════════════════════════════   │
│  ◄───────────── Zoom Slider ──────────────────────►        │
└─────────────────────────────────────────────────────────────┘

图例：
  ── 权益曲线 (蓝色实线)
  ▲  买入信号 (绿色三角)
  ▼  卖出信号 (红色倒三角)
```

**ECharts Option 结构：**

```typescript
{
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'cross' }
  },
  legend: {
    data: ['Portfolio Value', 'Buy', 'Sell']
  },
  grid: {
    left: '3%', right: '4%', bottom: '15%', containLabel: true
  },
  xAxis: {
    type: 'category',
    data: timestamps,        // equity_curve[].timestamp (YYYY-MM-DD)
    boundaryGap: false
  },
  yAxis: [{
    type: 'value',
    name: 'Value (¥)',
    position: 'left'
  }],
  dataZoom: [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', start: 0, end: 100 }
  ],
  series: [
    {
      name: 'Portfolio Value',
      type: 'line',
      data: values,            // equity_curve[].value
      smooth: true,
      lineStyle: { width: 2, color: '#1890ff' },
      areaStyle: { opacity: 0.1, color: '#1890ff' }
    },
    {
      name: 'Buy',
      type: 'scatter',
      data: buySignals,        // signals filter BUY → [timestamp, close]
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#52c41a' }
    },
    {
      name: 'Sell',
      type: 'scatter',
      data: sellSignals,       // signals filter SELL → [timestamp, close]
      symbol: 'triangle',
      symbolSize: 12,
      symbolRotate: 180,
      itemStyle: { color: '#ff4d4f' }
    }
  ]
}
```

### 7.3 Backtest Stats Component

**文件：`ui/backtest-stats.component.ts`**

使用 `nz-statistic` 组件展示关键指标，接受 `BacktestSummary` 作为 `@Input()`。

**布局：**

```
┌───────────┬───────────┬───────────┬───────────┐
│   盈亏     │   收益率   │   胜率     │   夏普比   │
│  +5,230   │  +5.23%   │  62.5%    │   1.23    │
│  (绿色)    │  (绿色)    │           │           │
├───────────┼───────────┼───────────┼───────────┤
│  最大回撤   │  交易次数   │  赢的次数   │  K线数量   │
│   3.21%   │     8     │     5     │    242    │
│  (红色)    │           │           │           │
└───────────┴───────────┴───────────┴───────────┘
```

**颜色规则：**
- PnL > 0 → 绿色 (`#52c41a`)，PnL < 0 → 红色 (`#ff4d4f`)
- 收益率同上
- 回撤始终红色

### 7.4 主页面布局

**文件：`pages/workbench-research.page.ts`**

```
┌──────────────────────────────────────────────────────────────┐
│  Strategy Research                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Strategy Config ──────────────────────────────────────┐  │
│  │  [策略选择] [动态参数] [股票] [时间] [资金] [运行按钮]    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Results (运行后显示) ─────────────────────────────────┐  │
│  │                                                        │  │
│  │  ┌── Backtest Stats ──────────────────────────────┐    │  │
│  │  │ [PnL] [收益率] [胜率] [夏普] [回撤] [交易数]      │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  ┌── Backtest Chart ──────────────────────────────┐    │  │
│  │  │                                                │    │  │
│  │  │  [权益曲线 + 买卖信号]                           │    │  │
│  │  │                                                │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  │                                                        │  │
│  │  ┌── Trades Table (可选) ─────────────────────────┐    │  │
│  │  │ 时间 | 数量 | 价格 | 盈亏 | 持仓天数             │    │  │
│  │  └────────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. ECharts 配置

### 8.1 模块注册

**修改：`src/app/app.config.ts`**

```typescript
import { provideEchartsCore } from 'ngx-echarts/core';
import * as echarts from 'echarts/core';
import { LineChart, ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 注册必要的 ECharts 模块（tree-shaking）
echarts.use([
  LineChart, ScatterChart,
  GridComponent, TooltipComponent, LegendComponent, DataZoomComponent,
  CanvasRenderer
]);
```

在 `appConfig.providers` 中添加：

```typescript
provideEchartsCore({ echarts })
```

### 8.2 图标注册

在 `app.config.ts` 的 NZ_ICONS 列表中添加：

```typescript
import { LineChartOutline } from '@ant-design/icons-angular/icons';
// 加入 NZ_ICONS 数组
```

---

## 9. 新增策略的前端流程

当后端新增一个策略（如 RSI）时：

1. 后端在 `strategy_engine/strategies/` 添加策略并注册
2. 前端页面自动反映：
   - `GET /workbench/strategies` 返回新策略
   - 策略下拉框自动出现新选项
   - 选择后 `param_schema` 驱动表单自动渲染新参数字段
3. **无需修改任何前端代码**

示例：假设添加 RSI 策略，其 `param_schema` 为：

```json
{
  "period": {"type": "int", "min": 2},
  "overbought": {"type": "int", "min": 50, "max": 100},
  "oversold": {"type": "int", "min": 0, "max": 50}
}
```

前端会自动渲染 3 个 `nz-input-number` 字段，默认值来自 `default_params`。

---

## 10. 实施步骤

### Step 1: 创建 Models

- [ ] 创建 `models/workbench.model.ts` — 所有 TypeScript interfaces

### Step 2: 创建 API Service

- [ ] 创建 `services/workbench-api.service.ts` — getStrategies() + runBacktest()

### Step 3: 创建 Store

- [ ] 创建 `state/workbench.store.ts` — Signals-based state management

### Step 4: 创建 UI 组件

- [ ] 创建 `ui/strategy-config.component.ts` — 策略选择 + 动态参数表单
- [ ] 创建 `ui/backtest-chart.component.ts` — ECharts 权益曲线 + 信号散点
- [ ] 创建 `ui/backtest-stats.component.ts` — 统计卡片

### Step 5: 创建页面和路由

- [ ] 创建 `pages/workbench-shell.component.ts` — 路由外壳
- [ ] 创建 `pages/workbench-research.page.ts` — 主页面
- [ ] 创建 `workbench.routes.ts` — 路由定义
- [ ] 创建 `index.ts` — barrel export

### Step 6: 注册路由和导航

- [ ] 修改 `routing/app.routes.ts` — 添加 lazy-loaded workbench 路由
- [ ] 修改 `core/services/top-nav.service.ts` — 添加 Workbench 导航项
- [ ] 修改 `app.config.ts` — 注册 ECharts providers + 图标

### Step 7: 验证

- [ ] 页面加载时自动拉取策略列表
- [ ] 选择策略后动态渲染参数表单
- [ ] 填入参数点击运行，展示权益曲线和统计卡片
- [ ] 切换策略时清空结果、重新渲染参数表单
- [ ] 错误场景显示错误提示

---

## 11. 依赖说明

| 依赖 | 版本 | 说明 |
|------|------|------|
| ngx-echarts | 17.0.0 | 已安装，Angular ECharts 绑定 |
| echarts | 5.5.x | 已安装，图表引擎 |
| ng-zorro-antd | 17.0.x | 已安装，UI 组件库 |
| Angular | 17.3.x | 已安装 |
| RxJS | 7.8.x | 已安装 |

无需安装新依赖。

---

## 12. 未来扩展

| 扩展项 | 说明 |
|--------|------|
| 多股票对比 | 同时运行多个股票，展示对比图表 |
| 交易明细表 | 在图表下方添加 trades/orders 的 nz-table |
| 回撤子图 | 在权益曲线下方添加回撤面积图 |
| 导出报告 | 添加"导出 PDF/图片"按钮 |
| 参数对比 | 支持同策略不同参数的对比视图 |
| 历史记录 | 保存最近 N 次运行结果，可切换查看 |

---

## 13. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `features/workbench/models/workbench.model.ts` | **NEW** | TS interfaces |
| `features/workbench/services/workbench-api.service.ts` | **NEW** | HTTP API |
| `features/workbench/state/workbench.store.ts` | **NEW** | Store (Signals) |
| `features/workbench/ui/strategy-config.component.ts` | **NEW** | 策略选择 + 动态参数 |
| `features/workbench/ui/backtest-chart.component.ts` | **NEW** | ECharts 图表 |
| `features/workbench/ui/backtest-stats.component.ts` | **NEW** | 统计卡片 |
| `features/workbench/pages/workbench-shell.component.ts` | **NEW** | 路由外壳 |
| `features/workbench/pages/workbench-research.page.ts` | **NEW** | 主页面 |
| `features/workbench/workbench.routes.ts` | **NEW** | 路由定义 |
| `features/workbench/index.ts` | **NEW** | Barrel export |
| `routing/app.routes.ts` | **MODIFY** | 添加 workbench lazy route |
| `core/services/top-nav.service.ts` | **MODIFY** | 添加导航项 |
| `app.config.ts` | **MODIFY** | ECharts providers + 图标 |
