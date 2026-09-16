-- Migration: link missingness events back to query runs
-- Purpose: preserve source interrogation provenance when failed or partial runs become absences events.

ALTER TABLE missingness_events
    ADD COLUMN IF NOT EXISTS query_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_missingness_events_query_id ON missingness_events(query_id);