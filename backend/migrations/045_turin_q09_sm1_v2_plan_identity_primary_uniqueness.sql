-- Preserve one evaluable corpus-wide primary result per immutable retrieval plan.
-- Q09 SM1-v2 is already authorized by migration 044; this migration authorizes no inference.
-- Legacy unauthorised rows remain governed by the existing insert trigger.
BEGIN;

DROP INDEX IF EXISTS idx_experiment_runs_primary_question_protocol;
CREATE UNIQUE INDEX idx_experiment_runs_primary_question_protocol_plan
    ON experiment_runs(question_id, retrieval_protocol_version, retrieval_plan_id, retrieval_plan_version)
    WHERE retrieval_run_classification = 'primary'
      AND retrieval_scope = 'corpus_wide'
            AND formal_authorization_id IS NOT NULL
      AND (
          status IN ('completed', 'completed_with_missingness')
          OR raw_model_response IS NOT NULL
          OR COALESCE(jsonb_typeof(structured_response_json), 'null') <> 'null'
          OR COALESCE(jsonb_typeof(provenance_validation_json), 'null') <> 'null'
      );

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
    IF OLD.run_id = 'experiment-381bc274183b'
       AND OLD.status = 'failed'
       AND OLD.error_code = 'persistence_failure'
       AND OLD.formal_authorization_id = 'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization'
       AND OLD.raw_model_response IS NOT NULL
       AND NEW.status = 'completed'
       AND NEW.error_code IS NULL
       AND NEW.error_message IS NULL
       AND NEW.run_id = OLD.run_id
       AND NEW.created_at = OLD.created_at
       AND NEW.locked_at = OLD.locked_at
       AND NEW.question_id = OLD.question_id
       AND NEW.retrieval_plan_id = OLD.retrieval_plan_id
       AND NEW.retrieval_plan_version = OLD.retrieval_plan_version
       AND NEW.retrieval_protocol_version = OLD.retrieval_protocol_version
       AND NEW.corpus_version = OLD.corpus_version
       AND NEW.formal_authorization_id = OLD.formal_authorization_id
       AND NEW.raw_model_response = OLD.raw_model_response
       AND NEW.raw_repair_response IS NOT DISTINCT FROM OLD.raw_repair_response
       AND NEW.repair_attempted = false THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Experiment run snapshots are immutable after terminal persistence.';
END;
$$ LANGUAGE plpgsql;

COMMIT;