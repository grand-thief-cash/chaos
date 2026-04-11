# Feature: Workbench 数据维度选择

> 日期: 2026-04-11
> 状态: Design

## 1. 背景

Workbench 当前只有 **Source** 选择（default/home/production），本质是切换后端环境。数据维度 `asset_type` / `market` / `period` / `adjust` 全部硬编码（`stock` / `zh_a` / `daily` / `nf`）。

Cache Engine 已就绪，按 `asset_type/market/period/adjust` 四级目录组织缓存。无论有没有 cache，这些维度都是 workbench 查数据的必要参数——有 cache 走 cache，没 cache 直接从 phoenixA 获取。需要将这些维度暴露为前端可选项。

## 2. 设计原则

1. **Source 保留**：数据维度依附于数据源，先选 Source 再选维度
2. **data_options 独立于 cache_engine**：作为顶层配置直接挂在 `Config` 上，不归 engine 管理——它只是 workbench 服务查询参数的选项定义，有 cache 走 cache，没 cache 直接从 phoenixA 获取
3. **无兜底逻辑**：组合是开放的，查不到数据就返回空
4. **联动关系**：`adjust` 可选项取决于 `asset_type`（如 index 无复权）

## 3. 维度联动

| asset_type | adjust 可选项 |
|------------|--------------|
| `stock`    | `nf` / `qfq` / `hfq` |
| `index`    | 无（不显示 adjust 选择器） |

其余维度（market、period）无联动，自由组合。

## 4. 配置模型

### 4.1 新增 Model — `artemis/models/configs.py`

```python
class DataOption(BaseModel):
    """单个选项（value + 展示 label）。"""
    value: str
    label: str


class AdjustRule(BaseModel):
    """asset_type → 可用 adjust 列表。"""
    asset_type: str
    options: list[DataOption]


class DataOptionsCfg(BaseModel):
    """Workbench 数据维度选项配置。"""
    asset_types: list[DataOption]
    markets: list[DataOption]
    periods: list[DataOption]
    adjust_rules: list[AdjustRule]
```

### 4.2 Config 扩展 — 顶层字段

`data_options` 直接挂在 `Config` 顶层，与 `server`、`engine`、`dept_services` 平级，不归入 engine 体系。

```python
class Config(BaseModel):
    env: str = 'development'
    server: ServerCfg = ...
    engine: EngineCfg = ...
    dept_services: DeptServicesCfg = ...
    data_options: DataOptionsCfg = Field(default_factory=DataOptionsCfg)  # 新增，顶层
    ...
```

### 4.3 config.yaml

```yaml
data_options:
    asset_types:
      - { value: "stock", label: "股票" }
      - { value: "index", label: "指数" }
    markets:
      - { value: "zh_a", label: "A股" }
    periods:
      - { value: "daily", label: "日线" }
      - { value: "weekly", label: "周线" }
      - { value: "5min", label: "5分钟" }
      - { value: "15min", label: "15分钟" }
      - { value: "30min", label: "30分钟" }
      - { value: "60min", label: "60分钟" }
    adjust_rules:
      - asset_type: "stock"
        options:
          - { value: "nf", label: "不复权" }
          - { value: "qfq", label: "前复权" }
          - { value: "hfq", label: "后复权" }
      - asset_type: "index"
        options: []
```

## 5. API 变更

### 5.1 新增 `GET /workbench/data-options`

返回配置中定义的选项列表：

```json
{
  "asset_types": [{"value": "stock", "label": "股票"}, {"value": "index", "label": "指数"}],
  "markets": [{"value": "zh_a", "label": "A股"}],
  "periods": [{"value": "daily", "label": "日线"}, ...],
  "adjust_rules": [
    {"asset_type": "stock", "options": [{"value": "nf", "label": "不复权"}, ...]},
    {"asset_type": "index", "options": []}
  ]
}
```

### 5.2 `GET /workbench/market-data` 参数扩展

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `asset_type` | `str` | — | 资产类型（必选） |
| `market` | `str` | — | 市场（必选） |
| `period` | `str` | — | 周期（必选，原 `timeframe`） |
| `adjust` | `str` | — | 复权方式（必选） |
| `symbol` | `str` | — | 股票代码 |
| `start_date` / `end_date` | `str` | — | 日期范围 |
| `source` | `str` | `None` | 数据源环境 |
| `use_cache` | `bool` | `True` | 是否走缓存 |

> **注**：`timeframe` 参数建议统一为 `period`，与 cache_engine 保持一致。可保留 `timeframe` 作为 alias 兼容。

### 5.3 `POST /workbench/indicators` 扩展

`IndicatorsRequest` 新增字段：

```python
class IndicatorsRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "daily"
    adjust: str = "nf"
    asset_type: str = "stock"    # 新增
    market: str = "zh_a"         # 新增
    indicators: List[IndicatorReq]
    source: Optional[str] = None
```

## 6. 服务层变更

### `artemis/services/workbench/market_data.py`

`get_market_bars()` 签名变更：

```python
def get_market_bars(
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "daily",
    adjust: str = "nf",
    asset_type: str = "stock",   # 新增
    market: str = "zh_a",        # 新增
    source: str | None = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
```

当前硬编码 `asset_type="stock", market="zh_a"` → 改为接收参数透传给 cache_engine。

## 7. 前端变更 (Cthulhu)

### 7.1 模型 — `workbench.model.ts`

```typescript
export interface DataOption {
  value: string;
  label: string;
}

export interface AdjustRule {
  asset_type: string;
  options: DataOption[];
}

export interface DataOptionsResponse {
  asset_types: DataOption[];
  markets: DataOption[];
  periods: DataOption[];
  adjust_rules: AdjustRule[];
}
```

### 7.2 Store — `workbench.store.ts`

- **保留** Source 相关逻辑（`_sources`、`loadSources`、`selectSource`）
- 新增 data options 加载 + 选中值管理
- 无 fallback：选项未加载完成时不可操作

### 7.3 Market Data 页 — `market-data.page.ts`

- **保留** Source 选择器
- 新增 Asset / Market / Period / Adjust 四个下拉（排在 Source 之后）
- adjust 根据 asset_type 联动：从 `adjust_rules` 中查找当前 asset_type 对应的 options
- index 选中时 adjust 下拉不显示
- 选中值传递给所有 API 调用（getMarketData、calculateIndicators）

### 7.4 Strategy Config — `strategy-config.component.ts`

- **保留** Source 选择器
- 新增数据维度选择器（同上联动逻辑）
- Run Backtest 请求中传递 asset_type / market / period / adjust

## 8. 数据流

```
用户选择 Source + asset/market/period/adjust
        │
        ▼
GET /workbench/market-data?source=X&asset_type=stock&market=zh_a&period=daily&adjust=nf&symbol=000001&...
        │
        ▼
get_market_bars(asset_type=stock, market=zh_a, ...)
        │
        ├─ cache_engine.get(asset_type, market, period, adjust, ...)
        │     └─ cache hit → 返回
        │     └─ cache miss → 回源 phoenixA → 写入 cache → 返回
        │
        └─ 无 cache → 直接 phoenixA → 返回
```

## 9. 验证

1. `GET /workbench/data-options` 返回配置中定义的选项列表
2. `GET /workbench/market-data?asset_type=stock&market=zh_a&...` 参数透传到 cache_engine / phoenixA
3. 前端 Source 选择器保留，新增四个维度下拉
4. 选 index 时 adjust 下拉消失；选 stock 时显示 nf/qfq/hfq
5. 不同维度组合请求数据，无数据时展示空状态
6. 同步验证 config-home.yaml / config-production.yaml 的 data_options 配置
