BEGIN;

CREATE TABLE IF NOT EXISTS turin_corpus_dev_benchmarks (
    benchmark_version VARCHAR(128) PRIMARY KEY,
    benchmark_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS turin_corpus_dev_benchmark_runs (
    run_id VARCHAR(255) PRIMARY KEY,
    benchmark_version VARCHAR(128) NOT NULL REFERENCES turin_corpus_dev_benchmarks(benchmark_version) ON DELETE RESTRICT,
    case_id VARCHAR(64) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    configuration_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS turin_corpus_dev_benchmark_run_artifacts (
    run_id VARCHAR(255) NOT NULL REFERENCES turin_corpus_dev_benchmark_runs(run_id) ON DELETE RESTRICT,
    artifact_sequence INTEGER NOT NULL,
    artifact_type VARCHAR(64) NOT NULL,
    artifact_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, artifact_sequence)
);

CREATE OR REPLACE FUNCTION reject_turin_corpus_dev_benchmark_mutation()
RETURNS TRIGGER AS $$ BEGIN
    RAISE EXCEPTION 'Turin corpus development benchmark records are immutable.';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER reject_turin_corpus_dev_benchmark_run_update
BEFORE UPDATE OR DELETE ON turin_corpus_dev_benchmark_runs
FOR EACH ROW EXECUTE FUNCTION reject_turin_corpus_dev_benchmark_mutation();

CREATE TRIGGER reject_turin_corpus_dev_benchmark_artifact_update
BEFORE UPDATE OR DELETE ON turin_corpus_dev_benchmark_run_artifacts
FOR EACH ROW EXECUTE FUNCTION reject_turin_corpus_dev_benchmark_mutation();

COMMIT;