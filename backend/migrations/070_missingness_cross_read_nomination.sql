-- Migration: retain the Cross-readings mapping that a researcher nominated for review.

ALTER TABLE missingness_events
    ADD COLUMN IF NOT EXISTS cross_read_mapping_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_missingness_events_cross_read_mapping_id
    ON missingness_events(cross_read_mapping_id);