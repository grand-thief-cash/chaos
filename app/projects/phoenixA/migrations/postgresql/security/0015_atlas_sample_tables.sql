
-- ============================================================
-- Atlas Sample Tables
-- 记录采样任务、分类结果、文档明细
-- ============================================================
CREATE SCHEMA IF NOT EXISTS atlas_kg;

-- 1. 采样任务主表
CREATE TABLE IF NOT EXISTS atlas_kg.sample_run (
    id UUID PRIMARY KEY,
    request_payload JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(request_payload) = 'object'),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'RUNNING', 'FAILED', 'SUCCESS', 'REVIEWED', 'PUBLISHED')),
    cronjob_run_id BIGINT NULL,
    sampled_document_ids TEXT[] NOT NULL DEFAULT '{}',
    current INT NOT NULL DEFAULT 0 CHECK (current >= 0),
    total INT NOT NULL DEFAULT 0 CHECK (total >= 0),
    progress_message TEXT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    error_code TEXT NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sample_run_status ON atlas_kg.sample_run(status);
CREATE INDEX IF NOT EXISTS idx_sample_run_cronjob_id ON atlas_kg.sample_run(cronjob_run_id);

-- 2. 采样分类结果: per-type JSON output
CREATE TABLE IF NOT EXISTS atlas_kg.sample_category_result (
    id UUID PRIMARY KEY,
    sample_run_id UUID NOT NULL REFERENCES atlas_kg.sample_run(id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,
    document_count INT NOT NULL DEFAULT 0 CHECK (document_count >= 0),
    raw_results JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(raw_results) = 'array'),
    field_summary JSONB NULL CHECK (field_summary IS NULL OR jsonb_typeof(field_summary) = 'object'),
    generated_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uidx_sample_category ON atlas_kg.sample_category_result(sample_run_id, report_type);
CREATE INDEX IF NOT EXISTS idx_sample_category_run ON atlas_kg.sample_category_result(sample_run_id);

-- 3. 采样文档明细: 单个文档处理记录,关联 extraction_run
CREATE TABLE IF NOT EXISTS atlas_kg.sample_document_result (
    id UUID PRIMARY KEY,
    sample_run_id UUID NOT NULL REFERENCES atlas_kg.sample_run(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    extraction_run_id UUID NOT NULL REFERENCES atlas_kg.extraction_run(id),
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'FAILED', 'SUCCESS')),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    duration_ms INT NULL CHECK (duration_ms >= 0),
    error_code TEXT NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sample_doc_run ON atlas_kg.sample_document_result(sample_run_id);
CREATE INDEX IF NOT EXISTS idx_sample_doc_document ON atlas_kg.sample_document_result(document_id);
