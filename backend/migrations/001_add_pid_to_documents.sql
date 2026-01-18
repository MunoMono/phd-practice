-- Migration: Add PID and authority linkage to documents table
-- This enforces the allowlist filter for training corpus

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Add PID columns to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS pid VARCHAR(255),
ADD COLUMN IF NOT EXISTS authority_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS authority_data JSONB;

-- Create indexes for efficient PID filtering
CREATE INDEX IF NOT EXISTS idx_documents_pid ON documents(pid);
CREATE INDEX IF NOT EXISTS idx_documents_authority_id ON documents(authority_id);

-- Add unique constraint on PID (each PID can only have one document)
ALTER TABLE documents
ADD CONSTRAINT unique_document_pid UNIQUE (pid);

-- Create vector index on document_chunks for similarity search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_vector_idx 
ON document_chunks 
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);

-- Index for temporal queries (epistemic drift analysis)
CREATE INDEX IF NOT EXISTS idx_document_chunks_publication_year 
ON document_chunks(publication_year);

-- Add provenance columns to document_chunks
ALTER TABLE document_chunks
ADD COLUMN IF NOT EXISTS source_page INTEGER,
ADD COLUMN IF NOT EXISTS source_section VARCHAR(500),
ADD COLUMN IF NOT EXISTS extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS citation JSONB;

-- Create training_runs table for model provenance
CREATE TABLE IF NOT EXISTS training_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100),
    base_model VARCHAR(255),
    training_date TIMESTAMP NOT NULL,
    training_duration_seconds INTEGER,
    chunk_ids_used JSONB,
    total_chunks INTEGER,
    pid_distribution JSONB,
    temporal_distribution JSONB,
    corpus_snapshot_id VARCHAR(255),
    model_checkpoint_s3 VARCHAR(500),
    hyperparameters JSONB,
    embedding_model_version VARCHAR(100),
    framework_versions JSONB,
    final_loss FLOAT,
    metrics JSONB,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_training_runs_run_id ON training_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_training_runs_snapshot ON training_runs(corpus_snapshot_id);

-- Create inference_logs table for XAI
CREATE TABLE IF NOT EXISTS inference_logs (
    id SERIAL PRIMARY KEY,
    inference_id VARCHAR(255) UNIQUE NOT NULL,
    query TEXT NOT NULL,
    query_embedding vector(384),
    prediction TEXT,
    model_version VARCHAR(255) NOT NULL,
    training_run_id VARCHAR(255),
    top_k_chunks JSONB,
    source_pids JSONB,
    source_years JSONB,
    confidence_score FLOAT,
    inference_time_ms INTEGER,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inference_logs_inference_id ON inference_logs(inference_id);
CREATE INDEX IF NOT EXISTS idx_inference_logs_model_version ON inference_logs(model_version);
CREATE INDEX IF NOT EXISTS idx_inference_logs_training_run ON inference_logs(training_run_id);
CREATE INDEX IF NOT EXISTS idx_inference_logs_session ON inference_logs(session_id);

-- Create corpus_snapshots table for versioning
CREATE TABLE IF NOT EXISTS corpus_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_id VARCHAR(255) UNIQUE NOT NULL,
    snapshot_date TIMESTAMP NOT NULL,
    name VARCHAR(255),
    description TEXT,
    total_documents INTEGER,
    total_chunks INTEGER,
    pid_list JSONB,
    chunk_manifest_s3 VARCHAR(500),
    year_range_start INTEGER,
    year_range_end INTEGER,
    year_distribution JSONB,
    changes_since_last JSONB,
    manifest_checksum VARCHAR(64),
    statistics JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_corpus_snapshots_snapshot_id ON corpus_snapshots(snapshot_id);

-- Add comment explaining the PID requirement
COMMENT ON COLUMN documents.pid IS 'Postgres authority PID - REQUIRED for training corpus eligibility. Only PID-linked assets are used for Grantie model training.';
COMMENT ON COLUMN documents.authority_id IS 'DDR Archive authority ID - links to GraphQL metadata';
COMMENT ON COLUMN documents.authority_data IS 'Cached authority metadata from DDR Archive GraphQL (captions, descriptive data)';
COMMENT ON COLUMN document_chunks.embedding_vector IS 'pgvector embedding (384-dim) for semantic similarity search and drift analysis';

-- Query to identify orphaned documents (no PID - not eligible for training)
-- SELECT document_id, filename, publication_year 
-- FROM documents 
-- WHERE pid IS NULL;

-- Query to get training corpus statistics
-- SELECT 
--   COUNT(*) as total_documents,
--   COUNT(pid) as documents_with_pid,
--   COUNT(*) - COUNT(pid) as orphaned_documents,
--   ROUND(COUNT(pid)::numeric / COUNT(*)::numeric * 100, 2) as pid_coverage_percent
-- FROM documents;
