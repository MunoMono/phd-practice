-- Migration: lightweight FTS retrieval and resumable ingestion state
-- Purpose: reduce runtime memory by replacing embedding-first retrieval with PostgreSQL FTS.

-- Keep pgvector installed for compatibility, but runtime retrieval uses FTS.
CREATE EXTENSION IF NOT EXISTS vector;

-- Add tsvector column for chunk text search.
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS search_tsv tsvector;

-- Backfill existing chunks.
UPDATE document_chunks
SET search_tsv = to_tsvector('english', COALESCE(chunk_text, ''))
WHERE search_tsv IS NULL;

-- Index for FTS.
CREATE INDEX IF NOT EXISTS idx_document_chunks_search_tsv
ON document_chunks USING GIN (search_tsv);

-- Keep search_tsv in sync on write.
CREATE OR REPLACE FUNCTION document_chunks_tsvector_update()
RETURNS trigger AS $$
BEGIN
    NEW.search_tsv := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_document_chunks_tsvector_update ON document_chunks;

CREATE TRIGGER trg_document_chunks_tsvector_update
BEFORE INSERT OR UPDATE OF chunk_text
ON document_chunks
FOR EACH ROW
EXECUTE FUNCTION document_chunks_tsvector_update();

-- Resumable ingestion state table.
CREATE TABLE IF NOT EXISTS ingestion_state (
    id SERIAL PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    last_error TEXT,
    retries INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_state_status
ON ingestion_state(status);
