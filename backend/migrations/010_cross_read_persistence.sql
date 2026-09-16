-- Migration: persist cross-read testimony-archive passages and mappings
-- Purpose: store oral-historical / testimony-archive cross-reading probes and their relation annotations.

CREATE TABLE IF NOT EXISTS cross_read_passages (
    id SERIAL PRIMARY KEY,
    passage_id VARCHAR(255) NOT NULL UNIQUE,
    passage_text TEXT NOT NULL,
    speaker_or_source VARCHAR(255),
    passage_label VARCHAR(255),
    source_type VARCHAR(64),
    memory_position_note TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cross_read_passages_source_type ON cross_read_passages(source_type);
CREATE INDEX IF NOT EXISTS idx_cross_read_passages_status ON cross_read_passages(status);

DROP TRIGGER IF EXISTS update_cross_read_passages_updated_at ON cross_read_passages;

CREATE TRIGGER update_cross_read_passages_updated_at
    BEFORE UPDATE ON cross_read_passages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS cross_read_mappings (
    id SERIAL PRIMARY KEY,
    mapping_id VARCHAR(255) NOT NULL UNIQUE,
    passage_id VARCHAR(255) NOT NULL REFERENCES cross_read_passages(passage_id) ON DELETE CASCADE,
    query_id VARCHAR(255) REFERENCES query_runs(query_id) ON DELETE SET NULL,
    chunk_id VARCHAR(255),
    document_id VARCHAR(255),
    page_range VARCHAR(255),
    relation_type VARCHAR(64) NOT NULL CHECK (relation_type IN ('supports', 'complicates', 'contradicts', 'no_documentary_trace')),
    confidence_or_status VARCHAR(64),
    reviewer_note TEXT,
    citation_text TEXT,
    provenance_json JSONB,
    source_metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cross_read_mappings_passage_id ON cross_read_mappings(passage_id);
CREATE INDEX IF NOT EXISTS idx_cross_read_mappings_query_id ON cross_read_mappings(query_id);
CREATE INDEX IF NOT EXISTS idx_cross_read_mappings_relation_type ON cross_read_mappings(relation_type);

DROP TRIGGER IF EXISTS update_cross_read_mappings_updated_at ON cross_read_mappings;

CREATE TRIGGER update_cross_read_mappings_updated_at
    BEFORE UPDATE ON cross_read_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();