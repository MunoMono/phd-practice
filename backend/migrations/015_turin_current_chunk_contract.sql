-- Preserve APR alpha rows while enforcing identity and namespace rules for all
-- future Turin chunks. NOT VALID leaves historical orphan rows untouched but
-- PostgreSQL enforces the constraint for every new or updated row.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS page_end INTEGER,
    ADD COLUMN IF NOT EXISTS corpus_version VARCHAR(255),
    ADD COLUMN IF NOT EXISTS ingestion_version VARCHAR(255),
    ADD COLUMN IF NOT EXISTS chunking_version VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_document_chunks_corpus_version
    ON document_chunks(corpus_version)
    WHERE corpus_version IS NOT NULL;

ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_current_document_fk;

ALTER TABLE document_chunks
    ADD CONSTRAINT document_chunks_current_document_fk
    FOREIGN KEY (document_id)
    REFERENCES documents(document_id)
    NOT VALID;

ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_current_version_fields;

ALTER TABLE document_chunks
    ADD CONSTRAINT document_chunks_current_version_fields
    CHECK (
        corpus_version IS NULL
        OR (ingestion_version IS NOT NULL AND chunking_version IS NOT NULL)
    ) NOT VALID;

COMMENT ON CONSTRAINT document_chunks_current_document_fk ON document_chunks IS
    'NOT VALID preserves APR alpha orphan rows but enforces document identity for all future chunk writes.';