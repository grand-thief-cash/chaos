-- Atlas Knowledge Graph — Initial PostgreSQL Schema
-- Version: 001
-- Date: 2026-04-29

-- ① 文档元数据
CREATE TABLE IF NOT EXISTS documents (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       VARCHAR(64) UNIQUE NOT NULL,
    title        VARCHAR(512),
    doc_type     VARCHAR(32) NOT NULL,            -- earnings|research|news|announcement
    company      VARCHAR(128),                     -- 主题公司（若有）
    publish_time TIMESTAMP,
    file_path    VARCHAR(1024),
    content_hash VARCHAR(64),                      -- SHA256，用于去重
    processed    BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_doc_type   ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_company    ON documents(company);
CREATE INDEX IF NOT EXISTS idx_documents_hash       ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_processed  ON documents(processed);

-- ② 抽取结果（核心：可回溯 + 可重跑 + prompt 版本管理）
CREATE TABLE IF NOT EXISTS extractions (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          VARCHAR(64) NOT NULL REFERENCES documents(doc_id),
    chunk_index     INT NOT NULL,
    prompt_version  VARCHAR(16) NOT NULL,          -- v5, v6... 追踪 prompt 版本
    llm_model       VARCHAR(64),
    graph_json      JSONB NOT NULL,                -- 完整的 skill 输出 JSON
    input_tokens    INT,
    output_tokens   INT,
    cost_usd        DECIMAL(10,6),
    quality_score   FLOAT,                         -- 人工或自动评分
    status          VARCHAR(16) DEFAULT 'completed', -- completed|failed|needs_review
    created_at      TIMESTAMP DEFAULT NOW(),

    UNIQUE(doc_id, chunk_index, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_extractions_doc_id   ON extractions(doc_id);
CREATE INDEX IF NOT EXISTS idx_extractions_status   ON extractions(status);
-- GIN 索引：支持在 graph_json 中按公司名/事件名检索
CREATE INDEX IF NOT EXISTS idx_extractions_json     ON extractions USING GIN (graph_json);

-- ③ 图谱写入记录（追踪哪些 extraction 已入图）
CREATE TABLE IF NOT EXISTS graph_ingestions (
    id              BIGSERIAL PRIMARY KEY,
    extraction_id   BIGINT REFERENCES extractions(id),
    nodes_created   INT DEFAULT 0,
    edges_created   INT DEFAULT 0,
    nodes_merged    INT DEFAULT 0,
    ingested_at     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graph_ingestions_ext ON graph_ingestions(extraction_id);

-- ④ 每日流水线运行记录
CREATE TABLE IF NOT EXISTS daily_runs (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    news_fetched     INT DEFAULT 0,
    news_relevant    INT DEFAULT 0,
    extractions_ok   INT DEFAULT 0,
    extractions_fail INT DEFAULT 0,
    impacts_generated INT DEFAULT 0,
    total_cost_usd   DECIMAL(10,4),
    status           VARCHAR(16),                  -- running|completed|failed
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_runs_date ON daily_runs(run_date);

-- ⑤ 事件影响日志（Impact Engine 输出，持久化用于回溯验证）
CREATE TABLE IF NOT EXISTS impact_logs (
    id              BIGSERIAL PRIMARY KEY,
    event_name      VARCHAR(512),
    event_time      VARCHAR(32),
    source_doc_id   VARCHAR(64),
    impact_json     JSONB NOT NULL,                -- 完整影响分析结果
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impact_logs_event   ON impact_logs(event_name);
CREATE INDEX IF NOT EXISTS idx_impact_logs_time    ON impact_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_impact_logs_json    ON impact_logs USING GIN (impact_json);

