-- Add deterministic SHA-256 bindings for persistent provenance records.
-- These are integrity checksums, not C2PA manifests or digital signatures.

ALTER TABLE query_runs
    ADD COLUMN IF NOT EXISTS provenance_sha256 VARCHAR(64);

ALTER TABLE query_run_chunks
    ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);

ALTER TABLE claim_evidence
    ADD COLUMN IF NOT EXISTS evidence_sha256 VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_query_runs_provenance_sha256 ON query_runs(provenance_sha256);
CREATE INDEX IF NOT EXISTS idx_query_run_chunks_content_sha256 ON query_run_chunks(content_sha256);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_evidence_sha256 ON claim_evidence(evidence_sha256);