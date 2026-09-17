-- Append-only, hash-linked event trail for research-output provenance.

ALTER TABLE missingness_events
    ADD COLUMN IF NOT EXISTS auto_generated BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_missingness_events_auto_generated ON missingness_events(auto_generated);

CREATE TABLE IF NOT EXISTS provenance_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(128) NOT NULL,
    subject_type VARCHAR(64) NOT NULL,
    subject_id VARCHAR(255) NOT NULL,
    actor VARCHAR(255) NOT NULL DEFAULT 'system',
    previous_event_sha256 VARCHAR(64),
    event_sha256 VARCHAR(64) NOT NULL UNIQUE,
    payload_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_provenance_events_subject ON provenance_events(subject_type, subject_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_provenance_events_previous_hash ON provenance_events(previous_event_sha256);

CREATE OR REPLACE FUNCTION reject_provenance_event_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Provenance events are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_provenance_event_update ON provenance_events;
CREATE TRIGGER reject_provenance_event_update
BEFORE UPDATE OR DELETE ON provenance_events
FOR EACH ROW EXECUTE FUNCTION reject_provenance_event_mutation();