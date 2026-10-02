BEGIN;

CREATE TABLE IF NOT EXISTS visual_temporal_periods (
    id BIGSERIAL PRIMARY KEY,
    period_id VARCHAR(255) NOT NULL UNIQUE,
    label VARCHAR(255) NOT NULL,
    start_year INTEGER,
    end_year INTEGER,
    authority_source TEXT NOT NULL,
    certainty VARCHAR(32) NOT NULL DEFAULT 'asserted',
    notes TEXT,
    created_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_year IS NULL OR end_year IS NULL OR start_year <= end_year)
);

CREATE INDEX IF NOT EXISTS ix_visual_temporal_periods_bounds ON visual_temporal_periods (start_year, end_year);

COMMIT;
