-- Phase 2A: corpus identity and provenance foundation.
-- Purpose: model archive PDFs as distinct source documents even when multiple
-- PDFs share the same archive/media PID.

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS archive_record_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS archive_record_pid VARCHAR(255),
ADD COLUMN IF NOT EXISTS source_uri TEXT,
ADD COLUMN IF NOT EXISTS source_path TEXT,
ADD COLUMN IF NOT EXISTS checksum_sha256 VARCHAR(64),
ADD COLUMN IF NOT EXISTS page_count INTEGER,
ADD COLUMN IF NOT EXISTS ocr_status VARCHAR(64) DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS ingestion_version VARCHAR(255),
ADD COLUMN IF NOT EXISTS corpus_version VARCHAR(255),
ADD COLUMN IF NOT EXISTS metadata_source VARCHAR(255);

ALTER TABLE documents
ALTER COLUMN pid SET NOT NULL;

ALTER TABLE documents
DROP CONSTRAINT IF EXISTS unique_document_pid;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_uri_unique
ON documents(source_uri)
WHERE source_uri IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_archive_record_id
ON documents(archive_record_id);

CREATE INDEX IF NOT EXISTS idx_documents_archive_record_pid
ON documents(archive_record_pid);

CREATE INDEX IF NOT EXISTS idx_documents_checksum_sha256
ON documents(checksum_sha256);

CREATE INDEX IF NOT EXISTS idx_documents_ingestion_version
ON documents(ingestion_version);

CREATE INDEX IF NOT EXISTS idx_documents_corpus_version
ON documents(corpus_version);

COMMENT ON COLUMN documents.pid IS 'Archive media/item PID used as the stable archive identifier for a source PDF. Multiple source PDFs may share the same PID.';
COMMENT ON COLUMN documents.archive_record_pid IS 'Parent archive record PID when the source PDF is attached to a higher-level record.';
COMMENT ON COLUMN documents.source_uri IS 'Authoritative source location for the master PDF, typically a public archive-media URL.';
COMMENT ON COLUMN documents.checksum_sha256 IS 'SHA-256 checksum of the source PDF bytes used for local provenance validation.';
COMMENT ON COLUMN documents.ingestion_version IS 'Version label for the ingestion/inventory implementation or configuration.';
COMMENT ON COLUMN documents.corpus_version IS 'Deterministic version identifier for the bounded corpus membership used by an experiment.';
COMMENT ON COLUMN documents.metadata_source IS 'Archive metadata source used to populate this document, e.g. archive_graphql.records_v1.';