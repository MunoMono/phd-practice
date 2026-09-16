-- Durable write-ahead lifecycle and append-only record of the Q06 orphaned inference.
BEGIN;

CREATE TABLE IF NOT EXISTS turin_execution_incidents (
    incident_id VARCHAR(255) PRIMARY KEY,
    authorization_id VARCHAR(255) NOT NULL UNIQUE REFERENCES turin_formal_protocol_authorizations(authorization_id) ON DELETE RESTRICT,
    intended_run_id VARCHAR(255) NOT NULL UNIQUE,
    parent_run_id VARCHAR(255) NOT NULL REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL,
    incident_category VARCHAR(128) NOT NULL CHECK (incident_category = 'post_generation_persistence_failure'),
    granite_http_status INTEGER NOT NULL CHECK (granite_http_status = 200),
    raw_response_durably_persisted BOOLEAN NOT NULL DEFAULT false,
    detail_json JSONB NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_execution_incident_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin execution incidents are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_execution_incident_update ON turin_execution_incidents;
CREATE TRIGGER reject_turin_execution_incident_update
BEFORE UPDATE OR DELETE ON turin_execution_incidents
FOR EACH ROW EXECUTE FUNCTION reject_turin_execution_incident_mutation();

CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_runs_formal_authorization_once
    ON experiment_runs(formal_authorization_id)
    WHERE formal_authorization_id IS NOT NULL;

CREATE OR REPLACE FUNCTION reject_immutable_experiment_run_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'running'
       AND NEW.status IN ('running', 'completed', 'completed_with_missingness', 'failed')
       AND NEW.run_id = OLD.run_id
       AND NEW.created_at = OLD.created_at
       AND NEW.locked_at = OLD.locked_at THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Experiment run snapshots are immutable after terminal persistence.';
END;
$$ LANGUAGE plpgsql;

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
    IF NEW.recovery_of_run_id IS NULL THEN RAISE EXCEPTION 'Formal recovery requires complete lineage.'; END IF;
    SELECT * INTO original_run FROM experiment_runs WHERE run_id = NEW.recovery_of_run_id;
    IF NOT FOUND OR NEW.question_id <> original_run.question_id OR NEW.retrieval_plan_id <> original_run.retrieval_plan_id OR NEW.retrieval_plan_version <> original_run.retrieval_plan_version OR NEW.retrieval_protocol_version <> original_run.retrieval_protocol_version OR NEW.corpus_version <> original_run.corpus_version OR NEW.retrieval_scope <> original_run.retrieval_scope OR NEW.retrieval_run_classification <> original_run.retrieval_run_classification THEN RAISE EXCEPTION 'Recovery must use the identical question, plan, protocol, corpus, scope, and classification.'; END IF;
    IF NEW.recovery_category = 'infrastructure_recovery_after_v1_2_read_timeout' THEN
        IF original_run.run_id <> 'experiment-3643a4fc2fb0' OR original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure' OR original_run.error_message NOT LIKE 'ReadTimeout:%' OR original_run.raw_model_response IS NOT NULL OR original_run.raw_repair_response IS NOT NULL OR original_run.parse_status <> 'not_invoked' OR NOT (original_run.parsed_response_json IS NULL OR original_run.parsed_response_json = 'null'::jsonb) OR NOT (original_run.structured_response_json IS NULL OR original_run.structured_response_json IN ('null'::jsonb, '{}'::jsonb)) OR NOT (original_run.display_response_json IS NULL OR original_run.display_response_json IN ('null'::jsonb, '{}'::jsonb)) OR NOT (original_run.provenance_validation_json IS NULL OR original_run.provenance_validation_json IN ('null'::jsonb, '{}'::jsonb)) THEN RAISE EXCEPTION 'Recovery source is not the governed Q06 no-output ReadTimeout incident.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a WHERE a.authorization_id = NEW.formal_authorization_id AND a.prior_non_evaluable_run_id = NEW.recovery_of_run_id AND a.question_id = NEW.question_id AND a.plan_id = NEW.retrieval_plan_id AND a.execution_protocol_version = NEW.retrieval_protocol_version AND a.corpus_version = NEW.corpus_version AND a.authorization_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires its exact formal authorization.'; END IF;
        IF EXISTS (SELECT 1 FROM turin_execution_incidents i WHERE i.authorization_id = NEW.formal_authorization_id) THEN RAISE EXCEPTION 'Formal authorization is logically spent by a recorded execution incident.'; END IF;
    ELSIF NEW.recovery_category = 'infrastructure_failure_before_inference' THEN
        IF original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure' OR original_run.raw_model_response IS NOT NULL OR original_run.model_name IS NOT NULL OR original_run.inference_duration_ms IS NOT NULL OR original_run.parse_status <> 'not_invoked' THEN RAISE EXCEPTION 'Recovery source is not a failed-before-inference infrastructure attempt.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.'; END IF;
    ELSIF NEW.recovery_category = 'instrument_implementation_correction' THEN
        IF original_run.status <> 'failed' OR original_run.error_code <> 'provenance_validation_failure' OR original_run.raw_model_response IS NULL OR NOT EXISTS (SELECT 1 FROM turin_formal_run_invalidations invalidation WHERE invalidation.invalidated_run_id = original_run.run_id AND invalidation.invalidation_category = 'instrument_implementation_correction' AND invalidation.defect_code = 'citation_contract_ambiguity' AND invalidation.plan_id = NEW.retrieval_plan_id AND invalidation.protocol_version = NEW.retrieval_protocol_version AND invalidation.corpus_version = NEW.corpus_version AND invalidation.model_name = NEW.model_name AND invalidation.max_tokens = (NEW.model_parameters_json->>'max_tokens')::integer AND invalidation.temperature = (NEW.model_parameters_json->>'temperature')::double precision AND invalidation.top_p = (NEW.model_parameters_json->>'top_p')::double precision AND invalidation.do_sample = (NEW.model_parameters_json->>'do_sample')::boolean) THEN RAISE EXCEPTION 'Recovery source is not a documented instrument implementation defect with identical governed model configuration.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.'; END IF;
    ELSE
        RAISE EXCEPTION 'Unsupported formal recovery category.';
    END IF;
    IF EXISTS (SELECT 1 FROM experiment_runs prior WHERE prior.recovery_of_run_id = NEW.recovery_of_run_id) THEN RAISE EXCEPTION 'Only one formal recovery execution is permitted for a recovery source.'; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

INSERT INTO turin_execution_incidents (incident_id, authorization_id, intended_run_id, parent_run_id, question_id, incident_category, granite_http_status, raw_response_durably_persisted, detail_json)
SELECT 'turin-q06-v12-orphaned-inference-incident', 'turin-q06-v12-read-timeout-infrastructure-recovery-authorization', 'experiment-2604c21d4d1b', 'experiment-3643a4fc2fb0', 'CI2', 'post_generation_persistence_failure', 200, false,
       '{"ollama_duration_seconds":305,"failure":"validate_turin_failure_recovery rejected the recovery category during final insert; fallback persistence raised PendingRollbackError","exact_raw_response_available":false}'::jsonb
WHERE EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations WHERE authorization_id = 'turin-q06-v12-read-timeout-infrastructure-recovery-authorization')
  AND NOT EXISTS (SELECT 1 FROM turin_execution_incidents WHERE incident_id = 'turin-q06-v12-orphaned-inference-incident');

COMMIT;