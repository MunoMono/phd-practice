-- Bind immutable experiment outputs and retained source snapshots.

ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS output_sha256 VARCHAR(64);

ALTER TABLE experiment_run_evidence
    ADD COLUMN IF NOT EXISTS evidence_sha256 VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_output_sha256 ON experiment_runs(output_sha256);
CREATE INDEX IF NOT EXISTS idx_experiment_run_evidence_evidence_sha256 ON experiment_run_evidence(evidence_sha256);