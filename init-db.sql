-- Initialize pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table for document chunks
CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(500) NOT NULL,
    embedding vector(384),  -- Dimension matches sentence-transformers/all-MiniLM-L6-v2
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS document_embeddings_vector_idx 
ON document_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create sessions table for logging
CREATE TABLE IF NOT EXISTS research_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    query TEXT NOT NULL,
    agent_response TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create experiments table for training tracking
CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    experiment_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(255),
    hyperparameters JSONB,
    metrics JSONB,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for experiments table
CREATE TRIGGER update_experiments_updated_at 
    BEFORE UPDATE ON experiments 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create digital_assets table for S3 asset tracking
CREATE TABLE IF NOT EXISTS digital_assets (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    s3_key VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Temporal Documents Table (1965-1985 PhD research)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) UNIQUE NOT NULL,
    pid VARCHAR(255) NOT NULL,
    authority_id VARCHAR(255),
    authority_data JSONB,
    archive_record_id VARCHAR(255),
    archive_record_pid VARCHAR(255),
    asset_id VARCHAR(255),
    asset_pid VARCHAR(255),
    asset_id_or_asset_pid VARCHAR(255),
    title VARCHAR(500),
    publication_year INTEGER NOT NULL,
    publication_date TIMESTAMP,
    
    -- File info
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),
    s3_key VARCHAR(500),
    source_uri TEXT UNIQUE,
    source_path TEXT,
    file_size_bytes INTEGER,
    checksum_sha256 VARCHAR(64),
    page_count INTEGER,
    ocr_status VARCHAR(64) DEFAULT 'unknown',
    
    -- Extracted content
    extracted_text TEXT,
    has_diagrams INTEGER DEFAULT 0,
    diagram_s3_keys JSONB,
    
    -- Processing metadata
    processed_at TIMESTAMP,
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_error TEXT,
    ingestion_version VARCHAR(255),
    corpus_version VARCHAR(255),
    metadata_source VARCHAR(255),
    use_for_ml INTEGER,
    ml_page_scope TEXT,
    ml_policy_status VARCHAR(64),
    ml_exclusion_reason TEXT,
    
    -- Metadata (renamed column)
    doc_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index on publication year for temporal queries
CREATE INDEX IF NOT EXISTS documents_publication_year_idx 
ON documents(publication_year);

CREATE INDEX IF NOT EXISTS documents_pid_idx
ON documents(pid);

CREATE INDEX IF NOT EXISTS documents_checksum_sha256_idx
ON documents(checksum_sha256);

CREATE INDEX IF NOT EXISTS documents_asset_id_idx
ON documents(asset_id);

CREATE INDEX IF NOT EXISTS documents_asset_pid_idx
ON documents(asset_pid);

CREATE INDEX IF NOT EXISTS documents_asset_identifier_idx
ON documents(asset_id_or_asset_pid);

CREATE INDEX IF NOT EXISTS documents_ml_policy_status_idx
ON documents(ml_policy_status);

-- Document Chunks Table (for embeddings)
CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    
    -- Chunk content
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    chunk_type VARCHAR(50),
    
    -- Temporal context
    publication_year INTEGER NOT NULL,
    
    -- Embeddings (pgvector)
    embedding_vector vector(384),
    embedding_model VARCHAR(100),
    
    -- Analysis results
    key_concepts JSONB,
    drift_score FLOAT,
    
    -- Metadata (renamed column)
    chunk_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for vector similarity search on chunks
CREATE INDEX IF NOT EXISTS document_chunks_vector_idx 
ON document_chunks 
USING ivfflat (embedding_vector vector_cosine_ops)
WITH (lists = 100);

-- Index on publication year
CREATE INDEX IF NOT EXISTS document_chunks_publication_year_idx 
ON document_chunks(publication_year);

-- Index on document_id for joins
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx 
ON document_chunks(document_id);

-- Drift Analysis Table
CREATE TABLE IF NOT EXISTS drift_analyses (
    id SERIAL PRIMARY KEY,
    analysis_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- Time period
    period_start_year INTEGER NOT NULL,
    period_end_year INTEGER NOT NULL,
    
    -- Documents analyzed
    document_count INTEGER,
    document_ids JSONB,
    
    -- Drift metrics
    drift_score FLOAT,
    conceptual_shift JSONB,
    terminology_changes JSONB,
    semantic_distance FLOAT,
    
    -- Analysis method
    analysis_method VARCHAR(100),
    model_used VARCHAR(100),
    
    -- Results
    results JSONB,
    visualization_data JSONB,
    
    -- Metadata (renamed column)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_metadata JSONB
);

-- Trigger for documents table
CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
