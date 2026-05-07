# Ubuntu Server — PostgreSQL 16 + TimescaleDB + PGVector 安装与配置指南

> 基于 `2026-04-29 INFRASTRUCTURE_AND_DATA_ENGINE.md` 中的设计决策。
>
> 目标环境：VM2 数据库虚拟机（48 GB RAM, 2TB NVMe + 8TB SATA SSD）
>
> Ubuntu Server 22.04 / 24.04 LTS

---

## 一、安装 PostgreSQL 16

```bash
# 1. 添加 PostgreSQL 官方 APT 仓库
sudo apt update
sudo apt install -y wget gnupg2 lsb-release

sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# 2. 安装 PostgreSQL 16 + 开发头文件（PGVector 编译需要）
sudo apt install -y postgresql-16 postgresql-server-dev-16

# 3. 验证
sudo systemctl status postgresql
psql --version
# 应输出: psql (PostgreSQL) 16.x
```

---

## 二、安装 TimescaleDB 扩展

```bash
# 1. 添加 TimescaleDB APT 仓库
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -cs) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt update

# 2. 安装 TimescaleDB（对应 PG16 版本）
sudo apt install -y timescaledb-2-postgresql-16

# 3. 运行 TimescaleDB 调优脚本（自动修改 postgresql.conf）
sudo timescaledb-tune --yes

# 4. 重启 PostgreSQL 加载扩展
sudo systemctl restart postgresql
```

---

## 三、安装 PGVector 扩展

```bash
# 1. 安装编译依赖
sudo apt install -y build-essential git

# 2. 克隆 pgvector 源码并编译安装
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# 3. 验证扩展文件存在
ls /usr/share/postgresql/16/extension/vector*
# 应看到 vector.control, vector--*.sql 等文件
```

---

## 四、磁盘挂载（8TB SATA SSD）

> 前提：在 hypervisor（Proxmox/ESXi/libvirt）中将 8TB SATA SSD 作为第二块虚拟磁盘分配给 VM2。

```bash
# 1. 查看磁盘设备
lsblk
# 应看到类似 /dev/sdb（8TB SATA SSD）

# 2. 分区（如果是新盘）
sudo parted /dev/sdb --script mklabel gpt mkpart primary ext4 0% 100%

# 3. 格式化
sudo mkfs.ext4 /dev/sdb1

# 4. 创建挂载点
sudo mkdir -p /sata8t

# 5. 获取 UUID（持久挂载用）
sudo blkid /dev/sdb1
# 记录 UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 6. 配置自动挂载
echo 'UUID=<你的UUID>  /sata8t  ext4  defaults,noatime  0  2' | sudo tee -a /etc/fstab

# 7. 挂载并验证
sudo mount -a
df -h /sata8t
# 应显示 ~8TB 可用空间
```

---

## 五、PostgreSQL 数据目录配置

### 5.1 主数据目录（NVMe，默认位置）

PostgreSQL 16 默认数据目录在 `/var/lib/postgresql/16/main/`，已在 NVMe 上。

如果需要将数据目录移到自定义 NVMe 路径：

```bash
# 仅在需要自定义路径时执行
sudo systemctl stop postgresql

# 移动默认数据目录到自定义位置
sudo rsync -av /var/lib/postgresql/16/main/ /home/machine/pg_data1
sudo chown -R postgres:postgres /home/machine/pg_data1

# 修改 postgresql.conf
sudo sed -i "s|data_directory = .*|data_directory = '/home/machine/pg_data1'|" /etc/postgresql/16/main/postgresql.conf

sudo systemctl start postgresql
```

### 5.2 创建 SATA SSD 上的表空间目录

```bash
# 创建 PostgreSQL 温存储目录
sudo mkdir -p /gw8tvol1/pgdata_warm
sudo chown postgres:postgres /gw8tvol1/pgdata_warm

# 创建备份相关目录
sudo mkdir -p /gw8tvol1/backups/pg_basebackup
sudo mkdir -p /gw8tvol1/backups/pg_wal_archive
sudo mkdir -p /gw8tvol1/backups/neo4j_dump
sudo mkdir -p /gw8tvol1/scripts
sudo chown -R postgres:postgres /gw8tvol1/backups/pg_basebackup
sudo chown -R postgres:postgres /gw8tvol1/backups/pg_wal_archive
```

---

## 六、创建数据库、Schema、扩展

```bash
# 以 postgres 用户连接
sudo -u postgres psql
```

```sql
-- 1. 创建数据库
CREATE DATABASE chaos_db;

-- 2. 连接到 chaos_db
\c chaos_db

-- 3. 创建 atlas 知识图谱 schema
CREATE SCHEMA IF NOT EXISTS kg;

-- 4. 启用扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- 5. 验证扩展
\dx
-- 应看到 timescaledb 和 vector 两个扩展

-- 6. 创建 SATA SSD 上的表空间（分钟线、温存储用）
CREATE TABLESPACE warm_storage LOCATION '/gw8tvol1/pgdata_warm';

-- 7. 验证表空间
\db
-- 应看到 warm_storage 表空间

-- 8. 创建应用用户（phoenixA / atlas 用）
CREATE USER chaos_app WITH PASSWORD '<your_password>';
GRANT ALL PRIVILEGES ON DATABASE chaos_db TO chaos_app;
GRANT ALL PRIVILEGES ON SCHEMA public TO chaos_app;
GRANT ALL PRIVILEGES ON SCHEMA kg TO chaos_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chaos_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA kg GRANT ALL ON TABLES TO chaos_app;

-- 退出
\q
```


```sql
-- 1. 创建 dev 数据库
CREATE DATABASE chaos_dev;

-- 2. 切换
\c chaos_dev

-- 3. schema（和生产对齐）
CREATE SCHEMA IF NOT EXISTS kg;

-- 4. 安装扩展（必须在每个 DB 单独安装）
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

-- 5. 验证
\dx

-- 6. dev 专用用户
CREATE USER chaos_app_dev WITH PASSWORD 'dev_password_here';

-- 7. 数据库权限
GRANT ALL PRIVILEGES ON DATABASE chaos_dev TO chaos_app_dev;

-- 8. schema 权限
GRANT ALL PRIVILEGES ON SCHEMA public TO chaos_app_dev;
GRANT ALL PRIVILEGES ON SCHEMA kg TO chaos_app_dev;

-- 9. 默认权限（避免后续建表权限问题）
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT ALL ON TABLES TO chaos_app_dev;

ALTER DEFAULT PRIVILEGES IN SCHEMA kg
GRANT ALL ON TABLES TO chaos_app_dev;

-- 10. 生产隔离 I/O
CREATE TABLESPACE warm_storage_dev LOCATION '/gw8tvol1/pgdata_warm_dev';
```

---

## 七、PostgreSQL 核心参数调优

```bash
sudo vim /etc/postgresql/16/main/postgresql.conf
```

根据 VM2 48GB RAM 配置：

```ini
# ── 连接 ─────────────────────────────────────────
listen_addresses = '*'                # 允许 VM1 连接
max_connections = 200                 # 多服务共用一个实例
port = 5432

# ── 内存 ─────────────────────────────────────────
shared_buffers = '12GB'               # 48GB RAM 的 25%
effective_cache_size = '36GB'         # 告诉优化器可用内存
work_mem = '256MB'                    # 复杂查询排序/哈希
maintenance_work_mem = '1GB'          # VACUUM / CREATE INDEX
huge_pages = try                      # 大页内存（如果 OS 支持）

# ── WAL & 检查点 ─────────────────────────────────
wal_level = replica                   # 支持 PITR 恢复
archive_mode = on
archive_command = 'cp %p /sata8t/backups/pg_wal_archive/%f'
wal_keep_size = '2GB'
max_wal_size = '4GB'
min_wal_size = '1GB'
checkpoint_completion_target = 0.9

# ── 查询优化 ─────────────────────────────────────
random_page_cost = 1.1                # SSD 优化（NVMe 更快，接近顺序读）
effective_io_concurrency = 200        # NVMe 并发 IO 能力
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_worker_processes = 16             # TimescaleDB 也需要 worker

# ── 日志 ─────────────────────────────────────────
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 500      # 记录超过 500ms 的慢查询
log_statement = 'ddl'                 # 记录 DDL 语句

# ── TimescaleDB ──────────────────────────────────
# timescaledb-tune 已自动配置以下参数，确认一下：
timescaledb.max_background_workers = 8
```

配置 `pg_hba.conf` 允许 VM1 连接：

```bash
sudo vim /etc/postgresql/16/main/pg_hba.conf
```

添加一行（根据你的 VM 网段调整）：

```
# TYPE  DATABASE   USER        ADDRESS         METHOD
host    chaos_db   chaos_app   10.0.0.0/8      scram-sha-256
host    chaos_db   chaos_app   192.168.0.0/16  scram-sha-256
```

重启使配置生效：

```bash
sudo systemctl restart postgresql
```

---

## 八、配置 WAL 归档 & 备份

### 8.1 每周全量备份脚本

```bash
sudo tee /sata8t/scripts/pg_backup_full.sh << 'EOF'
#!/bin/bash
# 每周全量备份（cron @weekly）

BACKUP_DIR="/sata8t/backups/pg_basebackup"
DATE=$(date +%Y%m%d_%H%M%S)

# 全量备份（tar 格式 + gzip 压缩）
pg_basebackup -h localhost -U postgres \
  -D "${BACKUP_DIR}/base_${DATE}" \
  -Ft -z -P

# 保留最近 4 份，删除旧的
cd "${BACKUP_DIR}"
ls -dt base_* | tail -n +5 | xargs rm -rf 2>/dev/null

echo "[$(date)] Full backup completed: base_${DATE}"
EOF

sudo chmod +x /sata8t/scripts/pg_backup_full.sh
```

### 8.2 WAL 归档清理脚本

```bash
sudo tee /sata8t/scripts/pg_wal_cleanup.sh << 'EOF'
#!/bin/bash
# 每日清理 7 天前的 WAL 归档

find /sata8t/backups/pg_wal_archive -type f -mtime +7 -delete
echo "[$(date)] WAL archive cleanup done"
EOF

sudo chmod +x /sata8t/scripts/pg_wal_cleanup.sh
```

### 8.3 注册 Cron 任务

```bash
sudo crontab -u postgres -e
```

添加：

```cron
# 每周日凌晨 3 点全量备份
0 3 * * 0  /sata8t/scripts/pg_backup_full.sh >> /sata8t/backups/backup.log 2>&1

# 每天凌晨 4 点清理旧 WAL
0 4 * * *  /sata8t/scripts/pg_wal_cleanup.sh >> /sata8t/backups/backup.log 2>&1
```

---

## 九、业务表创建

> ⚠️ 业务表的 DDL 不在本安装文档中维护。
>
> 业务表通过各项目的 **migration 文件** 管理，由 phoenixA 的 `postgres_gorm` component 在启动时自动执行。
>
> | Schema | 负责项目 | Migration 路径 |
> |--------|---------|---------------|
> | `kg` | phoenixA（为 atlas 代管） | `app/projects/phoenixA/migrations/postgresql/kg/` |
> | `public` | phoenixA | `app/projects/phoenixA/migrations/postgresql/security/` |
>
> 详见：
> - Atlas KG 表定义 → `app/projects/phoenixA/migrations/postgresql/kg/0001_kg_init.sql`
> - Go Infra Migration 机制 → `app/infra/docs/2026-04-30 HOW_TO_USE.md` 中的 Migration 章节

---

## 十、验证安装

```bash
# 1. 验证 PostgreSQL 运行
sudo systemctl status postgresql

# 2. 验证扩展
sudo -u postgres psql -d chaos_db -c "\dx"
# 应看到: timescaledb, vector

# 3. 验证表空间
sudo -u postgres psql -d chaos_db -c "\db"
# 应看到: warm_storage -> /sata8t/pgdata_warm

# 4. 验证 schema
sudo -u postgres psql -d chaos_db -c "\dn"
# 应看到: kg, public

# 5. 验证 kg 表
sudo -u postgres psql -d chaos_db -c "\dt kg.*"
# 应看到: documents, extractions, graph_ingestions, daily_runs, impact_logs

# 6. 验证 WAL 归档目录
ls /sata8t/backups/pg_wal_archive/
# 启动后应逐渐出现 WAL 文件

# 7. 从 VM1 测试远程连接
psql -h <VM2-IP> -U chaos_app -d chaos_db -c "SELECT 1"
```

---

## 十一、phoenixA config.yaml 新增 PostgreSQL 配置示例

```yaml
# 在 phoenixA config.yaml 中新增（与 mysql_gorm 并存期间）
postgres_gorm:
  enabled: true
  log_level: info
  slow_threshold: 200ms
  data_sources:
    kg:                              # atlas 知识图谱数据域
      host: <VM2-IP>
      port: 5432
      user: chaos_app
      password: <your_password>
      database: chaos_db
      schema: kg                     # 自动 SET search_path TO kg
      max_open_conns: 20
      max_idle_conns: 5
      conn_max_life: 60m
      ping_on_start: true
      skip_default_tx: true          # 读多写少场景提升性能
      enable_timescale: false        # kg schema 不需要 TimescaleDB
      enable_pgvector: true          # KG 需要向量搜索
      migrate_enabled: true
      migrate_dir: ./migrations/kg
```

```yaml
# 未来全量迁移后（Phase B+）替换 mysql_gorm:
postgres_gorm:
  enabled: true
  log_level: info
  slow_threshold: 200ms
  data_sources:
    security:                        # phoenixA 核心数据（原 MySQL）
      host: localhost                # VM2 本机
      port: 5432
      user: chaos_app
      password: <your_password>
      database: chaos_db
      schema: public
      max_open_conns: 50
      max_idle_conns: 10
      conn_max_life: 60m
      ping_on_start: true
      skip_default_tx: true
      enable_timescale: true         # K 线数据用 TimescaleDB
      migrate_enabled: true
      migrate_dir: ./migrations
    kg:
      host: localhost
      port: 5432
      user: chaos_app
      password: <your_password>
      database: chaos_db
      schema: kg
      max_open_conns: 20
      max_idle_conns: 5
      conn_max_life: 60m
      ping_on_start: true
      enable_pgvector: true
      migrate_enabled: true
      migrate_dir: ./migrations/kg
```

---

## 附录：常用管理命令

```bash
# 查看表空间使用
sudo -u postgres psql -d chaos_db -c "SELECT spcname, pg_size_pretty(pg_tablespace_size(spcname)) FROM pg_tablespace;"

# 查看各 schema 大小
sudo -u postgres psql -d chaos_db -c "
  SELECT schemaname, pg_size_pretty(SUM(pg_total_relation_size(schemaname || '.' || tablename)))
  FROM pg_tables WHERE schemaname IN ('public', 'kg')
  GROUP BY schemaname;
"

# 查看 TimescaleDB chunk 分布
sudo -u postgres psql -d chaos_db -c "SELECT * FROM timescaledb_information.chunks ORDER BY range_start DESC LIMIT 20;"

# 手动移动表到其他表空间
# ALTER TABLE bars_stock_zh_a_1min_nf SET TABLESPACE warm_storage;

# 查看活跃连接
sudo -u postgres psql -d chaos_db -c "SELECT datname, usename, client_addr, state FROM pg_stat_activity WHERE datname='chaos_db';"
```

