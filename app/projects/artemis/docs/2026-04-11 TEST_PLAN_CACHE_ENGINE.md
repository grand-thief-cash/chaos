# Cache Engine Phase 1 — Test Plan

> Date: 2026-04-11
> Target: cache_engine 模块全部组件
> Strategy: 单元测试 + 端到端场景测试

---

## 1. 测试模块划分

| 测试类 | 目标组件 | 用例数 |
|--------|----------|--------|
| TestPartitionResolver | 规则匹配、路径生成、范围查询 | 22 |
| TestArrowStorage | Arrow 读写、原子写入、合并去重、Schema | 16 |
| TestCompactionLock | 读写互斥、超时、并发 | 9 |
| TestCompactionManager | compact_symbol、compact_all | 7 |
| TestCacheEngine | get/put 核心、cache miss、增量写入 | 18 |
| TestCacheEngineEndToEnd | 完整业务场景模拟 | 5 |
| **合计** | | **77** |

---

## 2. TestPartitionResolver (22 cases)

### 2.1 规则匹配 (resolve_rule)

| # | 用例 | 预期 |
|---|------|------|
| 1 | stock + daily → yearly | granularity="yearly" |
| 2 | stock + 1min → monthly | granularity="monthly" |
| 3 | index (any period) → yearly | granularity="yearly" |
| 4 | 未知 asset_type (etf) → fallback | granularity="yearly" |
| 5 | stock + weekly → yearly | granularity="yearly" |
| 6 | 无规则配置 → raise ValueError | ValueError |
| 7 | rule.match 为空 dict → 兜底匹配 | 返回该规则 |

### 2.2 路径生成

| # | 用例 | 预期 |
|---|------|------|
| 8 | resolve_dir 路径结构 | cache_dir/stock/zh_a/daily/hfq/000001 |
| 9 | resolve_base_path yearly (无 month) | 2025.arrow |
| 10 | resolve_base_path monthly (有 month) | 2025_03.arrow |
| 11 | resolve_base_path yearly 忽略 month 参数 | 2025.arrow |
| 12 | resolve_incremental_path 年分区 | 2025.inc.20260413.arrow |
| 13 | resolve_incremental_path 月分区 | 2025_03.inc.20260413.arrow |

### 2.3 范围查询 (resolve_range + enumerate)

| # | 用例 | 预期 |
|---|------|------|
| 14 | 单年范围 → 1 个 base partition | ["2025"] |
| 15 | 跨年范围 (2024-06 ~ 2025-06) → 2 个 base | ["2024","2025"] |
| 16 | 月分区跨 3 个月 → 3 个 partition | ["2024_01","2024_02","2024_03"] |
| 17 | 含增量文件 → resolve 返回 base + delta | base=1, delta=2 |
| 18 | 无文件存在 → 空 resolved 列表 | [] |
| 19 | enumerate yearly 3 年 → 3 partitions | ["2023","2024","2025"] |
| 20 | enumerate monthly 跨年 → 含 2024_12 和 2025_01 | 4 months |
| 21 | yearly partition covers full year | 2025-01-01 ~ 2025-12-31 |
| 22 | monthly partition covers leap Feb | 2024-02-01 ~ 2024-02-29 |

---

## 3. TestArrowStorage (16 cases)

| # | 用例 | 预期 |
|---|------|------|
| 1 | write_df + read_mmap roundtrip | 数据一致 |
| 2 | read 不存在的文件 | 返回 None |
| 3 | file_exists True/False | 正确判断 |
| 4 | delete_file 删除后文件不存在 | 文件消失 |
| 5 | delete 不存在的文件不报错 | 无异常 |
| 6 | scan_incremental_files 找到 .inc.*.arrow | 3 个文件 |
| 7 | scan_incremental_files 目录不存在 | 返回 [] |
| 8 | merge_files base+inc 去重排序 | 合并正确,inc 删除 |
| 9 | merge_files 空 inc list | 返回 base 行数 |
| 10 | merge_files 无文件 | 返回 0 |
| 11 | 原子写入后无 .tmp 残留 | 无 .tmp.arrow |
| 12 | Schema 强制转换: 多余列被丢弃 | 仅 OHLCV 列 |
| 13 | Schema 强制转换: int→float64 类型正确 | 类型匹配 |
| 14 | ensure_dir 创建嵌套目录 | 目录存在 |
| 15 | write_incremental_df 与 write_df 结果一致 | 可读 |
| 16 | 并发写入同一文件不损坏 | 数据完整 |

---

## 4. TestCompactionLock (9 cases)

| # | 用例 | 预期 |
|---|------|------|
| 1 | 多个并发读允许 | acquire_read 均成功 |
| 2 | Compaction 进行中读被阻塞 | 等待 compaction 完成 |
| 3 | 读进行中 Compaction 被阻塞 | 等待读完成 |
| 4 | 读在 Compaction 期间超时 | 返回 False |
| 5 | Compaction 在读期间超时 | 返回 False |
| 6 | is_compacting 属性正确 | True/False |
| 7 | active_reads 属性正确 | 计数准确 |
| 8 | Compaction 之间互斥 | 第二次 acquire 失败 |
| 9 | 最后一个 reader release → 通知等待的 compaction | compaction 开始 |

---

## 5. TestCompactionManager (7 cases)

| # | 用例 | 预期 |
|---|------|------|
| 1 | compact_symbol 目录不存在 | 返回空 result |
| 2 | compact_symbol 有 base+inc | 合并成功, inc 删除 |
| 3 | compact_symbol 无 inc 文件 | 跳过, bases_compacted=0 |
| 4 | compact_symbol 忽略 .tmp 文件 | 跳过 tmp |
| 5 | compact_all 多 symbol | 每个 symbol 合并 |
| 6 | compact_all 空 cache | 返回 [] |
| 7 | compact_symbol 合并后数据无重复 | unique dates |

---

## 6. TestCacheEngine (18 cases)

### 6.1 写入 (put)

| # | 用例 | 预期 |
|---|------|------|
| 1 | put yearly 全年 + get | 数据完整 |
| 2 | put 跨年数据 → 多个 base 文件 | 2 个 .arrow |
| 3 | put 两次同年 → 第二次写 incremental | 1 个 .inc 文件 |
| 4 | put 空 DataFrame → no-op | 无文件 |
| 5 | put monthly 数据 | 正确写入 |

### 6.2 读取 (get)

| # | 用例 | 预期 |
|---|------|------|
| 6 | get 子集日期范围 | 仅返回范围内数据 |
| 7 | cache miss + fetcher → 回源 | fetcher 被调用 |
| 8 | cache miss + 无 fetcher | 返回 None |
| 9 | fetcher 返回空列表 | 返回 None |
| 10 | 二次 get 同范围 → cache hit | fetcher 不被调用 |
| 11 | use_cache=False 跳过缓存 | 直接回源 |
| 12 | use_cache=False 但仍写入缓存 | 后续 get 命中 |
| 13 | get 日期切片精度 | 日期严格在范围内 |

### 6.3 内部方法

| # | 用例 | 预期 |
|---|------|------|
| 14 | _group_by_partition yearly | 按 year 分组 |
| 15 | _group_by_partition monthly | 按 year_month 分组 |
| 16 | _group_by_partition 无 date 列 | [("unknown", df)] |
| 17 | _get_inc_date 从 df 取 max date | YYYYMMDD |
| 18 | access_count 每次 get 递增 | +1 |

---

## 7. TestCacheEngineEndToEnd (5 cases)

| # | 场景 | 验证点 |
|---|------|--------|
| 1 | 完整回测流程 | fetch→cache→re-fetch(hit)→subset |
| 2 | 每日增量更新 | base→inc→compact→get 全量 |
| 3 | 多线程并发读 | 10 线程同时读无异常 |
| 4 | 不同 symbol 数据隔离 | 各 symbol 目录独立 |
| 5 | put→compact→get 跨年完整流程 | 跨年数据正确合并 |

---

## 8. Corner Cases Checklist

- [x] start_date == end_date (单日)
- [x] 空 DataFrame 写入 no-op
- [x] 无 date 列的 DataFrame
- [x] 无匹配规则的 ValueError
- [x] fetcher 返回空
- [x] 文件不存在时的读取
- [x] 增量文件命名 (年分区/月分区)
- [x] 跨年日期范围 resolve
- [x] 闰年 February (2024-02-29)
- [x] CompactionLock 超时
- [x] 并发读写安全性
- [x] .tmp 文件残留不影响正常操作
- [x] OHLCV schema 强制转换 (多余列丢弃, 类型转换)
- [x] 原子写入 (.tmp → rename)
