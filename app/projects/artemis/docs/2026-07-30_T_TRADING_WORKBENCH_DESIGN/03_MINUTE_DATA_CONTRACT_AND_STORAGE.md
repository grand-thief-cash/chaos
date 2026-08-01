# 03. 分钟数据契约与存储

## 1. 周期规范

内部 canonical period：

| 内部值 | BaoStock | AmazingData | UI label |
|---|---:|---|---|
| min1 | 不支持 | `Period.min1` | 1 分钟 |
| min5 | `5` | `Period.min5` | 5 分钟 |
| min15 | `15` | `Period.min15` | 15 分钟 |
| min30 | `30` | `Period.min30` | 30 分钟 |
| min60 | `60` | `Period.min60` | 60 分钟 |

`1min/5min/...` 仅作为迁移期输入别名，在 API 边界立即归一化；表名、缓存路径、报告和模型元数据全部使用 canonical value。

## 2. 分钟 bar 契约

第一轮沿用 PhoenixA Standard Bars API 的 `trade_date` JSON 字段以降低跨服务改动，但语义按 period 区分：

- daily/weekly/monthly：`YYYY-MM-DD`；
- intraday：RFC3339 时间戳，例如 `2026-07-29T09:35:00+08:00`。

领域层统一将 intraday `trade_date` 视为 `bar_time/bar_end`，Cthulhu 接收时映射为 `Bar.date`，不得截断。

标准字段：

| 字段 | 类型 | 规则 |
|---|---|---|
| security_id | uint64 | API 必填、物理主键，逻辑关联 `security_registry.id` |
| symbol | string | 不进入 bars 物理表；响应需要展示时从 registry 读取 |
| trade_date | timestamptz | 分钟 bar 时间，Asia/Shanghai offset |
| open/high/low/close | numeric(20,4) | 非空、有限数、`low <= O/C <= high` |
| volume | bigint nullable | 供应商原始整数值；真实 AmazingData 样本需核验股票/指数单位后再声明跨源可比 |
| amount | bigint nullable | 统一为人民币元，四舍五入 |
| preclose/pct_chg | nullable | 分钟源缺失时保持 NULL |

## 3. 物理表

已存在/新增：

```sql
ods.bars_stock_zh_a_min5_nf
ods.bars_stock_zh_a_min1_nf
ods.bars_stock_zh_a_min30_nf
ods.bars_index_zh_a_min1_nf
ods.bars_index_zh_a_min5_nf
```

建议结构：

```sql
CREATE TABLE ods.bars_stock_zh_a_min5_nf (
    security_id BIGINT NOT NULL,
    trade_date  TIMESTAMPTZ NOT NULL,
    open        NUMERIC(20,4) NOT NULL,
    high        NUMERIC(20,4) NOT NULL,
    low         NUMERIC(20,4) NOT NULL,
    close       NUMERIC(20,4) NOT NULL,
    volume      BIGINT,
    amount      BIGINT,
    preclose    NUMERIC(20,4),
    pct_chg     NUMERIC(10,4),
    PRIMARY KEY (security_id, trade_date)
);
```

转换为 TimescaleDB hypertable，建议 chunk 为 1 个月，并建立：

- `(security_id, trade_date DESC)`；
- `(trade_date DESC)`。

新增表由 PhoenixA migration `0014_amazing_data_intraday_context.sql` 创建。尚未投入使用的旧日线 bars 定义已直接在干净基线 `0001_ods.sql` 中改为 `security_id` 物理键，不再保留 `0015` 式补丁迁移。日线复用既有 stock/index daily 表；本阶段不创建行业指数分钟表。

## 4. 为什么只存不复权成交价

做 T 成交发生在交易所实际价格上。前复权历史价格会随未来公司行为改变，直接用于历史成交会造成错误价格甚至未来信息污染。因此：

- 分钟成交与回放默认 `adjust=nf`；
- 跨日连续技术特征需要时，通过 point-in-time 可用的复权因子生成研究视图；
- API 对非 `nf` 分钟表在表不存在时明确返回数据源不可用，而不是静默退回 `nf`。

## 5. BaoStock 时间转换

BaoStock `time` 格式为 `YYYYMMDDHHMMSSsss`。转换步骤：

1. 校验 17 位数字；
2. 解析年月日时分秒和毫秒；
3. 绑定 `Asia/Shanghai`；
4. 输出 RFC3339；
5. 校验 `date` 与 `time` 的日期部分一致；
6. 丢弃午休区间和交易时段外的异常记录，但记录 rejected reason。

源时间究竟代表 bar start 或 bar end 必须通过样本与供应商说明确认。BaoStock 字段按其返回标签保存，并在策略中仅于该 timestamp 后读取。

AmazingData 文档明确使用前推/开始标签：`09:30 min1` 覆盖 `09:30:00.000~09:30:59.999`，`09:35 min5` 覆盖 `09:35:00.000~09:39:59.999`。下载 adapter 因此把标签转换为完整 bar 首次可用时刻：

```text
min1 09:30 label -> 09:31 available_at
min5 09:35 label -> 09:40 available_at
min30 label       -> label + 30 minutes
```

这样 signal engine 不会在区间尚未结束时读取最终 OHLCV。

文档还说明开盘集合竞价成交量并入第一根分钟 K 线、收盘集合竞价成交量并入最后一根。它表示 K 线“包含竞价影响”，不表示能从 K 线独立拆出竞价价格、成交量或订单不平衡。

## 6. Upsert 与 watermark

- upsert 唯一键 `(security_id, trade_date)`，重跑幂等；
- last-update 返回分钟最大时间戳，不得调用日线 `YYYY-MM-DD` 截断器；
- parent 从最大时间戳所属日期重新下载；
- 当请求 `end_date` 是当天且当前时间早于分钟完成时间，任务应允许写入已有数据，但下一轮仍重放当天；
- 第一轮不在库中保存 completeness 状态，任务日志记录每个 security/day 的 bar count。

Market K-line parent 以 `security_registry` 为唯一 identity 来源：

- 默认显式传 `security_ids` 或 `symbols`，不隐式全市场下载；
- symbol、exchange、asset_type、market 必须和 registry 匹配；
- 每个 security 从 PhoenixA watermark 所在交易日重放并 upsert；
- 只有显式 `all_registered=true` 才扫描对应资产类型的全部 registry；
- 相同 effective start 的证券合并成 child batch，避免逐证券 SDK 往返。

## 7. 查询语义

Workbench 查询 A 股一个交易日时只覆盖实际观察窗口：

```text
start = 2026-07-29T09:15:00+08:00
end   = 2026-07-29T15:00:59.999999+08:00
```

09:15 起点为竞价和实时观察预留；历史分钟 K 线通常从连续竞价后的第一根完整 bar 开始。15:00 后不再扩大到自然日末尾。PhoenixA 保持升序、分页，Artemis client 自动翻页，禁止依赖单页 5000 上限。

## 8. Arrow 缓存

分钟数据按月分区。必须修正：

- period key 使用 `min5`；
- `date` 字符串保留完整 timestamp；
- 切片把 date-only end 扩展为 end-of-day，或统一传 RFC3339；
- 去重键为完整 timestamp；
- 缓存 schema 允许 timestamp string，读取后按绝对时间排序；
- 缓存 identity 必须升级为 `security_id + period + adjust`，不能重新引入 symbol 物理身份。

第一轮若缓存契约无法安全满足分钟时间，可对 replay 设置 `use_cache=false`，优先保证正确性；缓存优化不能阻塞 MVP。

## 9. 数据质量规则

写入前：

- identity、timestamp、OHLC 必填；
- OHLC 有限且关系合法；
- volume/amount 非负；
- timestamp 唯一且严格可排序；
- 同一日不得跨午休生成伪 bar；
- 单日 bar 数异常只告警，不直接失败，因为停牌、临停和源缺失均可能发生。

回放前：

- 至少满足策略 warmup bars；
- 不允许重复时间；
- 所有 bars 属于请求 trade_date；
- 非递增时间、非法价格导致请求 422；
- 缺口和零成交量作为质量 flags/统计返回。

## 10. 多源扩展

动态 bars 表只保存一份 canonical 值，不保存同一 security/time 的多源副本，也不增加 `source` 列。上游来源属于采集任务配置和运行日志，不属于 bar identity：

- 同一个 `(security_id, trade_date)` 后写覆盖前写；
- 生产调度必须为每个 canonical dataset 指定唯一首选源，不能并发混写；
- 切换供应商需要单独的数据核验和受控回填，不通过 bar 表内 source 分支查询；
- BaoStock extension 表只保存 canonical bars 没有的估值/状态扩展字段，不代表 bars 多版本。

## 11. 实时轮询点与分钟 bars 的边界

新浪/腾讯等轮询接口每约 5 秒返回的 latest price 是离散观察点，不是原生 OHLC bar：

- 原始轮询点默认只驻留内存，不写入分钟 bars 表；
- 实时计算直接消费每个 `QuotePoint`，维护有限长度的点序列和增量状态；
- 不把轮询点合成 sampled OHLC，不复用依赖完整 bar 语义的历史策略实现；
- bar 回测用于低成本发现策略假设；进入实时前必须实现和验证显式的 point-native 策略版本；
- 信号和 compact forward outcome 可以持久化；
- 收盘后权威分钟线只用于把实时 signal time/price 投射到图表和做粗粒度审计，不覆盖实时 signal，也不冒充 5 秒 outcome。

point-native 特征可以包括固定秒数/固定点数收益、EWMA、累计量额差分、更新频率、spread、盘口不平衡和 micro-price。每个有效新点到达后即可重算；缺点是轮询没有覆盖的瞬间仍不可见，因此必须记录 gap/stale 质量。

实时 outcome 由后续点流在线更新 MFE/MAE 和 first-touch，因此无需保存全部 5 秒点。若点流中断或进程重启导致窗口不完整，必须标记 incomplete；收盘分钟线不得用来补成同精度 outcome。

供应商接入统一经过 `RealtimeQuoteAdapter -> QuotePoint`。当前新浪实现解析网页实际使用的 `hq.sinajs.cn` GB18030 响应，包括 source time、最新价、累计量额和五档盘口；腾讯与东财必须各自实现、各自保存契约样本测试，禁止假设字段或时间语义相同。轮询响应不是长期历史数据许可，生产使用前必须单独确认授权、限频和稳定性。
