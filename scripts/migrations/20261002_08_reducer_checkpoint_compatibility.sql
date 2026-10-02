BEGIN;

CREATE TABLE IF NOT EXISTS reducer_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    reducer_id VARCHAR(255) NOT NULL UNIQUE,
    embedding_set_id VARCHAR(255) NOT NULL,
    projection_id VARCHAR(255) NOT NULL,
    dimensions INTEGER NOT NULL,
    serialization_format VARCHAR(64) NOT NULL,
    checksum VARCHAR(128) NOT NULL,
    corpus_snapshot_id VARCHAR(255) NOT NULL,
    compatibility_status VARCHAR(32) NOT NULL DEFAULT 'unreviewed',
    retained_location TEXT NOT NULL,
    created_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (dimensions >= 2),
    CHECK (compatibility_status IN ('unreviewed', 'compatible', 'incompatible'))
);

CREATE TABLE IF NOT EXISTS reducer_compatibility_reviews (
    id BIGSERIAL PRIMARY KEY,
    review_id VARCHAR(255) NOT NULL UNIQUE,
    reducer_id VARCHAR(255) NOT NULL REFERENCES reducer_checkpoints(reducer_id) ON DELETE CASCADE,
    validation_method VARCHAR(255) NOT NULL,
    result VARCHAR(32) NOT NULL,
    reviewer VARCHAR(255) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (result IN ('passed', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_reducer_checkpoints_scope ON reducer_checkpoints (embedding_set_id, projection_id, dimensions, corpus_snapshot_id);
CREATE INDEX IF NOT EXISTS ix_reducer_compatibility_reviews_checkpoint ON reducer_compatibility_reviews (reducer_id, created_at DESC);

COMMIT;
