-- Phase 0 gate for the Feature Platform.
--
-- security_registry.id is referenced as security_id throughout ODS/DWD using
-- logical foreign keys. Once historical feature values are persisted, deleting
-- and rebuilding this registry could silently attach old values to a different
-- instrument. Make the identity contract explicit and enforce it in PostgreSQL.

CREATE OR REPLACE FUNCTION ods.reject_security_registry_delete_or_truncate()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'ods.security_registry rows are permanent; refresh with natural-key upsert and lifecycle status updates';
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_security_registry_no_delete_or_truncate
    ON ods.security_registry;

CREATE TRIGGER trg_security_registry_no_delete_or_truncate
    BEFORE DELETE OR TRUNCATE ON ods.security_registry
    FOR EACH STATEMENT
    EXECUTE FUNCTION ods.reject_security_registry_delete_or_truncate();

CREATE OR REPLACE FUNCTION ods.reject_security_registry_natural_key_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (OLD.exchange, OLD.asset_type, OLD.symbol)
       IS DISTINCT FROM
       (NEW.exchange, NEW.asset_type, NEW.symbol) THEN
        RAISE EXCEPTION
            'ods.security_registry natural key is immutable for security_id %', OLD.id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_security_registry_natural_key_immutable
    ON ods.security_registry;

CREATE TRIGGER trg_security_registry_natural_key_immutable
    BEFORE UPDATE OF exchange, asset_type, symbol ON ods.security_registry
    FOR EACH ROW
    EXECUTE FUNCTION ods.reject_security_registry_natural_key_change();

COMMENT ON COLUMN ods.security_registry.id IS
    '永久、不可回收的证券内部身份；(exchange, asset_type, symbol) 首次注册时分配，后续全量刷新按自然键 upsert 并保留原 ID。';

COMMENT ON TABLE ods.security_registry IS
    '统一证券注册表。security_id 永久稳定；禁止 DELETE/TRUNCATE 和自然键改写。证券生命周期通过 status/list_date/delist_date 更新。';
