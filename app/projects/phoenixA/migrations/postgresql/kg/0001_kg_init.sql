-- Atlas Knowledge Graph schema tables
-- Managed by phoenixA postgres_gorm component (data source: kg)
-- This migration is idempotent (uses IF NOT EXISTS)
-- Storage tier (see 2026-05-09 STORAGE_TIER_PLANNING.md v2):
--   - kg.documents / kg.events / kg.daily_runs / kg.graph_ingestions -> pg_default
--   - kg.extractions / kg.impact_logs -> warm_storage

-- Ensure kg schema exists
CREATE SCHEMA IF NOT EXISTS kg;

-- ① 文档元数据
CREATE TABLE IF NOT EXISTS kg.documents (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) UNIQUE NOT NULL,
    title           VARCHAR(512),
    doc_type        VARCHAR(32) NOT NULL,            -- earnings|research|industry|news|policy|announcement|manual
    source_type     VARCHAR(16) NOT NULL DEFAULT 'event',  -- graph_building|event_triggering
    company         VARCHAR(128),                    -- 主题公司（若有）
    publish_time    TIMESTAMP,                       -- 文档发布时间
    file_path       VARCHAR(1024),                   -- MinIO 对象路径
    content_hash    VARCHAR(64),                     -- 内容哈希（去重用）
    processed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_kg_documents_doc_type   ON kg.documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_kg_documents_company    ON kg.documents(company);
CREATE INDEX IF NOT EXISTS idx_kg_documents_hash       ON kg.documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_kg_documents_processed  ON kg.documents(processed);

-- ② 抽取结果（JSONB，可回溯 + 可重跑 + 可调 prompt）
CREATE TABLE IF NOT EXISTS kg.extractions (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) NOT NULL REFERENCES kg.documents(doc_id),
    chunk_index     INT NOT NULL,
    prompt_version  VARCHAR(16) NOT NULL,
    llm_model       VARCHAR(64),
    graph_json      JSONB NOT NULL,
    input_tokens    INT,
    output_tokens   INT,
    cost_usd        DECIMAL(10,6),
    quality_score   FLOAT,
    status          VARCHAR(16) DEFAULT 'completed',
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(doc_id, chunk_index, prompt_version)
) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_kg_extractions_graph_json ON kg.extractions USING GIN (graph_json) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_kg_extractions_doc_id ON kg.extractions (doc_id) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_kg_extractions_status ON kg.extractions (status) TABLESPACE warm_storage;

-- ③ 规范化事件表（事件去重核心, Layer 2）
CREATE TABLE IF NOT EXISTS kg.events (
    id                BIGSERIAL PRIMARY KEY,
    event_fingerprint VARCHAR(64) UNIQUE NOT NULL,
    entity_name       VARCHAR(256) NOT NULL,
    event_type        VARCHAR(32) NOT NULL,
    direction         VARCHAR(16),
    time_bucket       VARCHAR(16) NOT NULL,
    description       TEXT,
    severity          VARCHAR(8) DEFAULT 'medium',
    source_doc_ids    TEXT[] NOT NULL DEFAULT '{}',
    source_count      INT DEFAULT 1,
    first_seen_at     TIMESTAMP DEFAULT NOW(),
    last_seen_at      TIMESTAMP DEFAULT NOW(),
    impact_triggered  BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT NOW()
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_kg_events_type        ON kg.events(event_type);
CREATE INDEX IF NOT EXISTS idx_kg_events_entity      ON kg.events(entity_name);
CREATE INDEX IF NOT EXISTS idx_kg_events_first_seen  ON kg.events(first_seen_at);
CREATE INDEX IF NOT EXISTS idx_kg_events_fingerprint ON kg.events(event_fingerprint);

-- ④ 图谱写入记录
CREATE TABLE IF NOT EXISTS kg.graph_ingestions (
    id              BIGSERIAL PRIMARY KEY,
    extraction_id   BIGINT REFERENCES kg.extractions(id),
    nodes_created   INT DEFAULT 0,
    edges_created   INT DEFAULT 0,
    nodes_merged    INT DEFAULT 0,
    ingested_at     TIMESTAMP DEFAULT NOW()
) TABLESPACE pg_default;

-- ⑤ 每日流水线运行记录
CREATE TABLE IF NOT EXISTS kg.daily_runs (
    id                  BIGSERIAL PRIMARY KEY,
    run_date            DATE NOT NULL,
    docs_fetched        INT DEFAULT 0,
    docs_graph_building INT DEFAULT 0,
    docs_event          INT DEFAULT 0,
    events_new          INT DEFAULT 0,
    events_deduped      INT DEFAULT 0,
    extractions_ok      INT DEFAULT 0,
    extractions_fail    INT DEFAULT 0,
    impacts_generated   INT DEFAULT 0,
    total_cost_usd      DECIMAL(10,4),
    status              VARCHAR(16),
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP
) TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_kg_daily_runs_date ON kg.daily_runs(run_date);

-- ⑥ 事件影响日志
CREATE TABLE IF NOT EXISTS kg.impact_logs (
    id              BIGSERIAL PRIMARY KEY,
    event_id        BIGINT REFERENCES kg.events(id),
    event_name      VARCHAR(512),
    event_time      VARCHAR(32),
    source_doc_id   VARCHAR(64),
    impact_json     JSONB NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
 ) TABLESPACE warm_storage;

CREATE INDEX IF NOT EXISTS idx_kg_impact_logs_json     ON kg.impact_logs USING GIN (impact_json) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_kg_impact_logs_event    ON kg.impact_logs (event_name) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_kg_impact_logs_event_id ON kg.impact_logs (event_id) TABLESPACE warm_storage;
