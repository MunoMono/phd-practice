-- Preserve researcher claim revisions and withdrawn evidence records.

ALTER TABLE claim_evidence
    ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS withdrawal_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_claim_evidence_withdrawn_at ON claim_evidence(withdrawn_at);

CREATE TABLE IF NOT EXISTS claim_revisions (
    id SERIAL PRIMARY KEY,
    claim_id VARCHAR(255) NOT NULL REFERENCES claims(claim_id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL,
    reason VARCHAR(128) NOT NULL,
    snapshot_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (claim_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_claim_revisions_claim_id ON claim_revisions(claim_id, revision DESC);