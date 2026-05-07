# Cronjob + Artemis 任务配置手册

> 本文档是 Cronjob 调度服务与 Artemis 数据任务的完整配置参考。
> 涵盖所有可用任务、双向参数说明、配置示例和注意事项。
>
> 替代旧文档 `2026-03-18 CONIFG_OF_CRONJOB.md`。

---

## 目录

1. [架构概览](#1-架构概览)
2. [参数约定](#2-参数约定)
3. [Cronjob 侧通用配置](#3-cronjob-侧通用配置)
4. [任务目录](#4-任务目录)
5. [股票列表任务](#5-股票列表任务)
6. [历史行情任务](#6-历史行情任务)
7. [市场分类任务](#7-市场分类任务)
8. [申万行业任务](#8-申万行业任务)
9. [财务报表任务](#9-财务报表任务)
10. [公司行为任务](#10-公司行为任务)
11. [回测任务](#11-回测任务)
12. [内部任务（不可直接调度）](#12-内部任务不可直接调度)
13. [附录](#13-附录)

---

## 1. 架构概览

```
┌──────────┐    HTTP POST     ┌──────────┐
│  Cronjob  │ ──────────────→ │ Artemis  │
│  Service  │  /tasks/run/    │          │
│           │  {task_code}    │ TaskEngine│
│           │                 │   ↓      │
│           │  callback       │ TaskUnit │
│           │ ←────────────── │          │
└──────────┘                  └──────────┘
```

**请求结构**：Cronjob 向 Artemis 发送 HTTP POST，body 结构为：

```json
{
  "meta": {
    "run_id": 12345,
    "task_id": 67890,
    "exec_type": "SYNC",
    "task_code": "STOCK_ZH_A_LIST",
    "callback_endpoints": {
      "progress": "/api/v1/runs/12345/progress",
      "callback": "/api/v1/runs/12345/callback"
    }
  },
  "body": {
    // ← Cronjob 的 body_template 内容放在这里
  }
}
```

**任务生命周期**：`parameter_check` → `merge_parameters` → `load_dynamic_parameters` → `before_execute` → `execute` → `post_process` → `sink` → `finalize`

**参数合并优先级**：`task.yaml defaults` < `task.yaml variant config` < `incoming_params（cronjob body）` < `dynamic_params`

> **重要**：`parameter_check` 运行在 `merge_parameters` 之前，只看到 `incoming_params`（即 cronjob 传入的 body 内容）。因此 cronjob 传入的 body 必须包含代码中标记为 required 的所有参数，不能依赖 task.yaml 中的默认值。

---

## 2. 参数约定

| 约定 | 说明 |
|------|------|
| 日期格式 | 统一使用 `YYYY-MM-DD` 字符串，在 SDK 调用边界自动转为 int（如 `"2024-01-01"` → `20240101`） |
| 股票代码 | `symbols: ["000001"]` + `exchange: "SZ"` 分开传入，在 SDK 边界自动拼合为 `["000001.SZ"]` |
| 行业指数代码 | `symbols: ["851426.SI"]` 直接传入 SDK 格式（PhoenixA `index_code` 字段），不需要 `exchange` |
| 交易所 | `"SH"` / `"SZ"` / `"BJ"` / `"ALL"`（仅用于股票任务和 HIST 的 exchange 筛选） |
| 复权方式 | `"nf"`（不复权）/ `"qfq"`（前复权）/ `"hfq"`（后复权） |
| 周期 | `"daily"` / `"weekly"` / `"monthly"` / `"5min"` / `"15min"` / `"30min"` / `"60min"` |
| 日期语义 | 财务报表：`start_date/end_date` → SDK `begin_date/end_date`（报告期）；公司行为：→ 公告日期 |

### task.yaml `config` 字段说明

task.yaml 中的 `config` 字段**支持与 Artemis 参数相同的所有参数**。Cronjob body 和 task.yaml config 通过合并机制叠加：

```
最终参数 = task.yaml config（基础） + Cronjob body（覆盖）
```

因此，task.yaml 中的每个任务，其 `config` 可以写的字段就是对应"Artemis 参数"表中列出的全部字段。`start_date: null` 表示"不限定日期"（即全量下载），而非"不支持此参数"。

---

## 3. Cronjob 侧通用配置

每个任务在 Cronjob 中的配置结构如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | Y | 任务名称，唯一标识 |
| `description` | string | N | 任务描述 |
| `cron_expr` | string | Y | 6 位 cron 表达式（秒 分 时 日 月 周） |
| `exec_type` | string | Y | `SYNC`（同步等待结果）/ `ASYNC`（异步回调） |
| `http_method` | string | Y | HTTP 方法，通常为 `POST` |
| `target_service` | string | Y | 下游服务标识，通常为 `artemis` |
| `target_path` | string | Y | API 路径，格式 `/tasks/run/{TASK_CODE}` |
| `headers_json` | string | N | 额外 HTTP headers（JSON） |
| `body_template` | string | N | 请求体模板（JSON），即传给 Artemis 的业务参数 |
| `max_concurrency` | int | N | 单任务最大并发执行数，默认 1 |
| `concurrency_policy` | string | N | `QUEUE` / `SKIP` / `PARALLEL` |
| `overlap_action` | string | N | `SKIP` / `CANCEL_PREV` / `PARALLEL` / `ALLOW` |
| `failure_action` | string | N | `RUN_NEW` / `SKIP` / `RETRY` |

---

## 4. 任务目录

| Task Code | 类型 | 数据源 | 是否可 Cronjob 直接调度 | 简述 |
|-----------|------|--------|------------------------|------|
| `STOCK_ZH_A_LIST` | WorkerUnit | AmazingData | Y | A股股票列表 |
| `STOCK_ZH_A_HIST_PARENT` | OrchestratorUnit | Baostock | Y | A股历史行情（编排器） |
| `STOCK_ZH_A_HIST_CHILD` | WorkerUnit | Baostock | **N**（内部） | A股历史行情（单股执行） |
| `STOCK_ZH_A_MKT_CATEGORY_MAIRUI` | WorkerUnit | Mairui | Y | 市场分类（Mairui） |
| `STOCK_ZH_A_MKT_CATEGORY_SWHY` | WorkerUnit | AmazingData | Y | 申万行业分类 |
| `STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY` | WorkerUnit | AmazingData | Y | 申万行业成分股 |
| `STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY` | OrchestratorUnit | AmazingData | Y | 申万行业权重（编排器，按指数拆分） |
| `STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD` | WorkerUnit | AmazingData | **N**（内部） | 申万行业权重（单指数执行） |
| `STOCK_ZH_A_INDUSTRY_DAILY_SWHY` | OrchestratorUnit | AmazingData | Y | 申万行业日线（编排器，按指数拆分） |
| `STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD` | WorkerUnit | AmazingData | **N**（内部） | 申万行业日线（单指数执行） |
| `STOCK_ZH_A_BALANCE_SHEET` | WorkerUnit | AmazingData | Y | 资产负债表 |
| `STOCK_ZH_A_CASH_FLOW` | WorkerUnit | AmazingData | Y | 现金流量表 |
| `STOCK_ZH_A_INCOME` | WorkerUnit | AmazingData | Y | 利润表 |
| `STOCK_ZH_A_PROFIT_EXPRESS` | WorkerUnit | AmazingData | Y | 业绩快报 |
| `STOCK_ZH_A_PROFIT_NOTICE` | WorkerUnit | AmazingData | Y | 业绩预告 |
| `STOCK_ZH_A_DIVIDEND` | WorkerUnit | AmazingData | Y | 分红数据 |
| `STOCK_ZH_A_RIGHT_ISSUE` | WorkerUnit | AmazingData | Y | 配股数据 |
| `BACKTRADER_CAMPAIGN` | OrchestratorUnit | PhoenixA | Y | 回测战役（编排器） |
| `BACKTRADER_RUN` | WorkerUnit | PhoenixA | **N**（内部） | 单次回测执行 |

---

## 5. 股票列表任务

### STOCK_ZH_A_LIST

获取 A 股股票列表（上交所/深交所/北交所），写入 PhoenixA `security_registry`。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `exchange` | string | Y | - | 交易所：`SH` / `SZ` / `BJ` / `ALL` |

**task.yaml 变体**：

| match | config |
|-------|--------|
| `{ exchange: "SH" }` | `exchange: "SH"` |
| `{ exchange: "SZ" }` | `exchange: "SZ"` |
| `{ exchange: "BJ" }` | `exchange: "BJ"` |
| `{ exchange: "ALL" }` | `exchange: "ALL"` |

**Cronjob 配置示例**（上交所）：

```json
{
  "name": "stock_zh_a_list_sh",
  "cron_expr": "0 0 18 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_LIST",
  "body_template": "{\"exchange\": \"SH\"}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

---

## 6. 历史行情任务

### STOCK_ZH_A_HIST_PARENT

A股历史行情数据编排任务。根据交易所筛选股票列表，为每只股票生成 `STOCK_ZH_A_HIST_CHILD` 子任务。
自动从 PhoenixA 获取上次更新日期，做增量下载。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `period` | string | Y | - | K线周期：`daily` / `weekly` / `monthly` / `5min` / `15min` / `30min` / `60min` |
| `adjust` | string | Y | - | 复权方式：`nf`（不复权）/ `qfq`（前复权）/ `hfq`（后复权） |
| `exchange` | string | N* | `"SH,SZ,BJ"` | 交易所筛选，逗号分隔。不传则使用 variant 默认值 |
| `start_date` | string | N* | `"2016-01-01"` | 基准起始日期，格式 `YYYY-MM-DD`。不传则使用 variant 默认值 |
| `end_date` | string | N | 当天 | 截止日期 |
| `fields` | string | N* | 见下方 | baostock 查询字段列表，逗号分隔。不传则使用 variant 默认值 |
| `symbol_list` | string | N | - | 指定股票代码，逗号分隔（如 `"000001,600519"`）。不传则按 exchange 从 PhoenixA 获取全量 |

> *注：`exchange`、`start_date`、`fields` 在 `before_execute` 阶段检查（merge 后），若 variant 中有提供则可不传。但 `period` 和 `adjust` 必须在 body 中传入（parameter_check 阶段检查 incoming_params）。

**task.yaml 变体**：

```yaml
STOCK_ZH_A_HIST_PARENT:
  variants:
    - match: { period: "daily", adjust: "nf" }
      config:
        period: "daily"
        adjust: "nf"
        exchange: "SH,SZ,BJ"
        start_date: "2016-01-01"
        fields: "date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM"
        # end_date: null      # "YYYY-MM-DD" 或不设（默认当天）
        # symbol_list: null   # string，逗号分隔，如 "000001,600519"
    - match: { period: "daily", adjust: "hfq" }
      config:
        period: "daily"
        adjust: "hfq"
        exchange: "SH,SZ"
        start_date: "2009-01-01"
        fields: "date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM"
```

**Cronjob 配置示例**（日线不复权全量）：

```json
{
  "name": "stock_zh_a_hist_daily_nf",
  "cron_expr": "0 0 19 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_HIST_PARENT",
  "body_template": "{\"period\": \"daily\", \"adjust\": \"nf\"}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

**Cronjob 配置示例**（指定股票增量下载）：

```json
{
  "body_template": "{\"period\": \"daily\", \"adjust\": \"nf\", \"symbol_list\": \"000001,600519\", \"start_date\": \"2026-01-01\"}"
}
```

---

## 7. 市场分类任务

### STOCK_ZH_A_MKT_CATEGORY_MAIRUI

从 Mairui API 获取市场分类数据。无需任何参数。

**Artemis 参数**：无

**task.yaml 变体**：无（task.yaml 中未定义此任务，但已注册可执行）

**Cronjob 配置示例**：

```json
{
  "name": "stock_zh_a_mkt_category_mairui",
  "cron_expr": "0 0 10 * * 1",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_MKT_CATEGORY_MAIRUI",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

### STOCK_ZH_A_MKT_CATEGORY_SWHY

从 AmazingData 获取申万行业基础分类数据（行业代码、名称、层级关系）。无需任何参数。

**Artemis 参数**：无

**task.yaml 变体**：无（task.yaml 中未定义此任务，但已注册可执行）

**Cronjob 配置示例**：

```json
{
  "name": "stock_zh_a_mkt_category_swhy",
  "cron_expr": "0 0 10 * * 1",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_MKT_CATEGORY_SWHY",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

---

## 8. 申万行业任务

以下三个任务均使用 AmazingData SDK。

> **注意**：行业任务的 `symbols` 参数与股票任务不同。行业指数代码已经是 SDK 格式（如 `"851426.SI"`），直接传入即可，**不需要** `exchange` 参数。PhoenixA 中存储的 `index_code` 字段就是此格式。

### STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY

申万行业指数成分股数据。此任务**不支持**日期范围参数（SDK 限制）。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | N | 全量 | 行业指数代码列表（SDK 格式如 `["851426.SI"]`）。不传则从 PhoenixA 获取全部 |

**task.yaml 变体**：

```yaml
STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY:
  variants:
    - match: {}
      config: {}
      # 可配置字段: symbols（SDK格式，如 ["851426.SI"]）
      # 示例 — 只拉取指定行业:
      #   config:
      #     symbols: ["851426.SI", "801010.SI"]
```

**Cronjob 配置示例**（全量下载）：

```json
{
  "name": "swhy_industry_constituent",
  "cron_expr": "0 0 12 * * 6",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

### STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY

申万行业指数成分股权重数据。OrchestratorUnit — 按指数拆分为 `STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD` 子任务执行。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | N | 全量 | 行业指数代码列表（SDK 格式如 `["851426.SI"]`）。不传则从 PhoenixA 获取全部 |
| `start_date` | string | N | null（不限） | 交易日期起始，`YYYY-MM-DD` 格式。SDK 映射为 `begin_date`（int） |
| `end_date` | string | N | null（不限） | 交易日期截止，`YYYY-MM-DD` 格式。SDK 映射为 `end_date`（int） |

> `null` 表示不限定日期范围，SDK 将返回全部历史数据。

**task.yaml 变体**：

```yaml
STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY:
  variants:
    - match: {}
      config:
        start_date: null   # "YYYY-MM-DD" 或 null（不限）
        end_date: null     # "YYYY-MM-DD" 或 null（不限）
        # symbols: null    # string[]，行业指数代码（SDK格式），如 ["851426.SI"]
      # 示例 — 默认拉取最近一年:
      #   config:
      #     start_date: "2025-06-01"
      #     end_date: null
```

**Cronjob 配置示例**（指定日期范围）：

```json
{
  "name": "swhy_industry_weight",
  "cron_expr": "0 0 14 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY",
  "body_template": "{\"start_date\": \"2026-01-01\", \"end_date\": \"2026-05-07\"}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

**Cronjob 配置示例**（指定指数）：

```json
{
  "body_template": "{\"symbols\": [\"851426.SI\"], \"start_date\": \"2026-01-01\"}"
}
```

### STOCK_ZH_A_INDUSTRY_DAILY_SWHY

申万行业指数日行情数据（OHLCV、PE、PB、市值等）。OrchestratorUnit — 按指数拆分为 `STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD` 子任务执行。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | N | 全量 | 行业指数代码列表（SDK 格式如 `["851426.SI"]`）。不传则从 PhoenixA 获取全部 |
| `start_date` | string | N | null（不限） | 交易日期起始，`YYYY-MM-DD` 格式。SDK 映射为 `begin_date`（int） |
| `end_date` | string | N | null（不限） | 交易日期截止，`YYYY-MM-DD` 格式。SDK 映射为 `end_date`（int） |

> `null` 表示不限定日期范围，SDK 将返回全部历史数据。

**task.yaml 变体**：

```yaml
STOCK_ZH_A_INDUSTRY_DAILY_SWHY:
  variants:
    - match: {}
      config:
        start_date: null   # "YYYY-MM-DD" 或 null（不限）
        end_date: null     # "YYYY-MM-DD" 或 null（不限）
        # symbols: null    # string[]，行业指数代码（SDK格式），如 ["851426.SI"]
```

**Cronjob 配置示例**（全量下载）：

```json
{
  "name": "swhy_industry_daily",
  "cron_expr": "0 0 16 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_INDUSTRY_DAILY_SWHY",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

---

## 9. 财务报表任务

以下五个任务继承自 `BaseFinancialStatementTask`，结构和参数完全一致，仅 SDK 调用方法不同。

### 公共参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | N | 全量 | 纯股票代码列表（如 `["000001","600519"]`）。不传则从 SDK `get_hist_code_list` 获取全部 A 股历史代码 |
| `exchange` | string | 条件必填 | - | 当指定 `symbols` 时必填（如 `"SZ"` 或 `"SH"`），拼合为 SDK 格式 `"000001.SZ"` |
| `start_date` | string | N | null（不限） | 报告期起始日期，`YYYY-MM-DD` 格式。SDK 映射为 `begin_date`（int），筛选报告期在此之后的记录 |
| `end_date` | string | N | null（不限） | 报告期截止日期，`YYYY-MM-DD` 格式。SDK 映射为 `end_date`（int），筛选报告期在此之前的记录 |

> - 不传 `symbols` → 全量下载（SDK `get_hist_code_list` 获取 2013 年至今全部 A 股代码）
> - 传入 `symbols` + `exchange` → 增量下载指定股票
> - `null` 表示不限定报告期范围，SDK 将返回全部历史数据

### 公共 task.yaml 变体

所有 5 个财务报表任务使用相同的 task.yaml 结构：

```yaml
STOCK_ZH_A_BALANCE_SHEET:   # 或 CASH_FLOW / INCOME / PROFIT_EXPRESS / PROFIT_NOTICE
  variants:
    - match: {}
      config:
        start_date: null     # "YYYY-MM-DD" 或 null（不限报告期）
        end_date: null       # "YYYY-MM-DD" 或 null（不限报告期）
        # symbols: null      # string[]，股票代码列表，不设则全量
        # exchange: null     # string，指定 symbols 时必填
      # 示例 — 只拉取 2024 年以来的资产负债表:
      #   config:
      #     start_date: "2024-01-01"
      #     end_date: null
      # 示例 — 只拉取指定股票:
      #   config:
      #     symbols: ["000001", "600519"]
      #     exchange: "SZ"
```

### STOCK_ZH_A_BALANCE_SHEET（资产负债表）

**Cronjob 配置示例**（全量下载）：

```json
{
  "name": "balance_sheet_full",
  "cron_expr": "0 0 20 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_BALANCE_SHEET",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

**Cronjob 配置示例**（增量下载）：

```json
{
  "body_template": "{\"symbols\": [\"000001\", \"600519\"], \"exchange\": \"SZ\", \"start_date\": \"2025-01-01\"}"
}
```

### STOCK_ZH_A_CASH_FLOW（现金流量表）

参数和配置同 `STOCK_ZH_A_BALANCE_SHEET`，仅 `target_path` 不同。

- `target_path`: `/tasks/run/STOCK_ZH_A_CASH_FLOW`

### STOCK_ZH_A_INCOME（利润表）

参数和配置同 `STOCK_ZH_A_BALANCE_SHEET`，仅 `target_path` 不同。

- `target_path`: `/tasks/run/STOCK_ZH_A_INCOME`

### STOCK_ZH_A_PROFIT_EXPRESS（业绩快报）

参数和配置同 `STOCK_ZH_A_BALANCE_SHEET`，仅 `target_path` 不同。

- `target_path`: `/tasks/run/STOCK_ZH_A_PROFIT_EXPRESS`

### STOCK_ZH_A_PROFIT_NOTICE（业绩预告）

参数和配置同 `STOCK_ZH_A_BALANCE_SHEET`，仅 `target_path` 不同。

- `target_path`: `/tasks/run/STOCK_ZH_A_PROFIT_NOTICE`

---

## 10. 公司行为任务

以下两个任务继承自 `BaseCorporateActionTask`，结构一致。

### 公共参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | N | 全量 | 纯股票代码列表（如 `["000001","600519"]`）。不传则从 SDK `get_hist_code_list` 获取全部 A 股历史代码 |
| `exchange` | string | 条件必填 | - | 当指定 `symbols` 时必填（如 `"SZ"` 或 `"SH"`），拼合为 SDK 格式 `"000001.SZ"` |
| `start_date` | string | N | null（不限） | 公告日期起始，`YYYY-MM-DD` 格式。SDK 映射为 `begin_date`（int），筛选公告日期在此之后的记录 |
| `end_date` | string | N | null（不限） | 公告日期截止，`YYYY-MM-DD` 格式。SDK 映射为 `end_date`（int），筛选公告日期在此之前的记录 |

> - `null` 表示不限定公告日期范围，SDK 将返回全部历史数据

### 公共 task.yaml 变体

两个公司行为任务使用相同的 task.yaml 结构：

```yaml
STOCK_ZH_A_DIVIDEND:   # 或 RIGHT_ISSUE
  variants:
    - match: {}
      config:
        start_date: null     # "YYYY-MM-DD" 或 null（不限公告日期）
        end_date: null       # "YYYY-MM-DD" 或 null（不限公告日期）
        # symbols: null      # string[]，股票代码列表，不设则全量
        # exchange: null     # string，指定 symbols 时必填
      # 示例 — 只拉取 2025 年以来的分红数据:
      #   config:
      #     start_date: "2025-01-01"
      #     end_date: null
```

### STOCK_ZH_A_DIVIDEND（分红数据）

**task.yaml 变体**：

```yaml
STOCK_ZH_A_DIVIDEND:
  variants:
    - match: {}
      config:
        start_date: null     # "YYYY-MM-DD" 或 null（公告日期）
        end_date: null       # "YYYY-MM-DD" 或 null（公告日期）
        # symbols: null      # string[]，股票代码列表
        # exchange: null     # string，指定 symbols 时必填
```

**Cronjob 配置示例**：

```json
{
  "name": "dividend_full",
  "cron_expr": "0 0 21 * * 1-5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/STOCK_ZH_A_DIVIDEND",
  "body_template": "{}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

### STOCK_ZH_A_RIGHT_ISSUE（配股数据）

参数和配置同 `STOCK_ZH_A_DIVIDEND`，仅 `target_path` 不同。

- `target_path`: `/tasks/run/STOCK_ZH_A_RIGHT_ISSUE`

---

## 11. 回测任务

### BACKTRADER_CAMPAIGN

回测战役编排任务。将 N 只股票 × M 组策略参数拆分为 `BACKTRADER_RUN` 子任务并行执行。

**Artemis 参数**（传入 body / task.yaml config）：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mode` | string | Y | - | 回测模式，Phase 1 仅支持 `historical` |
| `strategy_code` | string | Y | - | 已注册的策略代码（如 `sma_cross`） |
| `data_provider_code` | string | Y | - | 数据源标识（如 `phoenixa_hist_daily`） |
| `analyzer_profile` | string | Y | - | 分析器配置（如 `default_hist_v1`） |
| `period` | string | Y | - | K线周期（`daily` / `weekly` / `monthly`） |
| `start_date` | string | Y | - | 回测起始日期，`YYYY-MM-DD` |
| `end_date` | string | Y | - | 回测结束日期，`YYYY-MM-DD` |
| `symbols` | string[] | F* | - | 股票代码列表（如 `["000001","600000"]`），与 `universe_code` 二选一 |
| `universe_code` | string | F* | - | 股票池代码（如 `ALL`），与 `symbols` 二选一 |
| `market` | string | N | `"CN_A"` | 市场标识 |
| `adjust` | string | N | `"nf"` | 复权方式：`nf` / `qfq` / `hfq` |
| `cash` | float | N | `100000.0` | 初始资金 |
| `commission` | float | N | `0.001` | 手续费率 |
| `strategy_params` | object | N | `{}` | 策略参数，覆盖策略默认参数（如 `{"fast": 3, "slow": 8}`） |
| `parameter_grid` | object[] | N | - | 参数网格，用于批量回测（如 `[{"fast": 5, "slow": 20}, {"fast": 10, "slow": 30}]`） |
| `persist_artifacts` | string[] | N | 见下方 | 需要持久化的制品类型 |

> `symbols` 和 `universe_code` 至少传一个。最多 50 只股票，最多 200 个子任务（symbols × parameter_grid）。

**persist_artifacts 可选值**：

| 值 | 说明 |
|----|------|
| `analyzers` | 分析结果（收益率、夏普比率、最大回撤等） |
| `trades` | 交易记录明细（买卖信号、订单状态、成交价格、盈亏） |
| `equity_curve` | 逐 bar 权益曲线 |
| `plot_manifest` | 绘图元数据清单 |
| `plot_series` | 绘图时序数据 |

**task.yaml 变体**：

```yaml
BACKTRADER_CAMPAIGN:
  variants:
    - match: { mode: "historical" }
      config:
        mode: "historical"
        market: "CN_A"
        period: "daily"
        adjust: "nf"
        cash: 100000.0
        commission: 0.001
        data_provider_code: "phoenixa_hist_daily"
        analyzer_profile: "default_hist_v1"
        persist_artifacts: ["analyzers", "trades", "equity_curve", "plot_manifest", "plot_series"]
        # 以下参数由 Cronjob body 传入，不在 task.yaml config 中设默认值:
        #   strategy_code:    string   (必填) — 如 "sma_cross"
        #   start_date:       string   (必填) — "YYYY-MM-DD"
        #   end_date:         string   (必填) — "YYYY-MM-DD"
        #   symbols:          string[] — 如 ["000001"]
        #   universe_code:    string   — 如 "ALL"
        #   strategy_params:  object   — 如 {"fast": 5, "slow": 20}
        #   parameter_grid:   object[] — 如 [{"fast": 5, "slow": 20}]
```

**Cronjob 配置示例**（单股票 SMA 金叉回测）：

```json
{
  "name": "backtest_sma_cross_000001",
  "cron_expr": "0 0 22 * * 5",
  "exec_type": "SYNC",
  "http_method": "POST",
  "target_service": "artemis",
  "target_path": "/tasks/run/BACKTRADER_CAMPAIGN",
  "body_template": "{\"mode\": \"historical\", \"strategy_code\": \"sma_cross\", \"data_provider_code\": \"phoenixa_hist_daily\", \"analyzer_profile\": \"default_hist_v1\", \"period\": \"daily\", \"adjust\": \"nf\", \"cash\": 100000.0, \"commission\": 0.001, \"symbols\": [\"000001\"], \"start_date\": \"2020-01-01\", \"end_date\": \"2026-04-01\", \"persist_artifacts\": [\"analyzers\", \"trades\", \"equity_curve\", \"plot_manifest\", \"plot_series\"]}",
  "max_concurrency": 1,
  "concurrency_policy": "SKIP",
  "overlap_action": "SKIP",
  "failure_action": "RUN_NEW"
}
```

**Cronjob 配置示例**（全市场参数网格回测）：

```json
{
  "body_template": "{\"mode\": \"historical\", \"strategy_code\": \"sma_cross\", \"data_provider_code\": \"phoenixa_hist_daily\", \"analyzer_profile\": \"default_hist_v1\", \"period\": \"daily\", \"adjust\": \"nf\", \"cash\": 100000.0, \"commission\": 0.001, \"universe_code\": \"ALL\", \"start_date\": \"2020-01-01\", \"end_date\": \"2026-04-01\", \"parameter_grid\": [{\"fast\": 5, \"slow\": 20}, {\"fast\": 10, \"slow\": 30}, {\"fast\": 20, \"slow\": 60}], \"persist_artifacts\": [\"analyzers\", \"trades\"]}"
}
```

---

## 12. 内部任务（不可直接调度）

以下任务由编排器（OrchestratorUnit）自动创建，不应通过 Cronjob 直接调度：

### STOCK_ZH_A_HIST_CHILD

由 `STOCK_ZH_A_HIST_PARENT` 的 `plan()` 方法自动生成，每只股票一个子任务。

内部参数：`bs_code`, `symbol`, `start_date`, `end_date`, `period`, `adjust`, `bs_period`, `bs_adjust`, `fields`

### BACKTRADER_RUN

由 `BACKTRADER_CAMPAIGN` 的 `plan()` 方法自动生成，每只股票 × 每组参数一个子任务。

内部参数：`mode`, `market`, `period`, `adjust`, `strategy_code`, `data_provider_code`, `analyzer_profile`, `cash`, `commission`, `persist_artifacts`, `symbol`, `start_date`, `end_date`, `strategy_params`

### STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD

由 `STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY` 的 `plan()` 方法自动生成，每个行业指数一个子任务。

内部参数：`index_code`, `start_date`, `end_date`

### STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD

由 `STOCK_ZH_A_INDUSTRY_DAILY_SWHY` 的 `plan()` 方法自动生成，每个行业指数一个子任务。

内部参数：`index_code`, `start_date`, `end_date`

---

## 13. 附录

### A. task.yaml 完整内容（含参数注释）

> 以下列出 task.yaml 中每个任务的 `config` 字段可配置的全部参数、类型、格式和示例。
> `config` 中的参数与 Cronjob body 传入的参数完全相同，通过合并机制叠加。

```yaml
tasks:
  # ────────────────────────────────────────────────────────────
  # STOCK_ZH_A_LIST — A股股票列表
  # ────────────────────────────────────────────────────────────
  # config 可配置参数:
  #   exchange: string (必填) — "SH" / "SZ" / "BJ" / "ALL"
  #
  STOCK_ZH_A_LIST:
    variants:
      - match: { exchange: "SH" }
        config: { exchange: "SH" }
      - match: { exchange: "SZ" }
        config: { exchange: "SZ" }
      - match: { exchange: "BJ" }
        config: { exchange: "BJ" }
      - match: { exchange: "ALL" }
        config: { exchange: "ALL" }

  # ────────────────────────────────────────────────────────────
  # STOCK_ZH_A_HIST_PARENT — A股历史行情（编排器）
  # ────────────────────────────────────────────────────────────
  # config 可配置参数:
  #   period:      string (必填) — K线周期 "daily" / "weekly" / "monthly" / "5min" / "15min" / "30min" / "60min"
  #   adjust:      string (必填) — 复权方式 "nf" / "qfq" / "hfq"
  #   exchange:    string        — 交易所筛选，逗号分隔，如 "SH,SZ,BJ"
  #   start_date:  string        — 基准起始日期 "YYYY-MM-DD"，如 "2016-01-01"
  #   end_date:    string        — 截止日期 "YYYY-MM-DD"，不传默认当天
  #   fields:      string        — baostock 查询字段，逗号分隔
  #   symbol_list: string        — 指定股票代码，逗号分隔（如 "000001,600519"），不传则按 exchange 从 PhoenixA 获取全量
  #
  STOCK_ZH_A_HIST_PARENT:
    variants:
      - match: { period: "daily", adjust: "nf" }
        config:
          period: "daily"
          adjust: "nf"
          exchange: "SH,SZ,BJ"
          start_date: "2016-01-01"
          fields: "date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM"
      - match: { period: "daily", adjust: "hfq" }
        config:
          period: "daily"
          adjust: "hfq"
          exchange: "SH,SZ"
          start_date: "2009-01-01"
          fields: "date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM"

  # ────────────────────────────────────────────────────────────
  # 申万行业任务（3 个） — 均使用 AmazingData SDK
  # ────────────────────────────────────────────────────────────
  # 注意：行业任务的 symbols 是 SDK 格式的 index_code（如 "851426.SI"），
  #       不需要 exchange 参数（与股票任务不同）
  #
  # config 可配置参数（WEIGHT / DAILY 通用）:
  #   symbols:    string[] — 行业指数代码（SDK格式如 ["851426.SI"]），不设则从 PhoenixA 获取全部
  #   start_date: string   — 交易日期起始 "YYYY-MM-DD"，null 表示不限
  #   end_date:   string   — 交易日期截止 "YYYY-MM-DD"，null 表示不限
  #
  # CONSTITUENT 不支持日期参数（SDK 限制），只支持 symbols
  #
  STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY:
    variants:
      - match: {}
        config:
          start_date: null     # "YYYY-MM-DD" 或 null
          end_date: null       # "YYYY-MM-DD" 或 null
          # symbols: null      # string[]，如 ["851426.SI", "801010.SI"]

  STOCK_ZH_A_INDUSTRY_WEIGHT_SWHY_CHILD:
    variants:
      - match: {}
        config: {}

  STOCK_ZH_A_INDUSTRY_DAILY_SWHY:
    variants:
      - match: {}
        config:
          start_date: null     # "YYYY-MM-DD" 或 null
          end_date: null       # "YYYY-MM-DD" 或 null
          # symbols: null      # string[]，如 ["851426.SI"]

  STOCK_ZH_A_INDUSTRY_DAILY_SWHY_CHILD:
    variants:
      - match: {}
        config: {}

  STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY:
    variants:
      - match: {}
        config: {}
        # symbols: null        # string[]，如 ["851426.SI"]
        # 注意：此任务不支持 start_date / end_date（SDK 限制）

  # ────────────────────────────────────────────────────────────
  # 财务报表任务（5 个） — 均使用 AmazingData SDK
  # ────────────────────────────────────────────────────────────
  # config 可配置参数（全部通用）:
  #   symbols:    string[] — 纯股票代码列表（如 ["000001", "600519"]），不设则全量下载
  #   exchange:   string   — 指定 symbols 时必填（如 "SZ" 或 "SH"），拼合为 SDK 格式 "000001.SZ"
  #   start_date: string   — 报告期起始 "YYYY-MM-DD"，null 表示不限，SDK 映射为 begin_date (int)
  #   end_date:   string   — 报告期截止 "YYYY-MM-DD"，null 表示不限，SDK 映射为 end_date (int)
  #
  STOCK_ZH_A_BALANCE_SHEET:
    variants:
      - match: {}
        config:
          start_date: null     # "YYYY-MM-DD" 或 null（报告期）
          end_date: null       # "YYYY-MM-DD" 或 null（报告期）
          # symbols: null      # string[]，如 ["000001", "600519"]
          # exchange: null     # string，指定 symbols 时必填

  STOCK_ZH_A_CASH_FLOW:
    variants:
      - match: {}
        config:
          start_date: null
          end_date: null

  STOCK_ZH_A_INCOME:
    variants:
      - match: {}
        config:
          start_date: null
          end_date: null

  STOCK_ZH_A_PROFIT_EXPRESS:
    variants:
      - match: {}
        config:
          start_date: null
          end_date: null

  STOCK_ZH_A_PROFIT_NOTICE:
    variants:
      - match: {}
        config:
          start_date: null
          end_date: null

  # ────────────────────────────────────────────────────────────
  # 公司行为任务（2 个） — 均使用 AmazingData SDK
  # ────────────────────────────────────────────────────────────
  # config 可配置参数（全部通用）:
  #   symbols:    string[] — 纯股票代码列表，不设则全量下载
  #   exchange:   string   — 指定 symbols 时必填
  #   start_date: string   — 公告日期起始 "YYYY-MM-DD"，null 表示不限，SDK 映射为 begin_date (int)
  #   end_date:   string   — 公告日期截止 "YYYY-MM-DD"，null 表示不限，SDK 映射为 end_date (int)
  #
  STOCK_ZH_A_DIVIDEND:
    variants:
      - match: {}
        config:
          start_date: null     # "YYYY-MM-DD" 或 null（公告日期）
          end_date: null       # "YYYY-MM-DD" 或 null（公告日期）
          # symbols: null      # string[]，如 ["000001", "600519"]
          # exchange: null     # string，指定 symbols 时必填

  STOCK_ZH_A_RIGHT_ISSUE:
    variants:
      - match: {}
        config:
          start_date: null
          end_date: null

  # ────────────────────────────────────────────────────────────
  # 回测任务（2 个） — Campaign 编排器 + Run 执行器
  # ────────────────────────────────────────────────────────────
  # config 可配置参数（Campaign / Run 通用）:
  #   mode:               string   (必填) — "historical"
  #   strategy_code:      string   (必填) — 已注册策略代码，如 "sma_cross"
  #   data_provider_code: string   (必填) — 数据源标识，如 "phoenixa_hist_daily"
  #   analyzer_profile:   string   (必填) — 分析器配置，如 "default_hist_v1"
  #   period:             string   (必填) — K线周期 "daily" / "weekly" / "monthly"
  #   start_date:         string   (必填) — "YYYY-MM-DD"
  #   end_date:           string   (必填) — "YYYY-MM-DD"
  #   symbols:            string[] — 股票代码列表，与 universe_code 二选一
  #   universe_code:      string   — 股票池代码 "ALL"，与 symbols 二选一
  #   market:             string   — "CN_A"（默认）
  #   adjust:             string   — "nf" / "qfq" / "hfq"（默认 "nf"）
  #   cash:               float    — 初始资金（默认 100000.0）
  #   commission:         float    — 手续费率（默认 0.001）
  #   strategy_params:    object   — 策略参数覆盖，如 {"fast": 5, "slow": 20}
  #   parameter_grid:     object[] — 参数网格批量回测，如 [{"fast": 5, "slow": 20}]
  #   persist_artifacts:  string[] — 持久化制品，可选值见下表
  #
  # persist_artifacts 可选值:
  #   "analyzers"      — 分析结果（收益率、夏普比率、最大回撤等）
  #   "trades"         — 交易记录明细
  #   "equity_curve"   — 逐 bar 权益曲线
  #   "plot_manifest"  — 绘图元数据清单
  #   "plot_series"    — 绘图时序数据
  #
  #
  BACKTRADER_CAMPAIGN:
    variants:
      - match: { mode: "historical" }
        config:
          mode: "historical"
          market: "CN_A"
          period: "daily"
          adjust: "nf"
          cash: 100000.0
          commission: 0.001
          data_provider_code: "phoenixa_hist_daily"
          analyzer_profile: "default_hist_v1"
          persist_artifacts: ["analyzers", "trades", "equity_curve", "plot_manifest", "plot_series"]

  BACKTRADER_RUN:
    variants:
      - match: { mode: "historical" }
        config:
          mode: "historical"
          market: "CN_A"
          period: "daily"
          adjust: "nf"
          cash: 100000.0
          commission: 0.001
          data_provider_code: "phoenixa_hist_daily"
          analyzer_profile: "default_hist_v1"
          persist_artifacts: ["analyzers", "trades", "equity_curve", "plot_manifest", "plot_series"]
```

### B. 旧文档问题修正记录

| 旧文档字段 | 问题 | 修正 |
|------------|------|------|
| `STOCK_ZH_A_HIST_PARENT.start_data` | 字段名拼写错误 | 应为 `start_date` |
| `STOCK_ZH_A_HIST_PARENT.end_data` | 字段名拼写错误 | 应为 `end_date` |
| `STOCK_ZH_A_HIST_PARENT.code_list` | 字段名与代码不一致 | 代码中实际为 `symbol_list` |
| `BACKTRADER_CAMPAIGN.timeframe` | 字段名与代码不一致 | 已修复：task.yaml 统一为 `period` |
| `BACKTRADER_CAMPAIGN.commission` 默认 `0.0` | 默认值与 task.yaml 不一致 | task.yaml 和代码中均为 `0.001` |
| 缺少 15 个任务 | 旧文档仅记录 2 个任务 | 本文档覆盖全部 17 个任务 |
| `STOCK_ZH_A_MKT_CATEGORY_MAIRUI` 未收录 | 任务已注册可执行 | 本文档已补充（原 `STOCK_ZH_A_MKT_CATEGORY`，已重命名以消除歧义） |
| `STOCK_ZH_A_MKT_CATEGORY_SWHY` 未收录 | 任务已注册可执行 | 本文档已补充 |
| 全部行业/财务/公司行为任务未收录 | 均已注册可执行 | 本文档已补充 |

### C. 已知问题

1. ~~**BACKTRADER_CAMPAIGN 命名不一致**~~：已修复 — task.yaml 中 `timeframe` 已统一改为 `period`，与代码 `parameter_check` 一致。
2. ~~**MKT_CATEGORY 硬编码 API Key**~~：已修复 — Mairui License 已提取到 config.yaml `sdk.mairui.license`，代码从配置读取。
3. **MKT_CATEGORY / MKT_CATEGORY_SWHY 无参数**：两个任务代码均不读取 `ctx.params`，属于全量拉取型任务，无需 task.yaml 变体。
4. ~~**MKT_CATEGORY 命名歧义**~~：已修复 — `STOCK_ZH_A_MKT_CATEGORY` 已重命名为 `STOCK_ZH_A_MKT_CATEGORY_MAIRUI`，与 `_SWHY` 后缀风格一致。
