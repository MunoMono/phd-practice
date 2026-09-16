BEGIN;

CREATE TABLE IF NOT EXISTS turin_evidence_pipeline_diagnostic_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL UNIQUE,
    protocol_version VARCHAR(128) NOT NULL,
    diagnostic_namespace VARCHAR(128) NOT NULL,
    baseline_run_id VARCHAR(255) REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL,
    retrieval_plan_id VARCHAR(255) NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    artifact_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_evidence_pipeline_diagnostic_mutation()
RETURNS TRIGGER AS $$ BEGIN
    RAISE EXCEPTION 'Turin evidence-pipeline diagnostic artifacts are immutable.';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER reject_turin_evidence_pipeline_diagnostic_update
BEFORE UPDATE OR DELETE ON turin_evidence_pipeline_diagnostic_runs
FOR EACH ROW EXECUTE FUNCTION reject_turin_evidence_pipeline_diagnostic_mutation();

COMMIT;