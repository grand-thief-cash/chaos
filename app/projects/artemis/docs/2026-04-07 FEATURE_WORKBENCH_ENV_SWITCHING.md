# FEATURE: Workbench 多数据源切换

## 文档信息
- 日期: 2026-04-07
- 类型: Feature Proposal
- 模块: Artemis (backend) + Cthulhu (frontend)
- 状态: Draft

## 1. 背景与动机

当前 Workbench 的策略研究和市场数据功能依赖 PhoenixA 数据服务。

- **development 环境**（本地/家庭网络）：PhoenixA 数据量有限，无法充分验证策略效果
- **production 环境**：PhoenixA 拥有完整历史数据，适合策略开发和实验
- **当前切换成本**：需要重新编译前端（`ng build --configuration production`）+ 重启后端（`-e production`），中断工作流

> **注意**：环境类型只有 `development` 和 `production` 两种。不同的开发机器（relx / home）通过 `--config` 参数指定不同的配置文件路径区分，而非通过不同的 env 名称。

**目标**：在 Workbench 页面内实现 **运行时** 数据源切换，无需重新编译或重启，即可访问不同配置文件对应的 PhoenixA 数据源。

## 2. 现状分析

### 2.1 Artemis 后端

| 项 | 现状 |
|---|---|
| 配置加载 | `config_manager.py` 启动时加载 **一个** config 文件（基于 CLI `--env`） |
| 配置文件 | 已有 3 套：`config.yaml`(本地 development)、`config-home.yaml`(家庭 development)、`config-production.yaml`(production) |
| 数据源 | 每套配置的 `dept_services.phoenixA` 指向不同 PhoenixA 实例 |
| Workbench 服务 | `market_data.py`、`backtest.py` 通过 `_build_phoenix_client()` 连接当前环境 |

**各配置文件对应的 PhoenixA 端点**：

| 配置文件 | `--env` | PhoenixA 地址 |
|---|---|---|
| `config.yaml` | `development` | `127.0.0.1:18085` |
| `config-home.yaml` | `development` | `192.168.31.72:8085` |
| `config-production.yaml` | `production` | `192.168.31.142:8085` |

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
2. **Artemis 启动时加载所有环境配置** — 仅 `dept_services` 段（**production 环境部署时仅保留自身配置**）
3. **Workbench API 新增 `env` 参数** — 按需创建对应环境的 PhoenixA client
4. **前端增加环境选择器** — 下拉框 + localStorage 持久化
5. **production 只读保障** — 通过 production 环境获取的数据仅用于研究分析，禁止任何写操作流入 production 数据源
6. **生产环境隔离** — 当 Artemis 以 `--env=production` 启动时，多数据源切换功能完全禁用，`/workbench/sources` 仅返回当前数据源，不可访问其他数据源
7. **指定即严格** — 明确指定 `env` 后，必须使用该环境的 PhoenixA，不可达则直接报错，绝不静默回退到其他环境

### 3.2 数据流

**development 环境部署时（完整功能）：**

```
┌─────────────────────┐
│  Cthulhu (前端)       │
│  ┌───────────────┐  │
│  │ Source Selector│──┼── selectedSource = "production"
│  │  (localStorage)│  │
│  └───────────────┘  │
│         │            │
│         ▼            │
│  GET /workbench/market-data?source=production&symbol=000001&...
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Artemis (本地后端)   │
│  --env=development   │
│  --config=config.yaml│
│                      │
│  cfg_mgr             │
│  ├─ scanned_sources: │
│  │  ├─ "default"     → config.yaml         → { phoenixA: 127.0.0.1:18085 }
│  │  ├─ "home"        → config-home.yaml    → { phoenixA: 192.168.31.72:8085 }
│  │  └─ "production"  → config-production.yaml → { phoenixA: 192.168.31.142:8085 }
│  │                    │
│  └─ market_data_service.get_market_bars(source="production")  ← 只读操作
│         │              │
│         ▼              │
│  PhoenixA (production) ┼── 192.168.31.142:8085
│  返回完整历史数据       │
│  (仅读取，回测结果在本地展示)│
└──────────────────────┘
```

**production 环境部署时（功能禁用）：**

```
┌─────────────────────┐
│  Cthulhu (前端)       │
│  ┌───────────────┐  │
│  │ Source Selector│  │  ← 隐藏或仅显示 "production"
│  │  (disabled)    │  │
│  └───────────────┘  │
│         │            │
│         ▼            │
│  GET /workbench/market-data?symbol=000001&...  ← 无 source 参数
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Artemis (production 后端) │
│  --env=production    │
│  --config=config.yaml│
│                      │
│  cfg_mgr             │
│  ├─ scanned_sources: │
│  │  └─ "default"     → config.yaml → { phoenixA: 192.168.31.142:8085 }
│  │                    │  ← 仅当前配置，不扫描其他文件
│  └─ market_data_service.get_market_bars(source=None)
│         │              │
│         ▼              │
│  PhoenixA (production) ┼── 192.168.31.142:8085
│  正常返回数据           │
└──────────────────────┘
```

## 4. 后端改动 (Artemis)

### 4.1 ConfigManager 多环境支持

**文件**: `artemis/core/config_manager.py`

新增 3 个方法：

```python
def _scan_data_sources(self) -> Dict[str, DeptServicesConfig]:
    """扫描 config 目录下所有 config-*.yaml，提取各数据源的 dept_services。

    - config.yaml              → "default"（当前 --config 指向的文件）
    - config-home.yaml         → "home"
    - config-production.yaml   → "production"

    如果当前 --env=production，则跳过扫描，仅保留当前配置（"default"）。
    """

def get_dept_services_for_source(self, source_name: str | None) -> DeptServicesConfig:
    """返回指定数据源的 dept_services。

    - source_name 为 None 时使用当前启动配置（默认行为）
    - source_name 存在但不属于 available_sources 时，抛出 ValueError（禁止回退）
    - 当前 --env=production 时，source_name 只能为 None，否则抛出 ValueError
    """

def available_sources(self) -> list[str]:
    """返回所有可用数据源名列表。

    - development 环境: ['default', 'home', 'production']
    - production 环境: ['default']（仅当前配置）
    """
```

启动时自动扫描，结果缓存在内存中。production 环境下跳过扫描，仅保留当前配置。

### 4.2 Workbench 服务 source 参数

**文件**: `artemis/services/workbench/market_data.py`

```python
def get_market_bars(*, symbol, start_date, end_date,
                    timeframe="daily", adjust="nf", source=None):
    client = _build_phoenix_client(source=source)  # 传入 source
    # 注意: market_data 服务仅执行读取操作，不涉及写入
    ...
```

**文件**: `artemis/services/workbench/backtest.py`

```python
def run_backtest(req: WorkbenchRunReq, source=None):
    phoenix_client = _build_phoenix_client(source=source)
    # 注意: backtest 结果仅在本地计算和展示，不会回写到任何远程数据源
    ...
```

**共用 `_build_phoenix_client` 更新**（两个文件各自有，或提取到 `_client_factory.py`）：

```python
def _build_phoenix_client(source: str | None = None) -> PhoenixAClient:
    dept = cfg_mgr.get_dept_services_for_source(source)
    # get_dept_services_for_source 在以下情况会抛出 ValueError:
    #   1. source 不在 available_sources 中（数据源不存在或被 production 隔离）
    #   2. 当前运行在 production 环境（--env=production），但 source 不是 None
    # 绝不回退到其他数据源
    ...
```

### 4.3 API 路由

**文件**: `artemis/api/http_gateway/workbench_routes.py`

| 端点 | 改动 |
|---|---|
| `GET /workbench/sources` | **新增** — development 环境: `{ "sources": ["default","home","production"], "default": "default" }`；production 环境: `{ "sources": ["default"], "default": "default" }` |
| `GET /workbench/market-data` | 增加 `source: str = None` 查询参数；source 不合法时返回 HTTP 400 |
| `POST /workbench/indicators` | `IndicatorsRequest` body 增加 `source` 字段；source 不合法时返回 HTTP 400 |
| `POST /workbench/run` | `WorkbenchRunReq` body 增加 `source` 字段；source 不合法时返回 HTTP 400 |

### 4.4 Model

**文件**: `artemis/models/workbench.py`

```python
class WorkbenchRunReq(BaseModel):
    ...
    source: Optional[str] = None

class IndicatorsRequest(BaseModel):
    ...
    source: Optional[str] = None
```

## 5. 前端改动 (Cthulhu)

### 5.1 API Service

**文件**: `cthulhu/src/app/features/workbench/services/workbench-api.service.ts`

```typescript
// 新增
getSources(): Observable<{ sources: string[]; default: string }>

// 现有方法增加 source 参数
getMarketData(symbol, start, end, source?: string)
calculateIndicators(req: IndicatorsRequest)  // req.source
runBacktest(req: WorkbenchRunRequest)         // req.source
```

### 5.2 数据源选择器 UI

**位置**: Market Data 和 Strategy Research 两个页面的 Search 折叠面板内

```
┌─ Search ──── ● Production ──────────────────────────────────┐
│ [Source: ▾ Production]  Symbol [000001]                      │
│ Start [2024-01-01]   End [2024-12-31]    [Load]              │
│ Indicator [▾ RSI]    period [14]         [+ Add]             │
└──────────────────────────────────────────────────────────────┘
```

数据源选择器选项（由 `GET /workbench/sources` 返回）：
- `Default` → `default`（当前 config.yaml）
- `Home` → `home`（config-home.yaml）
- `Production` → `production`（config-production.yaml）

**行为**：
- 组件: `<nz-select>` 下拉框，选项来自 `GET /workbench/sources`
- 持久化: `localStorage.setItem('workbench-source', sourceName)`
- 初始化: `ngOnInit` 时从 localStorage 恢复，无值则用后端返回的 `default`
- 切换数据源: 已加载数据时清除当前图表，提示用户重新 Load
- 视觉: 选择 production 数据源时 Search 标题旁显示红色标记 `● Production`
- **production 隔离**: 当 `/workbench/sources` 仅返回 `["default"]` 时，隐藏数据源选择器

### 5.3 受影响文件

| 文件 | 改动 |
|---|---|
| `workbench-api.service.ts` | 新增 `getSources()`，现有方法增加 `source` 参数 |
| `workbench.model.ts` | Request 类型增加 `source` 字段 |
| `market-data.page.ts` | 增加数据源选择器 UI + source 传参 |
| `research.page.ts` | 增加数据源选择器 UI + source 传参 |

## 6. 文件变更清单

| # | 文件 | 层 | 改动 |
|---|---|---|---|
| 1 | `artemis/core/config_manager.py` | 后端 | 新增多数据源扫描方法 |
| 2 | `artemis/services/workbench/market_data.py` | 后端 | `get_market_bars` 增加 source |
| 3 | `artemis/services/workbench/backtest.py` | 后端 | `run_backtest` 增加 source |
| 4 | `artemis/api/http_gateway/workbench_routes.py` | 后端 | 新增 `/sources`，现有端点加 source |
| 5 | `artemis/models/workbench.py` | 后端 | Model 增加 source 字段 |
| 6 | `cthulhu/.../workbench-api.service.ts` | 前端 | 新增 `getSources`，方法加 source |
| 7 | `cthulhu/.../workbench.model.ts` | 前端 | 类型增加 source |
| 8 | `cthulhu/.../market-data.page.ts` | 前端 | 增加数据源选择器 UI |
| 9 | `cthulhu/.../research.page.ts` | 前端 | 增加数据源选择器 UI |

## 7. 边界情况处理

| 场景 | 处理方式 |
|---|---|
| 不传 `source` | 使用后端当前启动配置（默认行为） |
| 传入不存在的 `source` | 返回 HTTP 400 + 明确错误信息 `"Data source '{source}' is not available"`，**绝不回退** |
| 当前 `--env=production`，传入非空 `source` | 返回 HTTP 400 + `"Data source switching is disabled in production"`，**绝不回退** |
| 某数据源 PhoenixA 不可达 | 返回 HTTP 502 + 明确错误信息 `"Failed to connect to PhoenixA for source '{source}'"`，**绝不回退到其他数据源** |
| 前端 localStorage 无缓存 | 使用后端返回的 `default` |
| 数据源切换时有已加载数据 | 清除图表，提示重新 Load |
| 代码部署到 production 环境（`--env=production`） | `/workbench/sources` 仅返回 `["default"]`，前端数据源选择器自动隐藏 |
| 通过 production 数据源发起写操作 | Workbench 所有 API 均为只读设计（查询市场数据、计算指标、运行回测），回测结果仅在本地展示，不回写任何远程数据源 |

## 8. 验证方案

### 8.1 后端验证（development 环境）

```bash
# 1. 查看可用数据源
curl http://localhost:18000/workbench/sources
# 期望: {"sources": ["default", "home", "production"], "default": "default"}

# 2. 使用 production 数据源获取数据
curl "http://localhost:18000/workbench/market-data?source=production&symbol=000001&start_date=2024-01-01&end_date=2024-12-31"
# 期望: 返回完整历史数据（只读，无写操作）

# 3. 不传 source（默认数据源）
curl "http://localhost:18000/workbench/market-data?symbol=000001&start_date=2024-01-01&end_date=2024-12-31"
# 期望: 返回当前配置文件对应的数据

# 4. 传入不存在的 source（禁止回退验证）
curl "http://localhost:18000/workbench/market-data?source=staging&symbol=000001&..."
# 期望: HTTP 400，{"error": "Data source 'staging' is not available"}
# 绝不能回退到默认数据源

# 5. 某数据源 PhoenixA 不可达（禁止回退验证）
curl "http://localhost:18000/workbench/market-data?source=production&symbol=000001&..."
# （假设 production PhoenixA 宕机）
# 期望: HTTP 502，{"error": "Failed to connect to PhoenixA for source 'production'"}
# 绝不能回退到其他数据源
```

### 8.2 后端验证（production 环境）

```bash
# 1. 查看 production 环境下的可用数据源
curl http://localhost:18000/workbench/sources
# 期望: {"sources": ["default"], "default": "default"}
# 仅返回当前配置，不暴露其他数据源

# 2. 尝试访问 home 数据源（隔离验证）
curl "http://localhost:18000/workbench/market-data?source=home&symbol=000001&..."
# 期望: HTTP 400，{"error": "Data source switching is disabled in production"}

# 3. 不传 source（正常使用）
curl "http://localhost:18000/workbench/market-data?symbol=000001&..."
# 期望: 正常返回 production 数据，功能不受影响
```

### 8.3 前端验证

1. 打开 Workbench → Market Data，确认 Search 面板内出现数据源选择器
2. 切换到 `production`，点击 Load，确认数据量明显大于 default
3. 刷新页面，确认数据源选择保持（localStorage 持久化）
4. 切回 `default`，Load 数据，确认正常
5. Strategy Research 页面同样验证
6. 选择 production 数据源时 Search 标题旁显示红色 `● Production` 标记
7. **production 部署验证**: 以 `--env=production` 部署后，数据源选择器应隐藏，无其他选项
