-- Authorize one Q06 v1.2 infrastructure recovery after the verified no-output ReadTimeout.
BEGIN;

WITH approved_plan AS (
    SELECT 1
    FROM turin_retrieval_plans
    WHERE plan_id = 'CI2-v1'
      AND question_id = 'CI2'
      AND plan_version = '1.0'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND researcher_approval_state = 'approved'
      AND run_classification = 'primary'
      AND plan_json->>'retrieval_scope' = 'corpus_wide'
      AND (plan_json->>'top_k')::integer = 5
), prerequisites AS (
    SELECT 1
    WHERE EXISTS (SELECT 1 FROM approved_plan)
      AND EXISTS (
          SELECT 1 FROM turin_retrieval_protocol_amendments
          WHERE protocol_version = 'turin-retrieval-protocol-v1.2'
            AND amendment_scope = 'structured_output_capacity'
            AND amendment_json->>'structured_output_max_tokens' = '500'
      )
      AND EXISTS (
          SELECT 1 FROM experiment_runs
          WHERE run_id = 'experiment-3643a4fc2fb0'
            AND question_id = 'CI2'
            AND retrieval_plan_id = 'CI2-v1'
            AND retrieval_plan_version = '1.0'
            AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.2'
            AND corpus_version = 'corpus_f40d78dbce52'
            AND retrieval_scope = 'corpus_wide'
            AND retrieval_run_classification = 'primary'
            AND formal_authorization_id = 'turin-q06-v12-primary-authorization'
            AND status = 'failed'
            AND error_code = 'granite_failure'
            AND error_message LIKE 'ReadTimeout:%'
            AND (raw_model_response IS NULL OR raw_model_response = '')
            AND (raw_repair_response IS NULL OR raw_repair_response = '')
            AND model_name IS NULL
            AND model_parameters_json = '{}'::jsonb
            AND inference_duration_ms IS NULL
            AND parse_status = 'not_invoked'
            AND (parsed_response_json IS NULL OR parsed_response_json = 'null'::jsonb)
            AND (structured_response_json IS NULL OR structured_response_json IN ('null'::jsonb, '{}'::jsonb))
            AND (display_response_json IS NULL OR display_response_json IN ('null'::jsonb, '{}'::jsonb))
            AND (provenance_validation_json IS NULL OR provenance_validation_json IN ('null'::jsonb, '{}'::jsonb))
            AND repair_attempted = false
      )
      AND (SELECT count(*) FROM experiment_runs WHERE question_id = 'CI2' AND retrieval_scope = 'corpus_wide' AND retrieval_run_classification = 'primary' AND status IN ('completed', 'completed_with_missingness') AND parse_status = 'parsed') = 0
      AND NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations WHERE authorization_id = 'turin-q06-v12-read-timeout-infrastructure-recovery-authorization')
      AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE recovery_of_run_id = 'experiment-3643a4fc2fb0')
      AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE question_id IN ('CI3', 'CI4', 'SM1', 'SM2', 'SM3', 'SM4'))
)
INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version, plan_protocol_version,
    execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category,
    model_name, model_parameters_json
)
SELECT
    'turin-q06-v12-read-timeout-infrastructure-recovery-authorization', 'experiment-3643a4fc2fb0', 'CI2', 'CI2-v1', '1.0', 'turin-retrieval-protocol-v1.0',
    'turin-retrieval-protocol-v1.2', 'corpus_f40d78dbce52', 'corpus_wide', 'primary', 'infrastructure_recovery_after_v1_2_read_timeout',
    'granite3.1-dense:2b-instruct-q4_K_M', '{"max_tokens": 500, "temperature": 0.0, "top_p": 1.0, "do_sample": false, "granite_timeout_seconds": 600}'::jsonb
FROM prerequisites;

COMMIT;