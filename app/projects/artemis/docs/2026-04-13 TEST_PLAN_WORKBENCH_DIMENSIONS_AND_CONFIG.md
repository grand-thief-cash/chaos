# Test Plan — Workbench 数据维度 / 配置 / Cache 联动

> 日期: 2026-04-13
> 目的: 补齐当前 Workbench 入口层测试空白，尤其是文档里已引入但尚未系统验证的维度选择、source 切换、cache 联动场景

---

## 1. 当前已补充的自动化测试

本次已新增可执行单元测试：

- `tests/test_config_manager.py`
  - nested override deep merge
  - reload 后 source cache 不污染新配置
- `tests/test_cache_engine_partial_miss.py`
  - partial cache hit 会触发回源补齐，而不是返回不完整数据

这两类测试解决的是**已确认的真实逻辑问题**。

---

## 2. 建议下一步必须补的测试模块

## A. ConfigManager / Source 扫描

### A1. available_sources

- [ ] development 环境扫描 `config-home.yaml` / `config-production.yaml`
- [ ] production 环境只返回 `production`
- [ ] 非法 source 返回 `ValueError`
- [ ] `get_dept_services_for_source(None)` 返回当前 source 配置
- [ ] 重复 `init_config` 后缓存不污染

### A2. override merge

- [ ] base + override 对 `server` 深合并
- [ ] base + override 对 `dept_services` 深合并
- [ ] base + override 对 `data_options` 深合并
- [ ] override 中 list 覆盖语义正确
- [ ] 不存在 override 文件时使用 base config

---

## B. Workbench Route Contract

建议新增：`tests/test_workbench_routes.py`

### B1. `/workbench/sources`

- [ ] 返回 `{"sources": [...], "current": "relx|home|production"}`
- [ ] production 环境仅返回 `production`

### B2. `/workbench/data-options`

- [ ] 返回的字段完整：`asset_types/markets/periods/adjust_rules`
- [ ] 配置为空时也返回合法空结构

### B3. `/workbench/market-data`

- [ ] stock 查询返回 200
- [ ] 非法 source 返回 400
- [ ] 后端 service 抛 `ValueError` 时返回 400
- [ ] 未知异常返回 500
- [ ] Chaos 自定义 API 统一只接受 `period`

### B4. `/workbench/indicators`

- [ ] 请求体中的 `asset_type/market/period/adjust/source` 透传正确
- [ ] 行情为空时返回业务错误
- [ ] indicator engine 异常时返回 500

### B5. `/workbench/run`

- [ ] `source` 透传正确
- [ ] 无数据时返回 400
- [ ] 未注册策略返回 400

---

## C. `market_data.py` Service 单元测试

建议新增：`tests/test_workbench_market_data_service.py`

### C1. Phoenix client 构建

- [ ] source=None 使用默认 source
- [ ] source=production 使用指定 source 的 `dept_services.phoenixA`
- [ ] 未配置 phoenixA 时抛 `ValueError`

### C2. cache 行为

- [ ] cache hit 直接返回本地数据
- [ ] cache miss 触发 data_fetcher
- [ ] partial hit 触发补数（本次已在 cache_engine 层补）
- [ ] `use_cache=False` 直接回源但仍写缓存
- [ ] cache engine disabled 时直接走 PhoenixA

### C3. 数据清洗

- [ ] NaN -> None
- [ ] inf -> None
- [ ] 空 bars -> 返回 `[]`

### C4. 维度透传

- [ ] `asset_type/market/period/adjust` 正确传给 cache
- [ ] `source` 正确传给 client factory
- [ ] 后续 provider 化后，验证 provider resolve 的 key 正确

---

## D. `backtest.py` Service 单元测试

建议新增：`tests/test_workbench_backtest_service.py`

### D1. 请求校验

- [ ] `start_date > end_date` 抛错
- [ ] strategy 参数校验失败抛错
- [ ] 空 bars 抛错且错误文案包含维度信息

### D2. 维度透传

- [ ] `asset_type/market/period/adjust/source/use_cache` 传给 `get_market_bars`
- [ ] 合并 `default_params + strategy_params` 正确

### D3. 结果结构

- [ ] 返回包含 `run_meta/summary/artifacts`
- [ ] `bars_processed` 正确
- [ ] analyzer 结果能被标准化

---

## E. PhoenixA Provider / Client 测试（强烈建议）

如果后续做 provider refactor，建议新增：

### E1. stock provider

- [ ] 调用 stock endpoint 正确
- [ ] period/adjust 参数正确
- [ ] 分页直到 exhausted

### E2. index provider

- [ ] 调用 index endpoint 正确
- [ ] adjust canonical 逻辑正确（例如固定 `nf`）

### E3. pagination

- [ ] `limit=5000` 时会继续翻页
- [ ] 多页结果正确拼接
- [ ] 空页停止

---

## F. 前端 Cthulhu 测试

建议补 Angular unit test / component test：

### F1. `workbench.store.ts`

- [ ] loadSources 成功后恢复 localStorage 选中值
- [ ] loadSources 返回不含当前 source 时回退到 `current`
- [ ] loadDataOptions 成功后正确写入 options
- [ ] loadDataOptions 失败时进入错误态而不是继续可操作（后续改造）

### F2. `market-data.page.ts`

- [ ] 选中 `index` 时 adjust selector 隐藏
- [ ] 选中 `stock` 时 adjust selector 显示 nf/qfq/hfq
- [ ] 维度变化后触发 clearData
- [ ] API 请求参数正确

### F3. `strategy-config.component.ts`

- [ ] 维度选择会进入 run request
- [ ] 切 source 后提示重新运行
- [ ] 没有 data options 时禁用表单（后续改造）

---

## 3. 高风险回归场景清单

这些场景建议每次发版前至少跑一次：

1. **跨年 partial hit**  
   2024 已缓存、2025 未缓存，查询跨年范围时必须补 2025。

2. **source 切换 + data options**  
   切 source 后，所有 API 请求都必须带对 source；前端不能混用旧结果。

   同时需要验证：所有 source 共用同一套 `data_options`，切 source 不应切换维度定义。

3. **index 场景**  
   adjust 不显示，但 cache key / provider key 不能出现歧义。

4. **长区间分钟线**  
   不能 silent truncate。

5. **config override**  
   只覆盖局部字段时，其他字段必须继承 base config。

---

## 4. 我建议的测试优先级

### 第一批（本周就该补）

- [x] `test_config_manager.py`
- [x] `test_cache_engine_partial_miss.py`
- [ ] `test_workbench_market_data_service.py`
- [ ] `test_workbench_routes.py`

### 第二批（配合 refactor）

- [ ] `test_workbench_backtest_service.py`
- [ ] provider / PhoenixA pagination tests
- [ ] frontend store/component tests

---

## 5. 结论

当前项目的底层 cache 测试相对完整，但**真正贴近业务入口的 Workbench 合约测试还明显不够**。  
如果后面准备继续推进 `index`、更多 source、更多 period，我建议优先把 Workbench service/route/provider 这几层的测试补齐，否则后续改动会非常容易出现“前端可选，但后端语义未闭合”的问题。

