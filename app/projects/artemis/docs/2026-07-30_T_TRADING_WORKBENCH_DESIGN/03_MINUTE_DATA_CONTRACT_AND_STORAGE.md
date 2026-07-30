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
| security_id | uint64 | API 必填、PhoenixA 解析为 symbol |
| symbol | string | 物理存储键，由 PhoenixA 解析后写入 |
| trade_date | timestamptz | 分钟 bar 时间，Asia/Shanghai offset |
| open/high/low/close | numeric(20,4) | 非空、有限数、`low <= O/C <= high` |
| volume | bigint nullable | 统一为股；BaoStock 已为股 |
| amount | bigint nullable | 统一为人民币元，四舍五入 |
| preclose/pct_chg | nullable | 分钟源缺失时保持 NULL |

## 3. 物理表

第一轮新增：

```sql
ods.bars_stock_zh_a_min5_nf
```

建议结构：

```sql
CREATE TABLE ods.bars_stock_zh_a_min5_nf (
    symbol      VARCHAR(32) NOT NULL,
    trade_date  TIMESTAMPTZ NOT NULL,
    open        NUMERIC(20,4) NOT NULL,
    high        NUMERIC(20,4) NOT NULL,
    low         NUMERIC(20,4) NOT NULL,
    close       NUMERIC(20,4) NOT NULL,
    volume      BIGINT,
    amount      BIGINT,
    preclose    NUMERIC(20,4),
    pct_chg     NUMERIC(10,4),
    PRIMARY KEY (symbol, trade_date)
);
```

转换为 TimescaleDB hypertable，建议 chunk 为 1 个月，并建立：

- `(symbol, trade_date DESC)`；
- `(trade_date DESC)`。

后续周期按相同结构新增表，不在第一轮提前创建无数据表。

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

源时间究竟代表 bar start 或 bar end 必须通过样本与供应商说明确认。第一轮字段按 BaoStock 返回标签保存，并在策略中仅于该 timestamp 后读取；AmazingData 接入时按其“前推算法”单独映射 `available_at`。

## 6. Upsert 与 watermark

- upsert 唯一键 `(symbol, trade_date)`，重跑幂等；
- last-update 返回分钟最大时间戳，不得调用日线 `YYYY-MM-DD` 截断器；
- parent 从最大时间戳所属日期重新下载；
- 当请求 `end_date` 是当天且当前时间早于 BaoStock 分钟完成时间，任务应允许写入已有数据，但下一轮仍重放当天；
- 第一轮不在库中保存 completeness 状态，任务日志记录每个 symbol/day 的 bar count。

## 7. 查询语义

Workbench 查询一个交易日时转换为：

```text
start = 2026-07-29T00:00:00+08:00
end   = 2026-07-29T23:59:59.999999+08:00
```

PhoenixA 保持升序、分页。Artemis client 自动翻页，禁止依赖单页 5000 上限。

## 8. Arrow 缓存

分钟数据按月分区。必须修正：

- period key 使用 `min5`；
- `date` 字符串保留完整 timestamp；
- 切片把 date-only end 扩展为 end-of-day，或统一传 RFC3339；
- 去重键为完整 timestamp；
- 缓存 schema 允许 timestamp string，读取后按绝对时间排序。

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

当前动态 bars 表保存 canonical 值，不并行保留多个 source 版本。后续接入 AmazingData 时建议增加 raw/source staging 或 observation provenance：

```text
source
source_revision
received_at
available_at
quality_flags
```

在此之前，批量报告必须记录运行所选的 source，避免不同供应商数据混合后无法解释结果差异。
