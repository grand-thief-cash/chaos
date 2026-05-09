-- ============================================================
-- PhoenixA PostgreSQL Migration 0003: trade_date DATE type
-- Scope: industry_weight, industry_daily
-- Changes: trade_date VARCHAR(10) → DATE
-- Storage tier: recreated indexes stay on warm_storage
-- ============================================================

-- Drop dependent indexes and constraints first
DROP INDEX IF EXISTS idx_iw_index_date;
DROP INDEX IF EXISTS idx_iw_symbol_date;
ALTER TABLE industry_weight DROP CONSTRAINT IF EXISTS uk_src_tax_idx_sym_dt;

DROP INDEX IF EXISTS idx_id_index_date;
DROP INDEX IF EXISTS idx_id_trade_date;
ALTER TABLE industry_daily DROP CONSTRAINT IF EXISTS uk_src_tax_idx_mkt_dt;

-- Convert trade_date columns
ALTER TABLE industry_weight ALTER COLUMN trade_date TYPE DATE USING to_date(trade_date, 'YYYY-MM-DD');
ALTER TABLE industry_weight ALTER COLUMN trade_date SET NOT NULL;

ALTER TABLE industry_daily ALTER COLUMN trade_date TYPE DATE USING to_date(trade_date, 'YYYY-MM-DD');
ALTER TABLE industry_daily ALTER COLUMN trade_date SET NOT NULL;

-- Recreate unique constraints
ALTER TABLE industry_weight ADD CONSTRAINT uk_src_tax_idx_sym_dt UNIQUE (source, taxonomy, index_code, symbol, market, trade_date);
ALTER TABLE industry_daily ADD CONSTRAINT uk_src_tax_idx_mkt_dt UNIQUE (source, taxonomy, index_code, market, trade_date);

-- Recreate indexes
CREATE INDEX idx_iw_index_date ON industry_weight (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX idx_iw_symbol_date ON industry_weight (symbol, market, trade_date) TABLESPACE warm_storage;
CREATE INDEX idx_id_index_date ON industry_daily (source, taxonomy, index_code, trade_date) TABLESPACE warm_storage;
CREATE INDEX idx_id_trade_date ON industry_daily (source, taxonomy, trade_date) TABLESPACE warm_storage;
