-- Append-only authorization for a demonstrated implementation defect. Existing runs remain immutable.
ALTER TABLE turin_formal_run_recoveries
    DROP CONSTRAINT IF EXISTS turin_formal_run_recoveries_recovery_category_check;
ALTER TABLE turin_formal_run_recoveries
    ADD CONSTRAINT turin_formal_run_recoveries_recovery_category_check
    CHECK (recovery_category IN ('infrastructure_failure_before_inference', 'instrument_implementation_correction'));

CREATE TABLE IF NOT EXISTS turin_formal_run_invalidations (
    id SERIAL PRIMARY KEY,
    invalidated_run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    invalidation_category VARCHAR(128) NOT NULL CHECK (invalidation_category = 'instrument_implementation_correction'),
    defect_code VARCHAR(128) NOT NULL CHECK (defect_code = 'citation_contract_ambiguity'),
    plan_id VARCHAR(255) NOT NULL,
    protocol_version VARCHAR(128) NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    max_tokens INTEGER NOT NULL,
    temperature DOUBLE PRECISION NOT NULL,
    top_p DOUBLE PRECISION NOT NULL,
    do_sample BOOLEAN NOT NULL,
    documented_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_invalidation_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin run-invalidation audit records are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_invalidation_update ON turin_formal_run_invalidations;
CREATE TRIGGER reject_turin_invalidation_update
BEFORE UPDATE OR DELETE ON turin_formal_run_invalidations
FOR EACH ROW EXECUTE FUNCTION reject_turin_invalidation_mutation();

DROP INDEX IF EXISTS idx_experiment_runs_primary_question_protocol;
CREATE UNIQUE INDEX idx_experiment_runs_primary_question_protocol
    ON experiment_runs(question_id, retrieval_protocol_version)
    WHERE retrieval_run_classification = 'primary'
      AND retrieval_scope = 'corpus_wide'
      AND status IN ('completed', 'completed_with_missingness');

CREATE OR REPLACE FUNCTION validate_turin_failure_recovery()
RETURNS TRIGGER AS $$
DECLARE original_run experiment_runs%ROWTYPE;
BEGIN
    IF NEW.recovery_of_run_id IS NULL AND NEW.recovery_category IS NULL THEN
        PERFORM pg_advisory_xact_lock(hashtext(COALESCE(NEW.question_id, '') || COALESCE(NEW.retrieval_protocol_version, '')));
        IF NEW.retrieval_run_classification = 'primary' AND NEW.retrieval_scope = 'corpus_wide'
           AND EXISTS (SELECT 1 FROM experiment_runs prior LEFT JOIN turin_formal_run_invalidations invalidation ON invalidation.invalidated_run_id = prior.run_id WHERE prior.question_id = NEW.question_id AND prior.retrieval_protocol_version = NEW.retrieval_protocol_version AND (prior.status IN ('completed', 'completed_with_missingness') OR prior.raw_model_response IS NOT NULL OR COALESCE(jsonb_typeof(prior.structured_response_json), 'null') <> 'null' OR COALESCE(jsonb_typeof(prior.provenance_validation_json), 'null') <> 'null') AND invalidation.invalidated_run_id IS NULL) THEN
            RAISE EXCEPTION 'An evaluable primary result already exists for this question and protocol.';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.recovery_of_run_id IS NULL THEN
        RAISE EXCEPTION 'Formal recovery requires complete lineage.';
    END IF;
    SELECT * INTO original_run FROM experiment_runs WHERE run_id = NEW.recovery_of_run_id;
    IF NOT FOUND OR NEW.question_id <> original_run.question_id OR NEW.retrieval_plan_id <> original_run.retrieval_plan_id OR NEW.retrieval_plan_version <> original_run.retrieval_plan_version OR NEW.retrieval_protocol_version <> original_run.retrieval_protocol_version OR NEW.corpus_version <> original_run.corpus_version OR NEW.retrieval_scope <> original_run.retrieval_scope OR NEW.retrieval_run_classification <> original_run.retrieval_run_classification THEN
        RAISE EXCEPTION 'Recovery must use the identical question, plan, protocol, corpus, scope, and classification.';
    END IF;
    IF NEW.recovery_category = 'infrastructure_failure_before_inference' THEN
        IF original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure' OR original_run.raw_model_response IS NOT NULL OR original_run.model_name IS NOT NULL OR original_run.inference_duration_ms IS NOT NULL OR original_run.parse_status <> 'not_invoked' THEN RAISE EXCEPTION 'Recovery source is not a failed-before-inference infrastructure attempt.'; END IF;
    ELSIF NEW.recovery_category = 'instrument_implementation_correction' THEN
        IF original_run.status <> 'failed' OR original_run.error_code <> 'provenance_validation_failure' OR original_run.raw_model_response IS NULL OR NOT EXISTS (SELECT 1 FROM turin_formal_run_invalidations invalidation WHERE invalidation.invalidated_run_id = original_run.run_id AND invalidation.invalidation_category = 'instrument_implementation_correction' AND invalidation.defect_code = 'citation_contract_ambiguity' AND invalidation.plan_id = NEW.retrieval_plan_id AND invalidation.protocol_version = NEW.retrieval_protocol_version AND invalidation.corpus_version = NEW.corpus_version AND invalidation.model_name = NEW.model_name AND invalidation.max_tokens = (NEW.model_parameters_json->>'max_tokens')::integer AND invalidation.temperature = (NEW.model_parameters_json->>'temperature')::double precision AND invalidation.top_p = (NEW.model_parameters_json->>'top_p')::double precision AND invalidation.do_sample = (NEW.model_parameters_json->>'do_sample')::boolean) THEN RAISE EXCEPTION 'Recovery source is not a documented instrument implementation defect with identical governed model configuration.'; END IF;
    ELSE RAISE EXCEPTION 'Unsupported formal recovery category.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.'; END IF;
    IF EXISTS (SELECT 1 FROM experiment_runs prior WHERE prior.recovery_of_run_id = NEW.recovery_of_run_id) THEN RAISE EXCEPTION 'Only one formal recovery execution is permitted for a recovery source.'; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;