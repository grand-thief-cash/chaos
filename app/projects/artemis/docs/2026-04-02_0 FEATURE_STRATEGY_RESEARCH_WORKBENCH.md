# FEATURE: Strategy Research Workbench（策略研发工作台）

> 日期：2026-04-02
> 状态：设计阶段
> 影响项目：Artemis（后端）、Cthulhu（前端）

---

## 0. 文档目标

本文档描述 Artemis 策略研发工作台（Strategy Research Workbench）的后端设计与实施计划。

工作台的核心定位是：一个**交互式、轻量级**的策略快速验证工具，让研发人员可以在页面上选择策略、选择数据、配置参数、运行回测、立即看到结果。

> **术语更新（2026-04-13）**：Workbench / Artemis 内部统一使用 `period` 表示周期；`timeframe`、`frequency` 等命名仅允许出现在外部 SDK / 外部 API 适配边界。

---

## 1. 背景与问题

### 1.1 现状

当前回测引擎（`strategy_engine`）被 `task_engine` 包裹调用：

```
HTTP API → TaskEngine → BacktraderCampaignTask → BacktraderRunTask → strategy_engine
```

`BacktraderRunTask` 走完整的任务生命周期（parameter_check → load_dynamic_parameters → before_execute → execute → post_process → sink → finalize），结果通过 `PhoenixAClient` 落库到 PhoenixA。

### 1.2 问题

这个设计对**交互式策略研发**来说过重：

| 维度 | 现有设计 | 策略研发需要的 |
|------|---------|--------------|
| 定位 | 后台任务执行 | 交互式研发工具 |
| 生命周期 | 重：8个阶段 | 轻：参数→运行→结果 |
| 结果 | 必须落库 | 直接返回 JSON（可不落库） |
| 调用方 | task_engine 调度 | HTTP API 直接调用 |
| 迭代速度 | 慢（注册/配置/执行） | 快（改参数/重跑） |

### 1.3 设计目标

1. 提供一组轻量 Workbench API，**直接调用 strategy_engine**，绕过 task_engine
2. 结果直接以 JSON 返回，MVP 阶段不需要落库
3. 每个策略的参数由 `param_schema` 描述，前端据此动态渲染表单
4. strategy_engine 保持独立可复用——未来定时任务 / 批量回测仍走 task_engine

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│  Cthulhu (Frontend)                                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Strategy Research Page                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │ │
│  │  │ 策略选择  │  │ 参数表单  │  │ 股票/时间/资金    │  │ │
│  │  └──────────┘  └──────────┘  └──────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────┐   │ │
│  │  │ 运行按钮                                      │   │ │
│  │  └──────────────────────────────────────────────┘   │ │
│  │  ┌─────────────────┐  ┌───────────────────────┐    │ │
│  │  │ ECharts 权益曲线  │  │ 统计卡片              │    │ │
│  │  └─────────────────┘  └───────────────────────┘    │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Artemis (Backend)                                       │
│                                                          │
│  ┌── Workbench API ──────────────────────────────────┐  │
│  │  GET  /workbench/strategies                        │  │
│  │  POST /workbench/run                               │  │
│  │                                                    │  │
│  │  直接调用 ──→ strategy_engine                      │  │
│  │                ├─ StrategyRegistry                 │  │
│  │                ├─ DataProviderRegistry             │  │
│  │                ├─ AnalyzerProfileRegistry          │  │
│  │                ├─ BacktraderEngineBuilder          │  │
│  │                └─ BacktestResultNormalizer         │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌── Task API (保持不变) ─────────────────────────────┐  │
│  │  POST /tasks/run/BACKTRADER_CAMPAIGN               │  │
│  │  → TaskEngine → BacktraderRunTask → strategy_engine│  │
│  │  → 落库到 PhoenixA                                 │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  PhoenixA    │
                   │  (行情数据)   │
                   └─────────────┘
```

### 2.2 关键设计决策

#### 决策 1：Workbench 不经过 task_engine

理由：
- task_engine 的 8 阶段生命周期、TaskContext、进度上报、回调机制是为**后台任务调度**设计的
- 策略研发需要的是**同步、即时**的反馈
- 两者使用场景完全不同，不应耦合

#### 决策 2：strategy_engine 保持独立

`strategy_engine` 已经是一个设计良好的独立模块（注册表模式 + 构建器模式）。Workbench 和 task_engine 都只是它的**调用方**。

```
strategy_engine (独立模块)
    ↑              ↑
    │              │
 Workbench API   Task API
 (交互式)        (定时/批量)
```

#### 决策 3：MVP 阶段不落库

交互式研发的结果直接以 JSON 返回给前端展示。如果用户想保存某次结果，未来可以添加"保存结果"按钮（那时再落库）。

#### 决策 4：analyzer_profile 硬编码

MVP 使用 `default_hist_v1`（Returns、DrawDown、TradeAnalyzer、SharpeRatio_A），不暴露给用户选择。未来需要时再开放。

---

## 3. API 设计

### 3.1 GET /workbench/strategies

返回所有可用策略及其参数 schema，供前端动态渲染参数表单。

**Response 200：**

```json
{
  "strategies": [
    {
      "code": "sma_cross",
      "default_params": {"fast": 10, "slow": 30, "stake": 1},
      "supported_modes": ["historical"],
      "supported_periods": ["daily"],
      "param_schema": {
        "fast": {"type": "int", "min": 1},
        "slow": {"type": "int", "min": 1},
        "stake": {"type": "int", "min": 1}
      }
    }
  ]
}
```

注意：不暴露 `cls`（backtrader Strategy 类），只暴露前端需要的元信息。

### 3.2 POST /workbench/run

同步执行一次单股票、单参数集的回测，返回完整结果。

**Request Body：**

```json
{
  "strategy_code": "sma_cross",
  "symbol": "sh600519",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "period": "daily",
  "adjust": "nf",
  "cash": 100000.0,
  "commission": 0.0,
  "strategy_params": {
    "fast": 10,
    "slow": 30
  }
}
```

**Response 200：**

```json
{
  "run_meta": {
    "run_id": "wb-20260402-001",
    "parent_run_id": null,
    "task_code": "workbench"
  },
  "summary": {
    "strategy_code": "sma_cross",
    "symbol": "sh600519",
    "period": "daily",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "start_cash": 100000.0,
    "end_value": 105230.0,
    "pnl": 5230.0,
    "pnl_pct": 0.0523,
    "max_drawdown": 3.21,
    "sharpe": 1.23,
    "bars_processed": 242,
    "trade_count": 8,
    "win_count": 5,
    "loss_count": 3,
    "win_rate": 0.625
  },
  "artifacts": {
    "equity_curve": [
      {"timestamp": "2024-01-02T00:00:00", "close": 1680.0, "cash": 100000.0, "value": 100000.0}
    ],
    "signals": [
      {"timestamp": "2024-02-15T00:00:00", "signal": "BUY", "close": 1720.0},
      {"timestamp": "2024-04-10T00:00:00", "signal": "SELL", "close": 1810.0}
    ],
    "trades": [
      {"timestamp": "2024-04-10T00:00:00", "size": 1, "price": 1720.0, "pnl": 90.0, "pnlcomm": 90.0, "barlen": 40}
    ],
    "orders": [
      {"timestamp": "2024-02-15T00:00:00", "status": "Completed", "order_type": "BUY", "size": 1, "price": 1720.0, "value": 1720.0, "commission": 0.0}
    ],
    "positions": [
      {"timestamp": "2024-01-02T00:00:00", "size": 0, "price": 0.0}
    ]
  }
}
```

**Error 400：** 参数校验失败

```json
{"detail": "strategy_code 'xxx' is not registered"}
{"detail": "no historical bars found for symbol=xxx"}
{"detail": "strategy_params.fast must be >= 1"}
```

**Error 500：** 内部错误

```json
{"detail": "internal error"}
```

---

## 4. 详细设计

### 4.1 Pydantic Models

**新文件：`artemis/models/workbench.py`**

```python
from typing import Any, Dict, List
from pydantic import BaseModel


class WorkbenchRunReq(BaseModel):
    """Workbench 回测运行请求。"""
    strategy_code: str
    symbol: str
    start_date: str
    end_date: str
    period: str = "daily"
    adjust: str = "nf"
    cash: float = 100000.0
    commission: float = 0.0
    strategy_params: Dict[str, Any] = {}
```

### 4.2 Workbench Service

**新文件：`artemis/engines/workbench/__init__.py`**

核心函数 `run_backtest(req: WorkbenchRunReq) -> dict` 的执行流程：

```
1. strategy_registry.require(req.strategy_code)
   → 获取 StrategySpec

2. spec.validate_params(req.strategy_params)
   → 校验策略参数

3. 从 cfg_mgr 构建 PhoenixAClient
   → 直接读 config，不依赖 TaskContext

4. phoenix_client.get_strategy_market_bars(
      symbol=req.symbol,
      start_date=req.start_date,
      end_date=req.end_date,
      period=req.period,
      adjust=req.adjust
   )
   → 拉取 K 线数据

5. BacktraderEngineBuilder.build(
      df=pd.DataFrame(bars),
      strategy_spec=spec,
      strategy_params={**spec.default_params, **req.strategy_params},
      analyzer_profile=analyzer_profile_registry.require("default_hist_v1"),
      cash=req.cash,
      commission=req.commission
   )
   → 构建 Cerebro 引擎

6. cerebro.run() → 执行回测

7. 提取 analyzer results
   → 复用 BacktraderRunTask._extract_analyzer_results 的逻辑

8. BacktestResultNormalizer.normalize(...)
   → 标准化结果

9. 返回 {run_meta, summary, artifacts}
```

辅助函数 `list_strategies() -> dict`：

```
遍历 strategy_registry._registry
对每个 StrategySpec，序列化为：
  {code, default_params, supported_modes, supported_periods, param_schema}
不暴露 cls 字段
```

### 4.3 API Routes

**新文件：`artemis/api/http_gateway/workbench_routes.py`**

```python
from fastapi import APIRouter, HTTPException
from artemis.models.workbench import WorkbenchRunReq
from artemis.engines.workbench import list_strategies, run_backtest

router = APIRouter(prefix="/workbench", tags=["workbench"])

@router.get("/strategies")
async def get_strategies():
    return list_strategies()

@router.post("/run")
async def run(req: WorkbenchRunReq):
    try:
        return run_backtest(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "workbench_run_failed", "error": str(e)})
        raise HTTPException(status_code=500, detail="internal error")
```

**修改：`artemis/api/http_gateway/routes.py`**

在文件末尾添加：

```python
from artemis.api.http_gateway.workbench_routes import router as workbench_router
app.include_router(workbench_router)
```

### 4.4 PhoenixAClient 构建方式

Workbench 不使用 TaskContext，需要直接构建 PhoenixAClient。参考 `TaskContext` 中的构建逻辑：

```python
from artemis.core import cfg_mgr
from artemis.core.clients.phoenixA_client import PhoenixAClient

config = cfg_mgr.get_config()
phoenix_cfg = config.get("dept_services", {}).get("phoenixA", {})
client = PhoenixAClient(
    host=phoenix_cfg.get("host", "localhost"),
    port=phoenix_cfg.get("port", 8000),
    logger=get_logger("workbench"),
    timeout_seconds=phoenix_cfg.get("timeout_seconds", 30),
)
```

### 4.5 Analyzer Results 提取

当前 `_extract_analyzer_results` 是 `BacktraderRunTask` 的静态方法（`backtest/run.py:24-36`）。

MVP 阶段在 workbench 中复制该逻辑（仅 10 行代码），避免 workbench 反向依赖 task_engine。未来可考虑移到 `strategy_engine/result_normalizer.py` 作为公共方法。

---

## 5. 不修改的模块

以下模块保持不变，Workbench 只是它们的新调用方：

| 模块 | 路径 | 说明 |
|------|------|------|
| strategy_engine | `engines/strategy_engine/` | 注册表 + 构建器 + 标准化器，原样复用 |
| task_engine | `engines/task_engine/` | 定时任务/批量回测仍走此路径 |
| PhoenixAClient | `core/clients/phoenixA_client.py` | 直接构建使用，不依赖 TaskContext |
| ConfigManager | `core/config_manager.py` | 直接读取配置 |

---

## 6. 新增策略的步骤

当需要添加新策略（如 RSI、MACD）时：

1. 在 `engines/strategy_engine/strategies/` 下创建策略文件（如 `rsi.py`）
2. 在 `strategies/registry_map.py` 中注册，填写 `param_schema`
3. Workbench API 自动发现（`GET /workbench/strategies` 遍历 registry）
4. 前端自动渲染对应的参数表单（根据 `param_schema` 动态生成）

**无需修改 Workbench API 或前端代码。**

---

## 7. 实施步骤

### Step 1: 创建 Pydantic Models

- [ ] 创建 `artemis/models/workbench.py` — `WorkbenchRunReq`
- [ ] 更新 `artemis/models/__init__.py` — 导出新 model

### Step 2: 创建 Workbench Service

- [ ] 创建 `artemis/engines/workbench/__init__.py` — `list_strategies()` + `run_backtest()`

### Step 3: 创建 API Routes

- [ ] 创建 `artemis/api/http_gateway/workbench_routes.py` — `GET /workbench/strategies` + `POST /workbench/run`
- [ ] 修改 `artemis/api/http_gateway/routes.py` — `app.include_router(workbench_router)`

### Step 4: 验证

- [ ] 启动 Artemis，`GET /workbench/strategies` 返回策略列表
- [ ] `POST /workbench/run` 用 sma_cross + sh600519 执行回测，返回完整结果
- [ ] 校验错误处理：未知策略码、无效参数、无数据

---

## 8. 未来扩展

| 扩展项 | 说明 |
|--------|------|
| 多股票回测 | 扩展 `POST /workbench/run` 支持 `symbols[]`，并行执行多股票 |
| 结果保存 | 添加 `POST /workbench/save` 将某次运行结果落库到 PhoenixA |
| 定时任务 | 现有 `task_engine` 的 BacktraderCampaignTask 继续服务此场景 |
| Analyzer 选择 | 扩展 API 接受 `analyzer_profile` 参数 |
| 参数优化 | 添加 `POST /workbench/optimize` 支持参数网格搜索 |
| 实时模拟 | 通过 task_engine 的 LONGRUN 模式支持 |

---

## 9. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `artemis/models/workbench.py` | **NEW** | Pydantic request model |
| `artemis/models/__init__.py` | **MODIFY** | 导出 workbench models |
| `artemis/engines/workbench/__init__.py` | **NEW** | Service: list_strategies + run_backtest |
| `artemis/api/http_gateway/workbench_routes.py` | **NEW** | FastAPI router: 2 endpoints |
| `artemis/api/http_gateway/routes.py` | **MODIFY** | 挂载 workbench router (1行) |
