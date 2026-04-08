# FEATURE: Workbench 多环境数据源切换

## 文档信息
- 日期: 2026-04-07
- 类型: Feature Proposal
- 模块: Artemis (backend) + Cthulhu (frontend)
- 状态: Draft

## 1. 背景与动机

当前 Workbench 的策略研究和市场数据功能依赖 PhoenixA 数据服务。

- **dev 环境**：PhoenixA 数据量有限，无法充分验证策略效果
- **prod 环境**：PhoenixA 拥有完整历史数据，适合策略开发和实验
- **当前切换成本**：需要重新编译前端（`ng build --configuration prod`）+ 重启后端（`-e prod`），中断工作流

**目标**：在 Workbench 页面内实现 **运行时** 环境切换（dev/prod），无需重新编译或重启，即可访问不同环境的数据源。

## 2. 现状分析

### 2.1 Artemis 后端

| 项 | 现状 |
|---|---|
| 配置加载 | `config_manager.py` 启动时加载 **一个** config 文件（基于 CLI `--env`） |
| 配置文件 | 已有 3 套：`config.yaml`(dev)、`config-home.yaml`、`config-prod.yaml` |
| 数据源 | 每套配置的 `dept_services.phoenixA` 指向不同 PhoenixA 实例 |
| Workbench 服务 | `market_data.py`、`backtest.py` 通过 `_build_phoenix_client()` 连接当前环境 |

**各环境 PhoenixA 端点**：

| 环境 | PhoenixA 地址 |
|---|---|
| dev | `127.0.0.1:18085` |
| home | `192.168.31.72:8085` |
| prod | `192.168.31.142:8085` |

### 2.2 Cthulhu 前端

| 项 | 现状 |
|---|---|
| 环境配置 | `environment.ts` 等 3 个文件在 **编译时** 替换 |
| API 基地址 | `workbench-api.service.ts` 所有请求发往 `environment.artemisApiBase` |
| 切换方式 | 只能通过 `ng build --configuration <env>` 切换，运行时无法更改 |

### 2.3 核心洞察

```
前端 ──HTTP──→ 本地 Artemis ──HTTP──→ PhoenixA (数据源)
                                      ↑
                                   真正的差异点
```

前端永远只连 **本地 Artemis**。环境之间的差异仅在 **Artemis → PhoenixA** 这一层。因此 **环境切换应由 Artemis 处理**，前端只需传递一个 `env` 参数。

## 3. 方案设计

### 3.1 架构原则

1. **前端始终连本地 Artemis** — 无跨域、无安全问题
2. **Artemis 启动时加载所有环境配置** — 仅 `dept_services` 段
3. **Workbench API 新增 `env` 参数** — 按需创建对应环境的 PhoenixA client
4. **前端增加环境选择器** — 下拉框 + localStorage 持久化

### 3.2 数据流

```
┌─────────────────────┐
│  Cthulhu (前端)       │
│  ┌───────────────┐  │
│  │ Env Selector  │──┼── selectedEnv = "prod"
│  │  (localStorage)│  │
│  └───────────────┘  │
│         │            │
│         ▼            │
│  GET /workbench/market-data?env=prod&symbol=000001&...
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Artemis (本地后端)   │
│                      │
│  cfg_mgr             │
│  ├─ env_configs:     │
│  │  ├─ "dev"  → { phoenixA: 127.0.0.1:18085 }
│  │  ├─ "home" → { phoenixA: 192.168.31.72:8085 }
│  │  └─ "prod" → { phoenixA: 192.168.31.142:8085 }
│  │                    │
│  └─ market_data_service.get_market_bars(env="prod")
│         │              │
│         ▼              │
│  PhoenixA (prod) ──────┼── 192.168.31.142:8085
│  返回完整历史数据       │
└──────────────────────┘
```

## 4. 后端改动 (Artemis)

### 4.1 ConfigManager 多环境支持

**文件**: `artemis/core/config_manager.py`

新增 3 个方法：

```python
def _scan_env_configs(self) -> Dict[str, DeptServicesConfig]:
    """扫描 config 目录下所有 config-*.yaml，提取各环境的 dept_services。
    
    - config.yaml         → "dev"
    - config-home.yaml    → "home"  
    - config-prod.yaml    → "prod"
    """

def get_dept_services_for_env(self, env_name: str | None) -> DeptServicesConfig:
    """返回指定环境的 dept_services，env_name 为 None 或不存在时回退到主配置。"""

def available_envs(self) -> list[str]:
    """返回所有可用环境名列表，如 ['dev', 'home', 'prod']。"""
```

启动时自动扫描，结果缓存在内存中。

### 4.2 Workbench 服务 env 参数

**文件**: `artemis/services/workbench/market_data.py`

```python
def get_market_bars(*, symbol, start_date, end_date, 
                    timeframe="daily", adjust="nf", env=None):
    client = _build_phoenix_client(env=env)  # 传入 env
    ...
```

**文件**: `artemis/services/workbench/backtest.py`

```python
def run_backtest(req: WorkbenchRunReq, env=None):
    phoenix_client = _build_phoenix_client(env=env)
    ...
```

**共用 `_build_phoenix_client` 更新**（两个文件各自有，或提取到 `_client_factory.py`）：

```python
def _build_phoenix_client(env: str | None = None) -> PhoenixAClient:
    dept = cfg_mgr.get_dept_services_for_env(env)
    ...
```

### 4.3 API 路由

**文件**: `artemis/api/http_gateway/workbench_routes.py`

| 端点 | 改动 |
|---|---|
| `GET /workbench/envs` | **新增** — 返回 `{ "envs": ["dev","home","prod"], "default": "dev" }` |
| `GET /workbench/market-data` | 增加 `env: str = None` 查询参数 |
| `POST /workbench/indicators` | `IndicatorsRequest` body 增加 `env` 字段 |
| `POST /workbench/run` | `WorkbenchRunReq` body 增加 `env` 字段 |

### 4.4 Model

**文件**: `artemis/models/workbench.py`

```python
class WorkbenchRunReq(BaseModel):
    ...
    env: Optional[str] = None

class IndicatorsRequest(BaseModel):
    ...
    env: Optional[str] = None
```

## 5. 前端改动 (Cthulhu)

### 5.1 API Service

**文件**: `cthulhu/src/app/features/workbench/services/workbench-api.service.ts`

```typescript
// 新增
getEnvs(): Observable<{ envs: string[]; default: string }>

// 现有方法增加 env 参数
getMarketData(symbol, start, end, env?: string)
calculateIndicators(req: IndicatorsRequest)  // req.env
runBacktest(req: WorkbenchRunRequest)         // req.env
```

### 5.2 环境选择器 UI

**位置**: Market Data 和 Strategy Research 两个页面的 Search 折叠面板内

```
┌─ Search ──── ● Production ──────────────────────┐
│ [Env: ▾ Production]  Symbol [000001]             │
│ Start [2024-01-01]   End [2024-12-31]    [Load]  │
│ Indicator [▾ RSI]    period [14]         [+ Add]  │
└──────────────────────────────────────────────────┘
```

**行为**：
- 组件: `<nz-select>` 下拉框，选项来自 `GET /workbench/envs`
- 持久化: `localStorage.setItem('workbench-env', envName)`
- 初始化: `ngOnInit` 时从 localStorage 恢复，无值则用后端返回的 `default`
- 切换环境: 已加载数据时清除当前图表，提示用户重新 Load
- 视觉: prod 环境在 Search 标题旁显示红色标记 `● Production`

### 5.3 受影响文件

| 文件 | 改动 |
|---|---|
| `workbench-api.service.ts` | 新增 `getEnvs()`，现有方法增加 `env` 参数 |
| `workbench.model.ts` | Request 类型增加 `env` 字段 |
| `market-data.page.ts` | 增加环境选择器 UI + env 传参 |
| `research.page.ts` | 增加环境选择器 UI + env 传参 |

## 6. 文件变更清单

| # | 文件 | 层 | 改动 |
|---|---|---|---|
| 1 | `artemis/core/config_manager.py` | 后端 | 新增多环境加载方法 |
| 2 | `artemis/services/workbench/market_data.py` | 后端 | `get_market_bars` 增加 env |
| 3 | `artemis/services/workbench/backtest.py` | 后端 | `run_backtest` 增加 env |
| 4 | `artemis/api/http_gateway/workbench_routes.py` | 后端 | 新增 `/envs`，现有端点加 env |
| 5 | `artemis/models/workbench.py` | 后端 | Model 增加 env 字段 |
| 6 | `cthulhu/.../workbench-api.service.ts` | 前端 | 新增 `getEnvs`，方法加 env |
| 7 | `cthulhu/.../workbench.model.ts` | 前端 | 类型增加 env |
| 8 | `cthulhu/.../market-data.page.ts` | 前端 | 增加环境选择器 UI |
| 9 | `cthulhu/.../research.page.ts` | 前端 | 增加环境选择器 UI |

## 7. 边界情况处理

| 场景 | 处理方式 |
|---|---|
| 不传 `env` | 使用后端默认环境（当前启动配置） |
| 传入不存在的 `env` | 回退到默认环境 + 日志 warning |
| 某环境 PhoenixA 不可达 | 返回 HTTP 500 + 友好错误信息 |
| 前端 localStorage 无缓存 | 使用后端返回的 `default` |
| 环境切换时有已加载数据 | 清除图表，提示重新 Load |

## 8. 验证方案

### 8.1 后端验证

```bash
# 1. 查看可用环境
curl http://localhost:18000/workbench/envs
# 期望: {"envs": ["dev", "home", "prod"], "default": "dev"}

# 2. 使用 prod 环境获取数据
curl "http://localhost:18000/workbench/market-data?env=prod&symbol=000001&start_date=2024-01-01&end_date=2024-12-31"
# 期望: 返回完整历史数据

# 3. 不传 env（默认环境）
curl "http://localhost:18000/workbench/market-data?symbol=000001&start_date=2024-01-01&end_date=2024-12-31"
# 期望: 返回 dev 环境数据

# 4. 传入不存在的 env
curl "http://localhost:18000/workbench/market-data?env=staging&symbol=000001&..."
# 期望: 回退到默认环境，日志有 warning
```

### 8.2 前端验证

1. 打开 Workbench → Market Data，确认 Search 面板内出现环境选择器
2. 切换到 `prod`，点击 Load，确认数据量明显大于 dev
3. 刷新页面，确认环境选择保持（localStorage 持久化）
4. 切回 `dev`，Load 数据，确认正常
5. Strategy Research 页面同样验证
6. prod 环境时 Search 标题旁显示红色 `● Production` 标记
