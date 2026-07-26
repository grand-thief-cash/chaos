-- Extend the shared research-report download tracker for the additional
-- Eastmoney report feeds consumed by artemis.
ALTER TABLE ods.research_report_download_record
    DROP CONSTRAINT IF EXISTS chk_rrdlrec_report_type;

ALTER TABLE ods.research_report_download_record
    ADD CONSTRAINT chk_rrdlrec_report_type
    CHECK (
        report_type IN (
            'stock',
            'industry',
            'macro',
            'new_stock',
            'strategy',
            'morning_report',
            'other'
        )
    );

COMMENT ON COLUMN ods.research_report_download_record.report_type IS
    '研报类型：stock / industry / macro / new_stock / strategy / morning_report / other。用于隔离列表游标、待下载队列和 MinIO 目录。';
