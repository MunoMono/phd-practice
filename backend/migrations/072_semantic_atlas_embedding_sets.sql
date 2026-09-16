-- Migration: immutable BGE-M3 embedding sets and reproducible Semantic Atlas projections.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_embedding_sets (
    id SERIAL PRIMARY KEY,
    embedding_set_id VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    corpus_release VARCHAR(255) NOT NULL,
    source_scope TEXT NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    model_revision VARCHAR(255) NOT NULL,
    model_checksum_sha256 VARCHAR(64) NOT NULL,
    vector_dimensions INTEGER NOT NULL CHECK (vector_dimensions = 1024),
    normalisation_chunking_version VARCHAR(255) NOT NULL,
    input_manifest_sha256 VARCHAR(64) NOT NULL,
    coverage_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_chunk_embeddings (
    id SERIAL PRIMARY KEY,
    embedding_set_id VARCHAR(255) NOT NULL REFERENCES semantic_embedding_sets(embedding_set_id) ON DELETE RESTRICT,
    chunk_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255) NOT NULL,
    text_fingerprint_sha256 VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL CHECK (status IN ('embedded', 'excluded', 'failed')),
    embedding vector(1024),
    failure_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (embedding_set_id, chunk_id),
    CHECK ((status = 'embedded' AND embedding IS NOT NULL) OR (status <> 'embedded' AND embedding IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_semantic_chunk_embeddings_set_status
    ON semantic_chunk_embeddings(embedding_set_id, status);
CREATE INDEX IF NOT EXISTS idx_semantic_chunk_embeddings_chunk_id
    ON semantic_chunk_embeddings(chunk_id);

CREATE TABLE IF NOT EXISTS semantic_atlas_projections (
    id SERIAL PRIMARY KEY,
    projection_id VARCHAR(255) NOT NULL UNIQUE,
    embedding_set_id VARCHAR(255) NOT NULL REFERENCES semantic_embedding_sets(embedding_set_id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    algorithm VARCHAR(64) NOT NULL,
    library_version VARCHAR(128),
    random_seed INTEGER NOT NULL,
    parameters_json JSONB NOT NULL,
    input_count INTEGER NOT NULL,
    input_ordering_sha256 VARCHAR(64) NOT NULL,
    numerical_tolerance DOUBLE PRECISION NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_atlas_projection_points (
    id SERIAL PRIMARY KEY,
    projection_id VARCHAR(255) NOT NULL REFERENCES semantic_atlas_projections(projection_id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) NOT NULL,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (projection_id, chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_semantic_atlas_projection_points_projection
    ON semantic_atlas_projection_points(projection_id);