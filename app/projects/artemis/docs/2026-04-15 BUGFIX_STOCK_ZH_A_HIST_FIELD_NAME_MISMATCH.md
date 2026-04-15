# BugFix: STOCK_ZH_A_HIST_PARENT 字段命名不匹配

> 日期：2026-04-15  
> 范围：`task_engine/download/zh/stock_zh_a_hist_child.py` + `config/task.yaml`  
> 根因：Artemis 发送 bars 使用旧字段名 `date`/`code`，PhoenixA v2 API 期望 `trade_date`/`symbol`

---

## 1. 错误现象

执行 `STOCK_ZH_A_HIST_PARENT` 任务时，PhoenixA 返回 400：

```
Error 1292 (22007): Incorrect date value: '' for column 'trade_date' at row 1
```

完整错误链路：
1. **phoenixA_upsert_bars_failed** — bars upsert 失败，status=400
2. **STOCK_ZH_A_HIST_CHILD task_failed** — `failed to sink stock hist for code=600000`，失败阶段：`sink`
3. **STOCK_ZH_A_HIST_PARENT task_failed** — 子任务在 index 0 失败，父任务终止

---

## 2. 根因分析

### 2.1 字段命名不匹配

PhoenixA v2 重构后统一了字段命名：

| 层级 | 旧名 | 新名（v2） | 说明 |
|------|------|-----------|------|
| DB/Model | `code` | `symbol` | `StandardBar.Symbol` (`json:"symbol"`) |
| DB/Model | `date` | `trade_date` | `StandardBar.TradeDate` (`json:"trade_date"`) |

但 Artemis `StockZhAHistChild` 仍在发送旧字段名：

```
execute()   → df['code'] = raw_code        # ❌ 应为 df['symbol']
post_process → 保留 "date", "code" 列名      # ❌ 应为 "trade_date", "symbol"
sink()      → 调用 upsert_stock_zh_a_hist()  # ❌ 传递未转换的字段
```

### 2.2 数据流追踪

```
baostock API → DataFrame(date, code, open, ...) 
            → post_process 保留 date/code 列名
            → sink → upsert_stock_zh_a_hist() → upsert_bars()
            → PhoenixA POST /api/v2/bars/stock/zh_a/upsert
            → json.Unmarshal → StandardBar{Symbol:"", TradeDate:""}  ← 空字符串！
            → MySQL INSERT → Error 1292: Incorrect date value ''
```

Go 端 `StandardBar` 通过 JSON tag 反序列化：
- `json:"symbol"` — 找不到 `symbol` key（只有 `code`）→ 空字符串 `""`
- `json:"trade_date"` — 找不到 `trade_date` key（只有 `date`）→ 空字符串 `""`
- MySQL `date` 类型列不接受空字符串 → **Error 1292**

### 2.3 扩展数据未分离

baostock 返回的扩展字段（`turn`, `peTTM`, `psTTM`, `pbMRQ`, `pcfNcfTTM`）混在标准 bars 中发送，但 PhoenixA 标准 bars 表不包含这些字段。应该分离为 `ext` 数据单独 upsert。

---

## 3. 修复方案

### 3.1 `stock_zh_a_hist_child.py`

| 方法 | 修改内容 |
|------|---------|
| `execute()` | `df['code'] = raw_code` → `df['symbol'] = raw_code` |
| `post_process()` | ① 列名映射：`date` → `trade_date`，`code` → `symbol`<br>② 分离标准 bars 和 ext 数据<br>③ 扩展字段重命名：`peTTM` → `pe_ttm` 等<br>④ `pctChg` → `pct_chg`<br>⑤ 返回 `{"bars": DataFrame, "ext": DataFrame}` |
| `sink()` | ① 接收 dict 而非 DataFrame<br>② 直接调用 `upsert_bars()`（v2）而非 `upsert_stock_zh_a_hist()`（legacy）<br>③ 传递 `source="baostock"` 和 `ext` 数据 |

### 3.2 `stock_zh_a_hist_parent.py`

| 方法 | 修改内容 |
|------|---------|
| `plan()` | `code = info.get("code")` → `symbol = info.get("symbol") or info.get("code")`<br>变量名统一为 `symbol`，日志/错误信息同步更新 |

### 3.3 `config/task.yaml`

| 修改 | 原因 |
|------|------|
| 移除 `code` 字段 | `execute()` 中已通过 `df['symbol'] = raw_code` 添加，baostock 返回的 `code` 是 `sh.600000` 格式，不是我们需要的 |
| 移除 `adjustflag, tradestatus, isST` | 这些字段 PhoenixA 不存储，移除以简化数据传输 |

字段变更：
```
# 旧
fields: "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"

# 新
fields: "date,open,high,low,close,preclose,volume,amount,turn,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM"
```

---

## 4. 字段映射总览

### 4.1 标准 Bars（StandardBar）

| baostock 原始字段 | Artemis post_process 输出 | PhoenixA JSON tag | PhoenixA DB 列 |
|-------------------|--------------------------|-------------------|---------------|
| `date` | `trade_date` | `trade_date` | `trade_date` |
| *(手动添加)* `symbol` | `symbol` | `symbol` | `symbol` |
| `open` | `open` | `open` | `open` |
| `high` | `high` | `high` | `high` |
| `low` | `low` | `low` | `low` |
| `close` | `close` | `close` | `close` |
| `preclose` | `preclose` | `preclose` | `preclose` |
| `volume` | `volume` | `volume` | `volume` |
| `amount` | `amount` | `amount` | `amount` |
| `pctChg` | `pct_chg` | `pct_chg` | `pct_chg` |

### 4.2 扩展 Bars（BarsExtBaostock）

| baostock 原始字段 | Artemis post_process 输出 | PhoenixA JSON tag | PhoenixA DB 列 |
|-------------------|--------------------------|-------------------|---------------|
| `turn` | `turn` | `turn` | `turn` |
| `peTTM` | `pe_ttm` | `pe_ttm` | `pe_ttm` |
| `psTTM` | `ps_ttm` | `ps_ttm` | `ps_ttm` |
| `pbMRQ` | `pb_mrq` | `pb_mrq` | `pb_mrq` |
| `pcfNcfTTM` | `pcf_ncf_ttm` | `pcf_ncf_ttm` | `pcf_ncf_ttm` |

---

## 5. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/clients/phoenixA_client.py` | 修改 | `get_securities()` 移除 `"code"` 向后兼容字段 |
| `engines/task_engine/download/zh/stock_zh_a_hist_child.py` | 修改 | 字段重命名 + bars/ext 分离 + v2 API 调用 + 移除 `code` 列兜底逻辑 |
| `engines/task_engine/download/zh/stock_zh_a_hist_parent.py` | 修改 | 变量/参数/API 统一为 `symbol` 系列，移除 `code_list` fallback |
| `engines/task_engine/backtest/campaign.py` | 修改 | `code_infos` → `symbol_infos` + legacy alias → v2 API |
| `config/task.yaml` | 修改 | baostock fields 移除 `code`/`adjustflag`/`tradestatus`/`isST` |
| `tests/test_backtrader_phase1.py` | 修改 | FakeClient 迁移到 v2 API，移除 `"code"` 字段 |
| `tests/test_task_error_propagation.py` | 修改 | FakeClient 迁移到 v2 API，移除 `"code"` 字段，错误断言更新 |

### 5.1 变量/参数命名统一 (`code` → `symbol`)

以下变量/参数/日志键全部从 `code` 系列统一为 `symbol` 系列：

| 文件 | 旧名 | 新名 | 说明 |
|------|------|------|------|
| **phoenixA_client.py** | `"code": sym` | *(移除)* | `get_securities()` 不再返回 `code` 字段 |
| **child.py** params | `"code"` | `"bs_code"` | baostock 格式 code（如 `sh.600000`） |
| **child.py** params | `"raw_code"` | `"symbol"` | plain symbol（如 `600000`） |
| **child.py** 变量 | `code` | `bs_code` | |
| **child.py** 变量 | `raw_code` | `symbol` | |
| **child.py** dead code | `if "code" in df.columns` | *(移除)* | baostock fields 已不含 `code` |
| **parent.py** fallback | `params.get("code_list")` | *(移除)* | 只读 `symbol_list` |
| **parent.py** fallback | `info.get("code")` | *(移除)* | 只读 `info.get("symbol")` |
| **parent.py** params | `"code"` | `"bs_code"` | child_params 中的 key |
| **parent.py** params | `"raw_code"` | `"symbol"` | child_params 中的 key |
| **parent.py** 变量 | `code_list_str` | `symbol_list_str` | |
| **parent.py** 变量 | `codes` | `symbols` | |
| **parent.py** 变量 | `code_infos` | `symbol_infos` | |
| **parent.py** ctx.params key | `"code_infos"` | `"symbol_infos"` | |
| **parent.py** 日志 | `"total_codes"` | `"total_symbols"` | |
| **parent.py** API 调用 | `get_stock_zh_a_codes()` | `get_securities()` | v2 API |
| **parent.py** API 调用 | `get_stock_zh_a_last_updates()` | `get_bars_last_update()` | v2 API |
| **campaign.py** 变量 | `code_infos` | `symbol_infos` | |
| **campaign.py** ctx.params key | `"code_infos"` | `"symbol_infos"` | |
| **campaign.py** API 调用 | `get_stock_zh_a_codes()` | `get_securities()` | v2 API |
| **campaign.py** API 调用 | `get_stock_zh_a_last_updates()` | `get_bars_last_update()` | v2 API |

### 5.2 保留 `code` 的合理场景

以下位置的 `code` 是正确的，不做修改：

| 位置 | 原因 |
|------|------|
| `phoenixA_client._normalize_bars_v2_to_cache()` | CacheEngine 内部使用 `code`/`date` 字段名，与 v2 API 无关 |
| `phoenixA_client.stock_zh_a_list_batch_upsert()` | Legacy alias 接受旧格式 `code`/`company`，内部转换为 `symbol`/`name` |
| `phoenixA_client` 其他 legacy alias 方法定义 | 保持向后兼容，但不再有生产调用方 |
| `stock_zh_a_list.py` | akshare 返回的原始列名为 `code`，在 `stock_zh_a_list_batch_upsert` 中转换 |
| `stock_zh_a_market_category.py` | 分类 taxonomy 域的 `code` 字段，非证券 symbol |
| `test_backtrader_phase1.py` fake bars `"code": symbol` | `get_strategy_market_bars` 经过 `_normalize_bars_v2_to_cache()` 返回 CacheEngine 格式 |
| `strategy_registry.py` `spec.code` | 策略注册码，非证券 symbol |

---

## 6. 验证步骤

1. 重启 Artemis
2. 触发 `STOCK_ZH_A_HIST_PARENT` 任务（`period=daily, adjust=hfq`）
3. 检查日志：
   - 应看到 `stock_zh_a_hist_child_success` 事件，包含 `bars_count` 和 `ext_count`
   - 不应再有 `Error 1292` 或 `phoenixA_upsert_bars_failed`
4. 检查 PhoenixA 数据库：
   - `bars_stock_zh_a_daily_hfq` 表应有 `symbol` 和 `trade_date` 正确填充
   - `bars_ext_baostock_stock_zh_a_daily` 表应有对应的扩展数据

---

## 7. 导入任务说明

`tasks_export_2026-04-15.json` **不需要修改**。该文件定义的是 cronjob 任务元数据（调度表达式、目标路径、body_template），body_template 中只传递 `period` 和 `adjust` 参数，与字段命名无关。实际的字段映射由 `task.yaml` 的 variant config 和 `StockZhAHistChild` 代码控制。

