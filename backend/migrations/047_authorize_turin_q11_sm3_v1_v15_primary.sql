-- One append-only authorization for the Q11 SM3-v1 / v1.5 formal execution.
-- This migration authorizes no inference.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1' AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2' AND authorization_category IN ('protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion', 'infrastructure_recovery_after_v1_2_read_timeout', 'orphaned_inference_replacement_after_write_ahead_persistence_remediation'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.3' AND authorization_category IN ('protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion', 'q07_ci3_v13_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.4' AND authorization_category = 'q07_ci3_v2_v14_primary_authorization')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.5' AND authorization_category IN ('q07_ci3_v2_v15_primary_authorization', 'q08_ci4_v15_primary_authorization', 'q09_sm1_v15_primary_authorization', 'q09_sm1_v2_v15_retrieval_plan_revision_authorization', 'q10_sm2_v15_primary_authorization', 'q11_sm3_v15_primary_authorization'))
    );

CREATE OR REPLACE FUNCTION validate_turin_clean_primary_authorization()
RETURNS TRIGGER AS $$
DECLARE
    expected_question_id VARCHAR(64);
    expected_plan_id VARCHAR(255);
    expected_plan_version VARCHAR(128);
    expected_execution_protocol VARCHAR(128);
    expected_authorization_category VARCHAR(255);
BEGIN
    IF NEW.formal_authorization_id = 'turin-q07-ci3-v2-v14-primary-authorization' THEN
        expected_question_id := 'CI3'; expected_plan_id := 'CI3-v2'; expected_plan_version := '2.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.4'; expected_authorization_category := 'q07_ci3_v2_v14_primary_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q07-ci3-v2-v15-primary-authorization' THEN
        expected_question_id := 'CI3'; expected_plan_id := 'CI3-v2'; expected_plan_version := '2.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q07_ci3_v2_v15_primary_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q08-ci4-v1-v15-primary-authorization' THEN
        expected_question_id := 'CI4'; expected_plan_id := 'CI4-v1'; expected_plan_version := '1.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q08_ci4_v15_primary_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q09-sm1-v1-v15-primary-authorization' THEN
        expected_question_id := 'SM1'; expected_plan_id := 'SM1-v1'; expected_plan_version := '1.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q09_sm1_v15_primary_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization' THEN
        expected_question_id := 'SM1'; expected_plan_id := 'SM1-v2'; expected_plan_version := '2.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q09_sm1_v2_v15_retrieval_plan_revision_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q10-sm2-v1-v15-primary-authorization' THEN
        expected_question_id := 'SM2'; expected_plan_id := 'SM2-v1'; expected_plan_version := '1.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q10_sm2_v15_primary_authorization';
    ELSIF NEW.formal_authorization_id = 'turin-q11-sm3-v1-v15-primary-authorization' THEN
        expected_question_id := 'SM3'; expected_plan_id := 'SM3-v1'; expected_plan_version := '1.0'; expected_execution_protocol := 'turin-retrieval-protocol-v1.5'; expected_authorization_category := 'q11_sm3_v15_primary_authorization';
    ELSE
        RETURN NEW;
    END IF;

    IF NEW.recovery_of_run_id IS NOT NULL
       OR NEW.recovery_category IS NOT NULL
       OR NEW.question_id <> expected_question_id
       OR NEW.retrieval_plan_id <> expected_plan_id
       OR NEW.retrieval_plan_version <> expected_plan_version
       OR NEW.retrieval_protocol_version <> expected_execution_protocol
       OR NEW.corpus_version <> 'corpus_f40d78dbce52'
       OR NEW.retrieval_scope <> 'corpus_wide'
       OR NEW.retrieval_run_classification <> 'primary'
       OR NEW.model_name <> 'granite3.1-dense:2b-instruct-q4_K_M'
       OR NEW.model_parameters_json <> '{"max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"granite_timeout_seconds":1200}'::jsonb
       OR NOT EXISTS (
           SELECT 1 FROM turin_formal_protocol_authorizations auth_record
           WHERE auth_record.authorization_id = NEW.formal_authorization_id
             AND auth_record.question_id = NEW.question_id
             AND auth_record.plan_id = NEW.retrieval_plan_id
             AND auth_record.plan_version = NEW.retrieval_plan_version
             AND auth_record.execution_protocol_version = NEW.retrieval_protocol_version
             AND auth_record.corpus_version = NEW.corpus_version
             AND auth_record.authorization_category = expected_authorization_category
       ) THEN
        RAISE EXCEPTION 'Turin formal execution requires its exact authorization and frozen identity.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
    plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
    run_classification, authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-q11-sm3-v1-v15-primary-authorization', NULL, 'SM3', 'SM3-v1', '1.0',
    'turin-retrieval-protocol-v1.0', 'turin-retrieval-protocol-v1.5',
    'corpus_f40d78dbce52', 'corpus_wide', 'primary',
    'q11_sm3_v15_primary_authorization', 'granite3.1-dense:2b-instruct-q4_K_M',
    '{"max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"granite_timeout_seconds":1200}'::jsonb
WHERE EXISTS (
    SELECT 1 FROM turin_retrieval_plans
    WHERE plan_id = 'SM3-v1' AND question_id = 'SM3' AND plan_version = '1.0'
      AND researcher_approval_state = 'approved' AND run_classification = 'primary'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND plan_json->>'retrieval_scope' = 'corpus_wide'
      AND plan_json->>'top_k' = '5'
      AND plan_json->'lexical_facets' = '[{"facet_id":"programme","alternatives":["Design in General Education"]},{"facet_id":"audience_reception","alternatives":["teachers","pupils","evaluation","feedback"]}]'::jsonb
      AND plan_json->'authority_linked_document_ids' = '[]'::jsonb
      AND plan_json->'authority_document_link_ids' = '[]'::jsonb
)
AND EXISTS (
    SELECT 1 FROM turin_retrieval_protocol_amendments
    WHERE protocol_version = 'turin-retrieval-protocol-v1.5'
      AND amendment_json->>'structured_output_max_tokens' = '1500'
      AND amendment_json->>'response_schema_version' = 'turin-archival-analysis-response-v1.5-concise'
      AND amendment_json->>'prompt_changed' = 'false'
)
AND EXISTS (
    SELECT 1 FROM experiment_runs
    WHERE run_id = 'experiment-f5914b425bb4' AND question_id = 'SM2'
      AND retrieval_plan_id = 'SM2-v1' AND status = 'completed'
      AND provenance_validation_json->>'valid' = 'true'
)
AND NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations WHERE authorization_id = 'turin-q11-sm3-v1-v15-primary-authorization')
AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE question_id = 'SM3' AND fixture_only = false)
AND NOT EXISTS (SELECT 1 FROM turin_formal_run_evaluability_classifications WHERE question_id = 'SM3')
AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE question_id = 'SM4');

COMMIT;