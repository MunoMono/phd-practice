-- Migration: record explicit readiness reviews before embedding or projection work begins.

CREATE TABLE IF NOT EXISTS embedding_readiness_reviews (
    id SERIAL PRIMARY KEY,
    review_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL CHECK (status IN ('draft', 'blocked', 'approved')),
    corpus_release VARCHAR(255) NOT NULL,
    source_scope TEXT NOT NULL,
    exclusions TEXT NOT NULL,
    embedding_model VARCHAR(255) NOT NULL,
    model_revision_or_checksum VARCHAR(255) NOT NULL,
    vector_dimensions INTEGER NOT NULL CHECK (vector_dimensions > 0),
    runtime_and_license TEXT NOT NULL,
    normalisation_chunking_version VARCHAR(255) NOT NULL,
    capacity_retention_plan TEXT NOT NULL,
    fts_separation_plan TEXT NOT NULL,
    analytical_question TEXT NOT NULL,
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_embedding_readiness_reviews_status
    ON embedding_readiness_reviews(status);