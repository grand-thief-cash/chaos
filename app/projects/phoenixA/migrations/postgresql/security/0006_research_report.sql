-- ──────────────────────────────────────────────────────────
-- research_report_download_record
--
-- Download-state tracker for stock (and, in future, industry) research-report
-- PDFs that artemis downloads from Eastmoney and sinks to MinIO. This table is
-- scoped to the DOWNLOAD TASK ONLY: it tracks enough to drive a full /
-- incremental download lifecycle (what to fetch, where the PDF was stored,
-- download status) plus the few fields the user explicitly asked to record
-- (source, pdf name, the report's subject, which brokerage produced it,
-- report type). It does NOT model research-report business content.
--
-- Unique key: (source, resource_id). resource_id is the source-defined report
-- id (eastmoney infoCode).
-- report_type: stock | industry | other (CHECK-constrained).
-- The report's subject is held in TWO columns:
--   - subject_source_code: the raw subject code from the source (stock→symbol,
--     industry→industry code). ALWAYS populated for stock/industry (CHECK-
--     constrained non-empty for those types). Used for the MinIO object path
--     and as the key for back-filling subject_id.
--   - subject_id: the resolved project surrogate id whose namespace is set by
--     report_type (stock→security_registry.id, industry→taxonomy_category.id).
--     Both are BIGINT. NULLable — NULL when the subject is not yet in the
--     relevant registry. artemis does NOT skip reports whose subject is
--     unregistered: it upserts them with subject_id=NULL (so the list cursor
--     still advances past them and they are tracked). subject_id is NOT
--     auto-back-filled: the list cursor is MAX(publish_date), so older
--     unresolved records are not naturally re-scanned. Back-filling subject_id
--     from subject_source_code requires a separate reconcile/backfill job.
-- status: pending | downloaded | no_pdf | detail_error | pdf_error (CHECK-constrained).
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ods.research_report_download_record (
    id                   BIGSERIAL      PRIMARY KEY,
    source               VARCHAR(32)    NOT NULL,
    resource_id          VARCHAR(64)    NOT NULL,
    report_type          VARCHAR(16)    NOT NULL DEFAULT 'stock',
    subject_id           BIGINT         NULL,
    subject_source_code  VARCHAR(32)    NOT NULL DEFAULT '',
    publish_date         VARCHAR(10)    NOT NULL DEFAULT '',
    title                VARCHAR(512)   NOT NULL DEFAULT '',
    org_name             VARCHAR(128)   NOT NULL DEFAULT '',
    detail_url           VARCHAR(512)   NOT NULL DEFAULT '',
    pdf_url              VARCHAR(512)   NOT NULL DEFAULT '',
    pdf_object_key       VARCHAR(512)   NOT NULL DEFAULT '',
    status               VARCHAR(24)    NOT NULL DEFAULT 'pending',
    last_error           TEXT           NOT NULL DEFAULT '',
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_research_report_download_record UNIQUE (source, resource_id),
    CONSTRAINT chk_rrdlrec_report_type CHECK (report_type IN ('stock','industry','other')),
    CONSTRAINT chk_rrdlrec_status CHECK (status IN ('pending','downloaded','no_pdf','detail_error','pdf_error')),
    CONSTRAINT chk_rrdlrec_subject_source_code CHECK (report_type NOT IN ('stock','industry') OR subject_source_code <> '')
) TABLESPACE warm_storage;

-- subject_id is a logical FK whose target depends on report_type:
--   stock → ods.security_registry.id ; industry → ods.taxonomy_category.id
-- (no real FK constraint, per refactor §6 R9). NULL until resolved from
-- subject_source_code.
CREATE INDEX IF NOT EXISTS idx_rrdlrec_status
    ON ods.research_report_download_record (status) TABLESPACE warm_storage;
CREATE INDEX IF NOT EXISTS idx_rrdlrec_publish_date
    ON ods.research_report_download_record (publish_date) TABLESPACE warm_storage
    WHERE publish_date != '';
CREATE INDEX IF NOT EXISTS idx_rrdlrec_subject_id
    ON ods.research_report_download_record (subject_id) TABLESPACE warm_storage
    WHERE subject_id IS NOT NULL;

COMMENT ON TABLE ods.research_report_download_record IS '研报下载任务状态跟踪表（东方财富）。artemis 从东方财富抓取研报列表，下载 PDF 并入 MinIO；本表只记录下载任务所需的最小元数据 + MinIO 对象键（pdf_object_key）+ 下载状态，不存 PDF 字节，也不建模研报业务内容。report_type 区分 stock/industry/other；主体由 subject_source_code（源原始代码，stock/industry 非空）+ subject_id（解析后的项目代理 ID，命名空间由 report_type 决定）共同表达。未注册主体的研报不跳过（subject_id=NULL，subject_source_code 仍记录），避免游标推进后永久漏抓。subject_id 不会自动补齐——list 游标为 MAX(publish_date)，旧记录不会自然重扫，需单独的 backfill 任务从 subject_source_code 补 resolve。状态机：pending → downloaded | no_pdf | detail_error | pdf_error。';
COMMENT ON COLUMN ods.research_report_download_record.id IS '自增主键。';
COMMENT ON COLUMN ods.research_report_download_record.source IS '数据源标识，eastmoney。';
COMMENT ON COLUMN ods.research_report_download_record.resource_id IS '源定义的研报 ID（东方财富 infoCode）；自然键组成部分。';
COMMENT ON COLUMN ods.research_report_download_record.report_type IS '研报类型：stock（个股）/ industry（产业）/ other。决定 subject_id 的命名空间。';
COMMENT ON COLUMN ods.research_report_download_record.subject_id IS '研报主体 ID；命名空间由 report_type 决定：stock→ods.security_registry.id（security_id），industry→ods.taxonomy_category.id（category_id）。无真实 FK 约束（refactor §6 R9）。由 artemis 从 subject_source_code resolve；未注册时为 NULL。不会自动补齐，需单独 backfill 任务。';
COMMENT ON COLUMN ods.research_report_download_record.subject_source_code IS '源原始主体代码（stock/industry 非空，CHECK 约束）：stock→股票代码（东方财富 stockCode），industry→产业代码。用于 MinIO 对象路径与 subject_id backfill 的 key。';
COMMENT ON COLUMN ods.research_report_download_record.publish_date IS '研报发布日期（YYYY-MM-DD）；用于文件名、列表游标（MAX）与排序。';
COMMENT ON COLUMN ods.research_report_download_record.title IS '研报标题；用于 MinIO 文件名（{date}_{title}.pdf）。';
COMMENT ON COLUMN ods.research_report_download_record.org_name IS '出研报的机构名称（哪家券商）；东方财富 ORGNAME。';
COMMENT ON COLUMN ods.research_report_download_record.detail_url IS '研报详情页 URL；artemis 抓取该页解析 PDF 直链。';
COMMENT ON COLUMN ods.research_report_download_record.pdf_url IS '已下载的 PDF 直链（下载后回填）；空表示尚未下载。';
COMMENT ON COLUMN ods.research_report_download_record.pdf_object_key IS 'MinIO 对象键（下载后回填）；phoenixA 仅存指针，PDF 字节在 MinIO。';
COMMENT ON COLUMN ods.research_report_download_record.status IS '下载状态：pending（待下载）/ downloaded（已下载）/ no_pdf（详情页无 PDF）/ detail_error（详情抓取失败）/ pdf_error（PDF 下载失败）。';
COMMENT ON COLUMN ods.research_report_download_record.last_error IS '最近一次失败原因（status 为 *_error 时填充）。';
COMMENT ON COLUMN ods.research_report_download_record.created_at IS '记录创建时间。';
COMMENT ON COLUMN ods.research_report_download_record.updated_at IS '记录更新时间。';
