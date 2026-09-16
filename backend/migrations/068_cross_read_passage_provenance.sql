-- Migration: add source provenance and access state to cross-read passages.
-- Purpose: distinguish attributable testimony from researcher-authored interpretive drafts.

ALTER TABLE cross_read_passages
    ADD COLUMN IF NOT EXISTS source_reference TEXT,
    ADD COLUMN IF NOT EXISTS source_date VARCHAR(64),
    ADD COLUMN IF NOT EXISTS access_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
    ADD COLUMN IF NOT EXISTS ingestion_method VARCHAR(32) NOT NULL DEFAULT 'researcher_entered';

ALTER TABLE cross_read_passages
    DROP CONSTRAINT IF EXISTS cross_read_passages_access_status_check,
    ADD CONSTRAINT cross_read_passages_access_status_check
        CHECK (access_status IN ('open', 'restricted', 'unknown')),
    DROP CONSTRAINT IF EXISTS cross_read_passages_ingestion_method_check,
    ADD CONSTRAINT cross_read_passages_ingestion_method_check
        CHECK (ingestion_method IN ('researcher_entered', 'imported'));

CREATE INDEX IF NOT EXISTS idx_cross_read_passages_access_status
    ON cross_read_passages(access_status);