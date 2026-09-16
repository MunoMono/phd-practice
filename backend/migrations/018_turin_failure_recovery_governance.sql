-- Failed-before-inference recovery is append-only and does not alter original run snapshots.

ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS recovery_of_run_id VARCHAR(255) REFERENCES experiment_runs(run_id),
    ADD COLUMN IF NOT EXISTS recovery_category VARCHAR(128);

CREATE TABLE IF NOT EXISTS turin_formal_run_recoveries (
    id SERIAL PRIMARY KEY,
    recovery_of_run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    plan_id VARCHAR(255) NOT NULL,
    protocol_version VARCHAR(128) NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    recovery_category VARCHAR(128) NOT NULL CHECK (recovery_category = 'infrastructure_failure_before_inference'),
    authorized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_recovery_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin failure-recovery audit records are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_recovery_update ON turin_formal_run_recoveries;
CREATE TRIGGER reject_turin_recovery_update
BEFORE UPDATE OR DELETE ON turin_formal_run_recoveries
FOR EACH ROW EXECUTE FUNCTION reject_turin_recovery_mutation();

DROP INDEX IF EXISTS idx_experiment_runs_primary_question_protocol;
CREATE UNIQUE INDEX idx_experiment_runs_primary_question_protocol
    ON experiment_runs(question_id, retrieval_protocol_version)
    WHERE retrieval_run_classification = 'primary'
      AND retrieval_scope = 'corpus_wide'
      AND (
          status IN ('completed', 'completed_with_missingness')
          OR raw_model_response IS NOT NULL
          OR COALESCE(jsonb_typeof(structured_response_json), 'null') <> 'null'
          OR COALESCE(jsonb_typeof(provenance_validation_json), 'null') <> 'null'
      );

CREATE OR REPLACE FUNCTION validate_turin_failure_recovery()
RETURNS TRIGGER AS $$
DECLARE original_run experiment_runs%ROWTYPE;
BEGIN
    IF NEW.recovery_of_run_id IS NULL AND NEW.recovery_category IS NULL THEN RETURN NEW; END IF;
    IF NEW.recovery_of_run_id IS NULL OR NEW.recovery_category <> 'infrastructure_failure_before_inference' THEN
        RAISE EXCEPTION 'Formal recovery requires complete infrastructure_failure_before_inference lineage.';
    END IF;
    SELECT * INTO original_run FROM experiment_runs WHERE run_id = NEW.recovery_of_run_id;
    IF NOT FOUND OR original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure'
       OR original_run.raw_model_response IS NOT NULL OR original_run.model_name IS NOT NULL
       OR original_run.inference_duration_ms IS NOT NULL OR original_run.parse_status <> 'not_invoked'
       OR COALESCE(jsonb_typeof(original_run.structured_response_json), 'null') <> 'null'
       OR COALESCE(jsonb_typeof(original_run.provenance_validation_json), 'null') <> 'null' THEN
        RAISE EXCEPTION 'Recovery source is not a failed-before-inference infrastructure attempt.';
    END IF;
    IF NEW.question_id <> original_run.question_id OR NEW.retrieval_plan_id <> original_run.retrieval_plan_id
       OR NEW.retrieval_plan_version <> original_run.retrieval_plan_version OR NEW.retrieval_protocol_version <> original_run.retrieval_protocol_version
       OR NEW.corpus_version <> original_run.corpus_version OR NEW.retrieval_scope <> original_run.retrieval_scope
       OR NEW.retrieval_run_classification <> original_run.retrieval_run_classification THEN
        RAISE EXCEPTION 'Recovery must use the identical question, plan, protocol, corpus, scope, and classification.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries a WHERE a.recovery_of_run_id = NEW.recovery_of_run_id AND a.plan_id = NEW.retrieval_plan_id AND a.protocol_version = NEW.retrieval_protocol_version AND a.corpus_version = NEW.corpus_version) THEN
        RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.';
    END IF;
    IF EXISTS (SELECT 1 FROM experiment_runs r WHERE r.recovery_of_run_id = NEW.recovery_of_run_id) THEN
        RAISE EXCEPTION 'Only one formal recovery execution is permitted for a failed-before-inference attempt.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS validate_turin_failure_recovery_insert ON experiment_runs;
CREATE TRIGGER validate_turin_failure_recovery_insert
BEFORE INSERT ON experiment_runs
FOR EACH ROW EXECUTE FUNCTION validate_turin_failure_recovery();