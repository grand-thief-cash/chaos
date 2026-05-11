# Factor Engine Data Contract

## 概述

本文档定义了 Artemis Factor Engine 数据需求与 PhoenixA API 供给之间的契约关系。

**版本**: v1.0
**日期**: 2026-05-11
**适用范围**: Artemis factor_engine ↔ PhoenixA 数据集成

---

## 1. 接口映射

### 1.1 FactorDataProvider 接口定义

```python
class FactorDataProvider(Protocol):
    def get_active_symbols(self, market: str, as_of_date: str) -> List[str]
    def get_industry_map(self, taxonomy: str, market: str) -> Dict[str, str]
    def get_financial_data(self, symbol: str, as_of_date: str) -> Dict[str, pd.DataFrame]
    def get_market_data(self, symbol: str, as_of_date: str) -> Optional[pd.DataFrame]
    def get_current_period(self, symbol: str, as_of_date: str) -> Optional[str]
```

### 1.2 PhoenixA API 映射

| FactorDataProvider 方法 | PhoenixA API | 参数说明 |
|----------------------|--------------|---------|
| `get_active_symbols` | `GET /api/v2/securities?market=zh_a&asset_type=stock` | 返回活跃股票列表 |
| `get_industry_map` | `GET /api/v2/taxonomy/by_security/{symbol}` (批量调用) | 返回 symbol → industry_code 映射 |
| `get_financial_data` | `GET /api/v2/financial/amazing_data/{statement_type}` | 支持 PIT 和多期查询 |
| `get_market_data` | `GET /api/v2/bars/stock/zh_a?symbol={symbol}&end_date={as_of_date}` | 返回 K 线数据 |
| `get_current_period` | `GET /api/v2/financial/amazing_data/{statement_type}?symbol={symbol}&ann_date_before={as_of_date}` | 返回最新报告期 |

---

## 2. 财务数据契约

### 2.1 数据转换规则

PhoenixA → pandas DataFrame 转换：

```python
# PhoenixA API 响应格式
{
    "data": [
        {
            "id": 1,
            "source": "amazing_data",
            "symbol": "000001",
            "market": "zh_a",
            "statement_type": "balance_sheet",
            "reporting_period": "2024-12-31",
            "report_type": "年报",
            "statement_code": "C101",
            "security_name": "平安银行",
            "ann_date": "2025-03-21",
            "actual_ann_date": "2025-03-21",
            "comp_type_code": 2,
            "data_json": {
                "TOTAL_ASSETS": 5431234567.89,
                "TOT_SHARE_EQUITY_EXCL_MIN_INT": 234567890.12,
                "CURRENCY_CAP": 123456789.01,
                "INV": 98765432.1,
                "TOT_SHARE": 19406000000
            },
            "created_at": "2025-03-21T10:00:00Z",
            "updated_at": "2025-03-21T10:00:00Z"
        }
    ],
    "total": 100
}

# 转换为 pandas DataFrame 格式
def convert_to_dataframe(api_response: dict) -> pd.DataFrame:
    rows = []
    for item in api_response["data"]:
        row = {
            "reporting_period": item["reporting_period"],
            "ann_date": item["ann_date"],
        }
        # 展开 data_json 字段
        row.update(item.get("data_json", {}))
        rows.append(row)
    return pd.DataFrame(rows)
```

### 2.2 PIT (Point-in-Time) 过滤

**用途**: 避免未来数据穿透（look-ahead bias）

**规则**:
- 使用 `ann_date_before` 参数过滤：`ann_date < as_of_date`
- 因子计算时只能使用在 `as_of_date` 之前已披露的数据

**示例**:
```python
# 计算 2025-04-01 的因子时，只能使用 2025-04-01 之前披露的数据
ann_date_before = "2025-04-01"
```

### 2.3 TTM (Trailing Twelve Months) 计算

**需要的报告期**:
- 当前期（如 2024-12-31）
- 上年年报（2023-12-31）
- 上年同期（2023-09-30）
- 至少 5 个季度的数据

**PhoenixA 支持**:
- `reporting_periods` 参数支持批量查询：`reporting_periods=2024-12-31,2024-09-30,2024-06-30,...`

**实现**:
```python
def get_ttm_periods(current_period: str) -> List[str]:
    """计算 TTM 需要的报告期列表"""
    year = int(current_period[:4])
    quarter = int(current_period[5:7]) // 3

    periods = [current_period]
    # 添加过去几个季度
    for i in range(1, 5):
        q = quarter - i
        y = year
        if q <= 0:
            q += 4
            y -= 1
        period = f"{y}-{q*3:02d}-{'31' if q==4 else '30'}"
        periods.append(period)

    return periods
```

### 2.4 字段语义对照

| 因子引擎字段名 | AmazingData 字段名 | PhoenixA data_json | 语义说明 | 单位 |
|--------------|------------------|-------------------|---------|------|
| **资产负债表** | | | | |
| TOTAL_ASSETS | TOTAL_ASSETS | 总资产 | 元 | |
| TOT_SHARE_EQUITY_EXCL_MIN_INT | TOT_SHARE_EQUITY_EXCL_MIN_INT | 归属于母公司所有者权益 | 元 | |
| CUR_ASSETS | CUR_ASSETS | 流动资产 | 元 | |
| CUR_LIAB | CUR_LIAB | 流动负债 | 元 | |
| INV | INV | 存货 | 元 | |
| ACCT_RECEIVABLE | ACCT_RECEIVABLE | 应收账款 | 元 | |
| ACCT_PAYABLE | ACCT_PAYABLE | 应付账款 | 元 | |
| CURRENCY_CAP | CURRENCY_CAP | 货币资金 | 元 | |
| ST_BORROWING | ST_BORROWING | 短期借款 | 元 | |
| LT_LOAN | LT_LOAN | 长期借款 | 元 | |
| BONDS_PAYABLE | BONDS_PAYABLE | 应付债券 | 元 | |
| GOODWILL | GOODWILL | 商誉 | 元 | |
| TOT_SHARE | TOT_SHARE | 股本 | 股 | |
| **利润表** | | | | |
| OPERA_REV | OPERA_REV | 营业收入 | 元 | |
| LESS_OPERA_COST | LESS_OPERA_COST | 营业成本 | 元 | |
| OPERA_PROFIT | OPERA_PROFIT | 营业利润 | 元 | |
| NET_PRO_EXCL_MIN_INT_INC | NET_PRO_EXCL_MIN_INT_INC | 归属于母公司所有者的净利润 | 元 | |
| INC_TAX | INC_TAX | 所得税费用 | 元 | |
| **现金流量表** | | | | |
| NET_CASH_FLOWS_OPER_ACT | NET_CASH_FLOWS_OPER_ACT | 经营活动产生的现金流量净额 | 元 | |
| CASH_PAID_PUR_CONST_FIOLTA | CASH_PAID_PUR_CONST_FIOLTA | 购建固定资产、无形资产和其他长期资产支付的现金 | 元 | |

### 2.5 市值数据

**计算方式** (PhoenixA 当前不直接存储市值):
```
market_cap = close_price × TOT_SHARE
```

- `close_price`: 来自 `bars_daily` 表 (via `GET /api/v2/bars/stock/zh_a`)
- `TOT_SHARE`: 来自 `balance_sheet.data_json`

**示例**:
```python
def get_market_cap(symbol: str, as_of_date: str) -> Optional[float]:
    # 1. 获取当日收盘价
    bars = client.get_bars(
        asset_type="stock",
        market="zh_a",
        symbol=symbol,
        start_date=as_of_date,
        end_date=as_of_date,
    )
    if not bars:
        return None
    close = bars[0]["close"]

    # 2. 获取最新股本
    balance_sheet = query_financial_statements(
        source="amazing_data",
        statement_type="balance_sheet",
        symbol=symbol,
        ann_date_before=as_of_date,
        page_size=1,
    )
    if not balance_sheet["data"]:
        return None
    total_share = balance_sheet["data"][0]["data_json"].get("TOT_SHARE")

    if close and total_share:
        return close * total_share / 100000000  # 转换为亿元
    return None
```

---

## 3. 行业分类契约

### 3.1 申万一级行业映射

**API**: `GET /api/v2/taxonomy/by_security/{symbol}`

**响应格式**:
```json
[
    {
        "source": "sw",
        "taxonomy": "industry",
        "category_code": "801010",
        "symbol": "000001",
        "asset_type": "stock",
        "market": "zh_a"
    }
]
```

**使用规则**:
- 因子引擎使用申万一级行业 (sw_l1)
- `taxonomy = "industry"`, `source = "sw"`
- 使用第一个匹配的 `category_code` 作为行业代码

### 3.2 金融行业过滤

**行业代码映射** (部分):
- `801010`: 银行
- `801780`: 非银行金融

**排除规则**:
- `exclude_financial = True` 的因子（如 ROIC）不计算金融行业股票
- 根据 `comp_type_code` 或行业代码判断

---

## 4. 行情数据契约

### 4.1 K 线数据

**API**: `GET /api/v2/bars/stock/zh_a`

**参数**:
- `symbol`: 证券代码
- `start_date`: 开始日期
- `end_date`: 结束日期
- `period`: 周期 (daily/weekly/monthly)
- `adjust`: 复权方式 (nf=不复权, qfq=前复权, hfq=后复权)

**响应格式**:
```json
{
    "data": [
        {
            "trade_date": "2025-04-01",
            "symbol": "000001",
            "open": 12.34,
            "high": 12.56,
            "low": 12.28,
            "close": 12.45,
            "volume": 12345678,
            "amount": 153456789.12
        }
    ]
}
```

### 4.2 字段映射

| Factor引擎需要 | PhoenixA 字段 | 语义 |
|--------------|--------------|------|
| close | close | 收盘价 |
| volume | volume | 成交量 |
| - | open/high/low | (可选) |

---

## 5. 数据质量要求

### 5.1 必填字段

| 数据类型 | 必填字段 |
|---------|---------|
| 财务报表 | symbol, reporting_period, ann_date, data_json |
| 行情 | symbol, trade_date, close |
| 行业映射 | symbol, category_code |

### 5.2 空值处理

- `None` / `NaN`: 视为缺失数据
- 0: 可能是真实值（如净利润为0），需要根据字段语义判断
- 空字符串 `""`: 视为缺失

### 5.3 单位一致性

- 所有金额字段单位为"元"
- 股本单位为"股"
- 日期格式为 `YYYY-MM-DD`

---

## 6. API 调用示例

### 6.1 获取财务数据（支持 PIT 和多期）

```python
from artemis.core.clients.phoenixA_client import PhoenixAClient

client = PhoenixAClient(base_url="http://localhost:8080")

# 获取平安银行资产负债表数据，TTM 需要 5 个期
periods = ["2024-12-31", "2024-09-30", "2024-06-30", "2024-03-31", "2023-12-31"]
response = client.query_financial_statements(
    source="amazing_data",
    statement_type="balance_sheet",
    symbol="000001",
    ann_date_before="2025-04-01",  # PIT 过滤
    reporting_periods=periods,
)

# 转换为 DataFrame
import pandas as pd
rows = []
for item in response["data"]:
    row = {"reporting_period": item["reporting_period"]}
    row.update(item["data_json"])
    rows.append(row)
df = pd.DataFrame(rows)
```

### 6.2 获取行业映射

```python
# 批量获取所有股票的行业映射
industry_map = {}
for symbol in active_symbols:
    mappings = client.get_taxonomy_by_security(symbol)
    for m in mappings:
        if m["source"] == "sw" and m["taxonomy"] == "industry":
            industry_map[symbol] = m["category_code"]
            break

# industry_map: {"000001": "801010", "000002": "801020", ...}
```

### 6.3 获取行情数据

```python
bars = client.get_bars(
    asset_type="stock",
    market="zh_a",
    symbol="000001",
    start_date="2025-04-01",
    end_date="2025-04-01",
)

df = pd.DataFrame(bars)
# columns: trade_date, symbol, open, high, low, close, volume, amount
```

---

## 7. 因子覆盖度

### 7.1 盈利能力因子 (6 个)

| 因子 | 数据需求 | PhoenixA 覆盖 | 状态 |
|------|---------|---------------|------|
| roe | NI_TTM, equity | ✅ | 完全覆盖 |
| roa | NI_TTM, total_assets | ✅ | 完全覆盖 |
| gross_margin | REV_TTM, COST_TTM | ✅ | 完全覆盖 |
| operating_margin | OPERA_PROFIT_TTM, REV_TTM | ✅ | 完全覆盖 |
| net_margin | NI_TTM, REV_TTM | ✅ | 完全覆盖 |
| roic | NOPAT, invested_capital | ✅ | 完全覆盖 |

### 7.2 估值因子 (7 个)

| 因子 | 数据需求 | PhoenixA 覆盖 | 状态 |
|------|---------|---------------|------|
| pe_ttm | market_cap, NI_TTM | ✅ | 通过 close × TOT_SHARE 计算 |
| pb | market_cap, equity | ✅ | 通过 close × TOT_SHARE 计算 |
| ps_ttm | market_cap, REV_TTM | ✅ | 通过 close × TOT_SHARE 计算 |
| peg | pe, growth | ✅ | 依赖 pe |
| ev_to_ebitda | EV, EBITDA | ⚠️ | 需确认债务数据 |
| pcf | market_cap, OCF_TTM | ✅ | 通过 close × TOT_SHARE 计算 |
| dividend_yield | DPS, close | ✅ | 需确认 DPS 数据 |

### 7.3 每股指标因子 (5 个)

| 因子 | 数据需求 | PhoenixA 覆盖 | 状态 |
|------|---------|---------------|------|
| eps_ttm | NI_TTM, TOT_SHARE | ✅ | 完全覆盖 |
| bps | equity, TOT_SHARE | ✅ | 完全覆盖 |
| cfps | OCF_TTM, TOT_SHARE | ✅ | 完全覆盖 |
| fcf_per_share | FCF_TTM, TOT_SHARE | ✅ | 完全覆盖 |
| dps | dividends, TOT_SHARE | ⚠️ | 需确认 dividend 数据 |

### 7.4 其他因子 (18 个)

成长、质量、偿债、效率因子主要依赖财务报表历史数据。

**状态**: ✅ 数据充足，需要 PIT 过滤和多期批量查询

---

## 8. 性能优化建议

### 8.1 批量查询

- **行业映射**: 使用 PhoenixA 缓存或批量查询
- **财务数据**: 使用 `reporting_periods` 参数一次获取多个期

### 8.2 本地缓存

- **行业映射**: 每日刷新一次即可（行业变更不频繁）
- **证券列表**: 每日刷新
- **财务数据**: 根据 `ann_date` 判断是否需要刷新

### 8.3 并发请求

- 多只股票的财务数据可以并发请求
- 使用连接池复用 HTTP 连接

---

## 9. 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-05-11 | 初始版本，定义 FactorDataProvider ↔ PhoenixA 契约 |

---

## 10. 相关文档

- [FACTOR_ENGINE_DATA_DESIGN.md](./2026-05-11%20FACTOR_ENGINE_DATA_DESIGN.md) - 因子引擎数据需求分析
- [AmazingData_development_guide.md](../../../docs/AmazingData_development_guide.md) - AmazingData 数据源文档
- [SDK_DOWNLOAD_TASK_ONBOARDING.md](../../../app/tools/py/skills/[2026-04-28]SDK_DOWNLOAD_TASK_ONBOARDING.md) - SDK 下载任务 onboarding 技能
