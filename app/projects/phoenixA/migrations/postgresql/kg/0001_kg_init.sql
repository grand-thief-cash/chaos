-- Atlas Knowledge Graph schema tables
-- Managed by phoenixA postgres_gorm component (data source: kg)
-- This migration is idempotent (uses IF NOT EXISTS)

-- Ensure kg schema exists
CREATE SCHEMA IF NOT EXISTS kg;

-- ① 文档元数据
CREATE TABLE IF NOT EXISTS kg.documents (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) UNIQUE NOT NULL,
    title           VARCHAR(512),
    doc_type        VARCHAR(32) NOT NULL,           -- earnings|research|news|announcement
    company         VARCHAR(128),                    -- 主题公司（若有）
    publish_time    TIMESTAMP,                       -- 文档发布时间
    file_path       VARCHAR(1024),                   -- MinIO 对象路径
    content_hash    VARCHAR(64),                     -- 内容哈希（去重用）
    processed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ② 抽取结果（JSONB，可回溯 + 可重跑 + 可调 prompt）
CREATE TABLE IF NOT EXISTS kg.extractions (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) NOT NULL REFERENCES kg.documents(doc_id),
    chunk_index     INT NOT NULL,
    prompt_version  VARCHAR(16) NOT NULL,            -- v5, v6... 追踪 prompt 版本
    llm_model       VARCHAR(64),
    graph_json      JSONB NOT NULL,                  -- 完整的 skill 抽取 JSON 输出
    input_tokens    INT,
    output_tokens   INT,
    cost_usd        DECIMAL(10,6),
    quality_score   FLOAT,                           -- 可选：人工或自动评分
    status          VARCHAR(16) DEFAULT 'completed', -- completed|failed|needs_review
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(doc_id, chunk_index, prompt_version)      -- 同一段不同 prompt 版本可共存
);

CREATE INDEX IF NOT EXISTS idx_extractions_graph_json ON kg.extractions USING GIN (graph_json);
CREATE INDEX IF NOT EXISTS idx_extractions_doc_id ON kg.extractions (doc_id);

-- ③ 图谱写入记录（追踪哪些抽取结果已入图）
CREATE TABLE IF NOT EXISTS kg.graph_ingestions (
    id              BIGSERIAL PRIMARY KEY,
    extraction_id   BIGINT REFERENCES kg.extractions(id),
    nodes_created   INT DEFAULT 0,
    edges_created   INT DEFAULT 0,
    nodes_merged    INT DEFAULT 0,                   -- 合并去重的数量
    ingested_at     TIMESTAMP DEFAULT NOW()
);

-- ④ 每日流水线运行记录
CREATE TABLE IF NOT EXISTS kg.daily_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_date        DATE NOT NULL,
    news_fetched    INT DEFAULT 0,
    news_relevant   INT DEFAULT 0,
    extractions_ok  INT DEFAULT 0,
    extractions_fail INT DEFAULT 0,
    impacts_generated INT DEFAULT 0,
    total_cost_usd  DECIMAL(10,4),
    status          VARCHAR(16),                     -- running|completed|failed
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP
);

-- ⑤ 事件影响日志（推理层输出，持久化用于回溯验证）
CREATE TABLE IF NOT EXISTS kg.impact_logs (
    id              BIGSERIAL PRIMARY KEY,
    event_name      VARCHAR(512),
    event_time      VARCHAR(32),
    source_doc_id   VARCHAR(64),
    impact_json     JSONB NOT NULL,                  -- 完整的影响分析结果
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impact_logs_json ON kg.impact_logs USING GIN (impact_json);
CREATE INDEX IF NOT EXISTS idx_impact_logs_event ON kg.impact_logs (event_name);

