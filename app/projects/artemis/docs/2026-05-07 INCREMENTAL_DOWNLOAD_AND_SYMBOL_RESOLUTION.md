# 2026-05-07 增量下载与参数统一迭代

> 更新日期：2026-05-07  
> 关联文档：`2026-04-26 FINANCIAL_DATA_FIELDS.md`, `2026-05-07 FINANCIAL_DATA_PG_MIGRATION.md`  
> 影响范围：Artemis (Python)

---

## 一、背景与问题

### 1.1 全量下载问题

之前所有财务数据和公司行为数据的下载任务都是**全量拉取**：每次执行都拉取全部历史代码的全部数据，无法按需刷新。

### 1.2 SDK 参数未充分利用

查阅 `AmazingData_development_guide.md` (V1.0.24)，各 SDK 接口支持的参数如下：

| SDK 方法 | `code_list` | `begin_date` | `end_date` | 日期含义 |
|----------|:-----------:|:------------:|:----------:|---------|
| **财务数据** |
| `get_balance_sheet` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 报告期 |
| `get_cash_flow` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 报告期 |
| `get_income` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 报告期 |
| `get_profit_express` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 报告期 |
| `get_profit_notice` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 报告期 |
| **公司行为** |
| `get_dividend` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 公告日期 |
| `get_right_issue` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 公告日期 |
| **行业指数** |
| `get_industry_constituent` | ✅ 必选 | ❌ 不支持 | ❌ 不支持 | - |
| `get_industry_weight` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 交易日期 |
| `get_industry_daily` | ✅ 必选 | ✅ 可选 | ✅ 可选 | 交易日期 |

### 1.3 参数命名不统一

之前 `industry_daily` 和 `industry_weight` 各自实现了 `_parse_date_to_int` 工具函数，需要统一。

---

## 二、设计方案

### 2.1 统一参数约定

整个项目统一使用 `start_date` / `end_date` 作为日期参数名，格式固定为 `"YYYY-MM-DD"` 字符串。  
在调用 AmazingData SDK 时由 `get_sdk_date_kwargs()` 自动映射为 `begin_date` / `end_date` (int)。

| 我们的参数 | 格式 | SDK 参数 | SDK 格式 |
|-----------|------|---------|---------|
| `start_date` | `"2024-01-01"` (str) | `begin_date` | `20240101` (int) |
| `end_date` | `"2024-12-31"` (str) | `end_date` | `20241231` (int) |

### 2.2 symbols + exchange 参数

在 task.yaml 和 ctx.params 中，证券代码和交易所**分开配置**，与 `security_registry` 的存储格式保持一致：

```yaml
# task.yaml 或 cronjob params
symbols: ["000001", "600519"]
exchange: "SZ"
start_date: "2024-01-01"
```

由 `get_symbols_from_params()` 在 SDK 调用边界组合为 AmazingData 格式：`["000001.SZ", "600519.SZ"]`

**规则**：
- `symbols` 不传 → 全量下载（不需要 `exchange`）
- `symbols` 传了 → `exchange` **必填**
- `exchange` 为单一交易所代码，如 `"SZ"` 或 `"SH"`
- 如果需要不同交易所的股票，分两次任务执行

### 2.3 每个 API 只支持文档声明的参数

- `get_industry_constituent`：**不支持** `start_date`/`end_date`（SDK 无此参数）
- 其他财务/公司行为/行业权重/行业日行情：支持 `start_date`/`end_date`

### 2.4 幂等写入

PhoenixA 的 DAO 层使用 `ON CONFLICT ... DO UPDATE`，增量下载可安全重复执行。

---

## 三、共享工具函数

### `utils.py` 新增

```python
def get_symbols_from_params(ctx) -> Optional[List[str]]:
    """从 ctx.params 读取 symbols + exchange，组合为 AmazingData 格式。
    symbols: ["000001", "600519"]  +  exchange: "SZ"
    → ["000001.SZ", "600519.SZ"]
    symbols 缺省时返回 None（全量下载模式）。"""

def get_sdk_date_kwargs(ctx) -> Dict[str, int]:
    """将 start_date/end_date ('YYYY-MM-DD' str) 映射为 SDK 的 begin_date/end_date (int)。
    返回: {'begin_date': 20240101} 或 {} （仅包含非空值）"""
```

---

## 四、调用示例

```yaml
# 全量下载（默认，无参数）
task_code: STOCK_ZH_A_BALANCE_SHEET
params: {}

# 增量：指定股票 + 报告期范围
task_code: STOCK_ZH_A_BALANCE_SHEET
params:
  symbols: ["000001", "600519"]
  exchange: "SZ"
  start_date: "2024-01-01"

# 增量：指定沪市股票的全部历史分红
task_code: STOCK_ZH_A_DIVIDEND
params:
  symbols: ["600519"]
  exchange: "SH"

# 行业日行情：只指定日期范围（全量指数）
task_code: STOCK_ZH_A_INDUSTRY_DAILY_SWHY
params:
  start_date: "2024-01-01"
  end_date: "2024-12-31"

# 行业成分股：只支持 symbols（无日期参数，SDK 不支持）
task_code: STOCK_ZH_A_INDUSTRY_CONSTITUENT_SWHY
params:
  symbols: ["801010.SI", "801020.SI"]
  exchange: ""  # 行业指数代码已包含后缀
```

---

## 五、变更文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `download/zh/utils.py` | **重构** | 新增 `get_symbols_from_params()` + `get_sdk_date_kwargs()`，消除各任务重复代码 |
| `download/zh/base_financial_statement.py` | **重构** | `execute()` 使用共享工具；`_sdk_call(**sdk_date_kwargs)` |
| `download/zh/base_corporate_action.py` | **重构** | 同上 |
| `download/zh/stock_zh_a_balance_sheet.py` | 修改 | `_sdk_call` 透传 `**sdk_date_kwargs` |
| `download/zh/stock_zh_a_cash_flow.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_income.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_profit_express.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_profit_notice.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_dividend.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_right_issue.py` | 修改 | 同上 |
| `download/zh/stock_zh_a_industry_weight_swhy.py` | **重构** | 移除局部 `_parse_date_to_int`，改用共享工具 |
| `download/zh/stock_zh_a_industry_daily_swhy.py` | **重构** | 同上 |
| `download/zh/stock_zh_a_industry_constituent_swhy.py` | 小改 | 使用 `get_symbols_from_params`；不传日期参数（SDK 不支持） |

