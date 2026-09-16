-- Immutable archival experiment snapshots and separately editable assessments.

CREATE TABLE IF NOT EXISTS experiment_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL UNIQUE,
    research_case VARCHAR(64) NOT NULL,
    prompt_name VARCHAR(255) NOT NULL,
    prompt_version VARCHAR(64) NOT NULL,
    system_prompt_version VARCHAR(64) NOT NULL,
    exact_research_question TEXT NOT NULL,
    corpus_version VARCHAR(255),
    git_commit VARCHAR(64),
    retrieval_method VARCHAR(128) NOT NULL,
    retrieval_config_json JSONB NOT NULL,
    retrieval_diagnostics_json JSONB NOT NULL,
    context_mode VARCHAR(64) NOT NULL,
    context_character_count INTEGER NOT NULL,
    context_chunk_count INTEGER NOT NULL,
    omitted_chunk_ids_json JSONB NOT NULL,
    authority_context_json JSONB NOT NULL,
    model_name VARCHAR(255),
    model_runtime VARCHAR(64),
    model_quantisation VARCHAR(128),
    model_parameters_json JSONB NOT NULL,
    model_seed_if_actual VARCHAR(64),
    inference_duration_ms DOUBLE PRECISION,
    raw_model_response TEXT,
    repair_attempted BOOLEAN NOT NULL DEFAULT FALSE,
    raw_repair_response TEXT,
    parse_status VARCHAR(64) NOT NULL,
    structured_response_json JSONB,
    provenance_validation_json JSONB,
    status VARCHAR(64) NOT NULL,
    error_code VARCHAR(128),
    error_message TEXT,
    fixture_only BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experiment_runs_created_at ON experiment_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiment_runs_status ON experiment_runs(status);

CREATE TABLE IF NOT EXISTS experiment_run_evidence (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    rank INTEGER NOT NULL,
    score DOUBLE PRECISION,
    document_id VARCHAR(255) NOT NULL,
    pid VARCHAR(255),
    archive_record_pid VARCHAR(255),
    archive_resolution_status VARCHAR(64) NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    chunk_id VARCHAR(255) NOT NULL,
    chunk_sequence INTEGER,
    excerpt TEXT NOT NULL,
    included_in_context BOOLEAN NOT NULL,
    snapshot_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_run_evidence_run_id ON experiment_run_evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_evidence_chunk_id ON experiment_run_evidence(chunk_id);

CREATE TABLE IF NOT EXISTS experiment_run_assessments (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    retrieval_relevance INTEGER CHECK (retrieval_relevance BETWEEN 0 AND 3),
    provenance_accuracy INTEGER CHECK (provenance_accuracy BETWEEN 0 AND 3),
    interpretative_restraint INTEGER CHECK (interpretative_restraint BETWEEN 0 AND 3),
    preservation_of_contestation INTEGER CHECK (preservation_of_contestation BETWEEN 0 AND 3),
    missingness_handling INTEGER CHECK (missingness_handling BETWEEN 0 AND 3),
    failure_categories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    authority_influence_note TEXT,
    assessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_immutable_experiment_run_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Experiment run snapshots are immutable; create a new run instead.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_experiment_run_update ON experiment_runs;
CREATE TRIGGER reject_experiment_run_update BEFORE UPDATE OR DELETE ON experiment_runs
FOR EACH ROW EXECUTE FUNCTION reject_immutable_experiment_run_mutation();

DROP TRIGGER IF EXISTS reject_experiment_evidence_update ON experiment_run_evidence;
CREATE TRIGGER reject_experiment_evidence_update BEFORE UPDATE OR DELETE ON experiment_run_evidence
FOR EACH ROW EXECUTE FUNCTION reject_immutable_experiment_run_mutation();