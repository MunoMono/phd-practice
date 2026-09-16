-- Migration: persist source interrogation retrieval trails
-- Purpose: store auditable query runs, retrieved chunks, and export records.

CREATE TABLE IF NOT EXISTS query_runs (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL UNIQUE,
    prompt TEXT NOT NULL,
    mode VARCHAR(64),
    model VARCHAR(255),
    response TEXT,
    caveats TEXT,
    failed_or_partial BOOLEAN NOT NULL DEFAULT FALSE,
    failure_reason TEXT,
    retrieved_chunk_count INTEGER NOT NULL DEFAULT 0,
    export_status VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_runs_created_at ON query_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_runs_failed_or_partial ON query_runs(failed_or_partial);

DROP TRIGGER IF EXISTS update_query_runs_updated_at ON query_runs;

CREATE TRIGGER update_query_runs_updated_at
    BEFORE UPDATE ON query_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS query_run_chunks (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL REFERENCES query_runs(query_id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255),
    page_range VARCHAR(255),
    rank INTEGER,
    score DOUBLE PRECISION,
    citation_text TEXT,
    provenance_json JSONB,
    source_metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_run_chunks_query_id ON query_run_chunks(query_id);
CREATE INDEX IF NOT EXISTS idx_query_run_chunks_chunk_id ON query_run_chunks(chunk_id);

CREATE TABLE IF NOT EXISTS query_run_exports (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(255) NOT NULL REFERENCES query_runs(query_id) ON DELETE CASCADE,
    export_type VARCHAR(32) NOT NULL CHECK (export_type IN ('json', 'markdown')),
    export_payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_run_exports_query_id ON query_run_exports(query_id);
CREATE INDEX IF NOT EXISTS idx_query_run_exports_export_type ON query_run_exports(export_type);