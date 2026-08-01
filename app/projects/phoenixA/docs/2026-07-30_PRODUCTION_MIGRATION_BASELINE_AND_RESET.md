# PhoenixA 生产迁移基线整理与非关键表重建方案

日期：2026-07-30

## 1. 结论

本轮把尚未投入生产使用的表改成“最终形态的干净建表”，不再通过后续
`ALTER TABLE` 修补旧定义。生产库不直接全库重建：

- 永久保留 `ods.security_registry` 及其 ID、序列、数据；
- 永久保留 `ods.research_report_download_record` 及其下载状态、对象键和数据；
- 保留 `ods._migrations`；
- 其余 PhoenixA 表在停写窗口内删除并由整理后的 `0001`～`0010` 重建；
- 服务启动后，再由迁移器正常应用尚未上线的 `0011`～`0014`。

不在本次开发或测试过程中执行生产重建。仓库中的重建脚本需要在维护窗口由
操作者显式输入“数据库名 + RESET_NONCRITICAL”才会运行。

## 2. 2026-07-30 生产只读审计

连接 `config-production.yaml` 指向的 PostgreSQL 后，得到：

| 项目 | 结果 |
|---|---:|
| PostgreSQL | 16.13 |
| TimescaleDB | 2.26.4 |
| `warm_storage` | 存在 |
| 已应用迁移 | `0001`～`0010` |
| `ods.security_registry` | 10,497 行，约 1.9 MB |
| `ods.research_report_download_record` | 31,294 行，约 29 MB |
| `govern.data_dataset_dictionary` | 3 行，可由种子迁移重建 |
| `govern.data_field_dictionary` | 565 行，可由种子迁移重建 |
| `govern.data_enum_dictionary` | 76 行，可由种子迁移重建 |
| 其他 PhoenixA 业务表 | 0 行 |

现有 7 个 hypertable 都没有 chunk，旧的 4 张日线 bars 表也都是空表，因此
把这些空表改为 `security_id` 物理键不需要做线上数据回填。

审计还发现：当前生产库没有任何指向 `ods.security_registry(id)` 的外键。本轮
干净基线为所有证券事实表补上外键；分钟线、日线、公司行为、财务报表、龙虎榜、
股本、特征值、事件、期权标的等都以 `security_id` 或
`underlying_security_id` 为物理身份。

## 3. `research_report_download_record` 为什么不加单一外键

`subject_id` 是有意保留的多态引用：

- `stock`、`new_stock`：引用 `security_registry.id`；
- `industry`：引用行业分类实体；
- `macro`、`strategy`、`morning_report`：通常为空。

因此它不能声明一个始终指向 `security_registry` 的数据库外键。生产审计显示
`stock/new_stock` 已解析的 subject 没有孤儿。这里采用写入边界校验和上线前审计，
而不是复制 symbol，也不是声明错误的单表外键。

## 4. 干净迁移的兼容规则

- `0001_ods.sql` 直接创建最终 `security_id` 版 ODS 表。
- `0006_research_report.sql` 直接包含 `extra` 和最终报告类型约束。
- 已在生产登记的 `0009`、`0010` 保留文件名，但仅作为兼容标记。
- `0012_ods_market_data_foundation.sql` 直接创建最终结构，不再
  `CREATE → ALTER → DROP/RENAME`。
- 日线 bars 的最终结构已经折叠进 `0001`，因此删除尚未上线的 `0015` 补丁。
- 迁移目录内不再存在 `ALTER TABLE` 或 `DROP TABLE`。

`hsgt_daily.symbol` 表示资金流通道名，`option_qvix_daily.symbol` 表示 QVIX
序列名，两者都不是证券身份；它们不应错误引用 registry。
`leading_stock_symbol`、`symbol_snapshot` 和研报 `subject_source_code` 只是来源/审计
快照，不参与主键、关联或查询身份。

## 5. 上线步骤

1. 发布前停止 PhoenixA 和会写入这些表的 Artemis 下载任务。
2. 运行只读审计：

   ```bash
   psql "$DATABASE_URL" -X \
     -f scripts/production/audit_rebuild_scope.sql
   ```

3. 对两张保留表和迁移记录做逻辑备份，并记录行数：

   ```bash
   pg_dump "$DATABASE_URL" --data-only \
     --table=ods.security_registry \
     --table=ods.research_report_download_record \
     --table=ods._migrations \
     --file=phoenixA_preserved_20260730.sql
   ```

4. 不要直接把 `security_dev` 当作空库演练环境。2026-07-30 审计确认该库已有
   财务报表、Feature Run、分钟 bars 等测试数据，重建脚本会按设计拒绝执行。
   应在临时数据库或四个隔离 schema 中完成同一 DDL/保留数据演练；只有在明确
   备份或同意丢弃这些测试数据后，才能对 `security_dev` 做整体重建。
5. 生产维护窗口执行：

   ```bash
   psql "$DATABASE_URL" -X \
     -v confirm_reset=security_prod:RESET_NONCRITICAL \
     -f scripts/production/reset_rebuildable_tables.sql
   ```

6. 启动 PhoenixA。迁移器会保持 `0001`～`0010` 的历史记录，并应用尚未登记的
   `0011`～`0014`。
7. 再跑只读审计，确认：
   - 两张保留表行数不变；
   - 所有证券事实表都有 registry 外键；
   - `_migrations` 已到 `0014`；
   - PhoenixA 健康检查、证券查询、bars 写入/查询通过。
8. 恢复 Artemis 下载任务。日线和分钟线按各自 watermark 增量下载，不做全量
   重复抓取。

## 6. 失败与恢复

重建脚本本身在单个事务中执行：预检发现任何非白名单业务表有数据，或任一 DDL
失败，都会整体回滚。若脚本提交后、服务应用 `0011`～`0014` 时失败，保留的两张
表仍然完整；修复迁移后重启服务即可重试未登记的迁移。

若保留表校验异常，不继续启动写任务，使用第 3 步的逻辑备份恢复，并对比备份前
记录的行数。不要重建 `security_registry`，否则已经发出的 `security_id` 会失去
稳定含义。
