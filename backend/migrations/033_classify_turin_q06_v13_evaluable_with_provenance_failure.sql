-- Append-only evaluability classification for complete formal responses with visible provenance failure.
BEGIN;

CREATE TABLE IF NOT EXISTS turin_formal_run_evaluability_classifications (
    classification_id VARCHAR(255) PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL,
    evaluability_status VARCHAR(64) NOT NULL CHECK (evaluability_status IN ('evaluable', 'evaluable_with_provenance_failure')),
    classification_reason TEXT NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_formal_run_evaluability_classification_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin formal run evaluability classifications are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_formal_run_evaluability_classification_update ON turin_formal_run_evaluability_classifications;
CREATE TRIGGER reject_turin_formal_run_evaluability_classification_update
BEFORE UPDATE OR DELETE ON turin_formal_run_evaluability_classifications
FOR EACH ROW EXECUTE FUNCTION reject_turin_formal_run_evaluability_classification_mutation();

INSERT INTO turin_formal_run_evaluability_classifications (
    classification_id,
    run_id,
    question_id,
    evaluability_status,
    classification_reason
)
SELECT
    'turin-q06-v13-evaluable-with-provenance-failure',
    'experiment-44c78aad4a99',
    'CI2',
    'evaluable_with_provenance_failure',
    'Granite completed naturally and the exact raw response was retained before parsing. The complete parsed response is inspectable. Provenance validation remains failed with one unsupported authority assertion; that failure is model behaviour available for research evaluation, not a loss of evaluability.'
WHERE EXISTS (
    SELECT 1
    FROM experiment_runs run
    WHERE run.run_id = 'experiment-44c78aad4a99'
      AND run.question_id = 'CI2'
      AND run.retrieval_plan_id = 'CI2-v1'
      AND run.retrieval_plan_version = '1.0'
      AND run.retrieval_protocol_version = 'turin-retrieval-protocol-v1.3'
      AND run.corpus_version = 'corpus_f40d78dbce52'
      AND run.retrieval_scope = 'corpus_wide'
      AND run.retrieval_run_classification = 'primary'
      AND run.fixture_only = false
      AND run.status = 'failed'
      AND run.error_code = 'provenance_validation_failure'
      AND run.raw_model_response IS NOT NULL
      AND run.parsed_response_json IS NOT NULL
      AND jsonb_typeof(run.parsed_response_json) = 'object'
      AND run.parse_status = 'parsed_with_provenance_failure'
      AND run.generation_metadata_json->>'done' = 'true'
      AND run.generation_metadata_json->>'done_reason' = 'stop'
      AND run.generation_metadata_json->>'eval_count' = '940'
      AND run.provenance_validation_json->>'valid' = 'false'
      AND run.provenance_validation_json->>'checked_claims' = '4'
      AND run.provenance_validation_json->>'valid_claims' = '3'
      AND run.provenance_validation_json->>'invalid_claims' = '1'
      AND run.provenance_validation_json->'issues' @> '["Authority assertion Your local authority ID is not present in supplied authority context."]'::jsonb
      AND run.authority_context_json->>'included' = 'false'
      AND run.authority_context_json->'contexts' = '[]'::jsonb
)
AND (SELECT count(*) FROM experiment_runs WHERE question_id = 'CI2' AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.3' AND fixture_only = false) = 1
AND (SELECT count(*) FROM experiment_runs WHERE formal_authorization_id = 'turin-q06-v13-output-capacity-reexecution-authorization') = 1
AND (SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI3', 'CI4', 'SM1', 'SM2', 'SM3', 'SM4')) = 0
AND NOT EXISTS (
    SELECT 1
    FROM turin_formal_run_evaluability_classifications
    WHERE classification_id = 'turin-q06-v13-evaluable-with-provenance-failure'
       OR run_id = 'experiment-44c78aad4a99'
);

COMMIT;
