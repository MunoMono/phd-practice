-- Migration: ML Enrichment Schema for RCA PhD Legacy
-- Adds comprehensive ML processing capabilities with pgvector semantic search
-- Supports embeddings, entity extraction, theme analysis, and temporal tracking

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Add ML enrichment columns to documents
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS embeddings vector(1536),      -- OpenAI/Granite embeddings
ADD COLUMN IF NOT EXISTS ml_entities JSONB,            -- Named entities, people, places, concepts
ADD COLUMN IF NOT EXISTS ml_summary TEXT,              -- AI-generated summary
ADD COLUMN IF NOT EXISTS ml_themes TEXT[],             -- Extracted themes/topics
ADD COLUMN IF NOT EXISTS ml_keywords TEXT[],           -- Key terms for search
ADD COLUMN IF NOT EXISTS ml_confidence FLOAT,          -- Processing confidence score
ADD COLUMN IF NOT EXISTS ml_processed_at TIMESTAMP,    -- When ML processing completed
ADD COLUMN IF NOT EXISTS ml_model_version VARCHAR(100), -- Model used for processing
ADD COLUMN IF NOT EXISTS ml_processing_time_seconds INTEGER, -- Performance tracking
ADD COLUMN IF NOT EXISTS ocr_text TEXT,                -- Full OCR extracted text
ADD COLUMN IF NOT EXISTS page_count INTEGER;           -- Number of pages in PDF

-- Indexes for high-performance queries
CREATE INDEX IF NOT EXISTS idx_documents_embeddings 
ON documents USING ivfflat (embeddings vector_cosine_ops) 
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_documents_ml_entities 
ON documents USING GIN (ml_entities);

CREATE INDEX IF NOT EXISTS idx_documents_ml_themes 
ON documents USING GIN (ml_themes);

CREATE INDEX IF NOT EXISTS idx_documents_ml_keywords 
ON documents USING GIN (ml_keywords);

CREATE INDEX IF NOT EXISTS idx_documents_ml_processed_at 
ON documents(ml_processed_at DESC);

-- ML processing log table for tracking pipeline execution
CREATE TABLE IF NOT EXISTS ml_processing_log (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) REFERENCES documents(document_id),
    pid VARCHAR(255),
    
    -- Processing stages
    stage VARCHAR(50) NOT NULL, -- 'download', 'ocr', 'embedding', 'entity_extraction', 'summarization'
    status VARCHAR(50) NOT NULL, -- 'started', 'completed', 'failed', 'skipped'
    
    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Results
    output_data JSONB,
    error_message TEXT,
    
    -- Metadata
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_processing_log_document 
ON ml_processing_log(document_id);

CREATE INDEX IF NOT EXISTS idx_ml_processing_log_stage_status 
ON ml_processing_log(stage, status);

-- Entity reference table for network analysis
CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    entity_text VARCHAR(500) NOT NULL,
    entity_type VARCHAR(100), -- 'PERSON', 'ORG', 'CONCEPT', 'METHOD', 'LOCATION'
    canonical_form VARCHAR(500), -- Normalized version
    frequency INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(entity_text, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_frequency ON entities(frequency DESC);

-- Document-Entity relationship table for network graphs
CREATE TABLE IF NOT EXISTS document_entities (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) REFERENCES documents(document_id),
    entity_id INTEGER REFERENCES entities(id),
    
    -- Context
    occurrences INTEGER DEFAULT 1,
    pages INTEGER[], -- Pages where entity appears
    confidence FLOAT,
    context_snippets TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(document_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_document_entities_document 
ON document_entities(document_id);

CREATE INDEX IF NOT EXISTS idx_document_entities_entity 
ON document_entities(entity_id);

-- Theme clustering table for visualization
CREATE TABLE IF NOT EXISTS theme_clusters (
    id SERIAL PRIMARY KEY,
    theme_name VARCHAR(255) UNIQUE NOT NULL,
    parent_theme VARCHAR(255),
    description TEXT,
    color_hex VARCHAR(7), -- For consistent visualization colors
    icon_name VARCHAR(100),
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document similarity matrix for network graphs
CREATE TABLE IF NOT EXISTS document_similarities (
    id SERIAL PRIMARY KEY,
    document_id_a VARCHAR(255) REFERENCES documents(document_id),
    document_id_b VARCHAR(255) REFERENCES documents(document_id),
    
    -- Similarity scores
    embedding_similarity FLOAT, -- Cosine similarity from embeddings
    entity_overlap FLOAT,       -- Jaccard similarity of entities
    theme_overlap FLOAT,        -- Jaccard similarity of themes
    combined_score FLOAT,       -- Weighted combination
    
    computed_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(document_id_a, document_id_b),
    CHECK (document_id_a < document_id_b) -- Avoid duplicates
);

CREATE INDEX IF NOT EXISTS idx_document_similarities_score 
ON document_similarities(combined_score DESC);

-- Temporal trends table for time-series analysis
CREATE TABLE IF NOT EXISTS temporal_trends (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    
    -- Metrics
    documents_published INTEGER DEFAULT 0,
    themes JSONB, -- {"design_methods": 5, "innovation": 3}
    entities JSONB,
    avg_pdf_count FLOAT,
    
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(year, month)
);

CREATE INDEX IF NOT EXISTS idx_temporal_trends_year ON temporal_trends(year);

-- Materialized view for fast dashboard queries
CREATE MATERIALIZED VIEW IF NOT EXISTS ml_dashboard_stats AS
SELECT 
    COUNT(*) as total_documents,
    COUNT(*) FILTER (WHERE embeddings IS NOT NULL) as documents_with_embeddings,
    COUNT(*) FILTER (WHERE ml_summary IS NOT NULL) as documents_with_summaries,
    COUNT(*) FILTER (WHERE ml_entities IS NOT NULL) as documents_with_entities,
    AVG(ml_confidence) as avg_confidence,
    AVG(ml_processing_time_seconds) as avg_processing_time,
    SUM(pdf_count) as total_pdfs,
    SUM(page_count) as total_pages,
    MIN(publication_year) as earliest_year,
    MAX(publication_year) as latest_year,
    COUNT(DISTINCT unnest(ml_themes)) as unique_themes,
    NOW() as last_updated
FROM documents
WHERE pid IS NOT NULL;

CREATE UNIQUE INDEX ON ml_dashboard_stats (last_updated);

-- Function to refresh dashboard stats
CREATE OR REPLACE FUNCTION refresh_ml_dashboard_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ml_dashboard_stats;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate document similarity
CREATE OR REPLACE FUNCTION calculate_document_similarity(doc_a VARCHAR, doc_b VARCHAR)
RETURNS FLOAT AS $$
DECLARE
    similarity FLOAT;
BEGIN
    SELECT 1 - (a.embeddings <=> b.embeddings)
    INTO similarity
    FROM documents a, documents b
    WHERE a.document_id = doc_a 
      AND b.document_id = doc_b
      AND a.embeddings IS NOT NULL 
      AND b.embeddings IS NOT NULL;
    
    RETURN COALESCE(similarity, 0.0);
END;
$$ LANGUAGE plpgsql;

-- Function to find similar documents using pgvector
CREATE OR REPLACE FUNCTION find_similar_documents(
    target_doc_id VARCHAR,
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE(
    document_id VARCHAR,
    title VARCHAR,
    similarity FLOAT,
    shared_themes TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.document_id,
        d.title,
        1 - (t.embeddings <=> d.embeddings) as similarity,
        ARRAY(SELECT unnest(t.ml_themes) INTERSECT SELECT unnest(d.ml_themes)) as shared_themes
    FROM documents t, documents d
    WHERE t.document_id = target_doc_id
      AND d.document_id != target_doc_id
      AND t.embeddings IS NOT NULL
      AND d.embeddings IS NOT NULL
      AND 1 - (t.embeddings <=> d.embeddings) > similarity_threshold
    ORDER BY t.embeddings <=> d.embeddings
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE documents IS 'Enhanced with ML enrichment capabilities for RCA PhD research corpus';
COMMENT ON COLUMN documents.embeddings IS 'Vector embeddings for semantic similarity search';
COMMENT ON COLUMN documents.ml_entities IS 'Extracted named entities (people, orgs, concepts)';
COMMENT ON COLUMN documents.ml_themes IS 'AI-identified themes and topics';
COMMENT ON TABLE ml_processing_log IS 'Audit trail for ML pipeline execution';
COMMENT ON TABLE document_similarities IS 'Precomputed similarity matrix for network visualization';
