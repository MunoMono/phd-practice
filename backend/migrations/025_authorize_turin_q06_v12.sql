-- Authorize exactly one Q06 primary replacement after v1.1 output-token exhaustion.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authoriz_execution_protocol_version_check,
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizatio_authorization_category_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1'
            AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR
        (execution_protocol_version = 'turin-retrieval-protocol-v1.2'
            AND authorization_category = 'protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion')
    );

WITH approved_plan AS (
    SELECT 1
    FROM turin_retrieval_plans
    WHERE plan_id = 'CI2-v1'
      AND question_id = 'CI2'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND plan_version = '1.0'
      AND researcher_approval_state = 'approved'
      AND run_classification = 'primary'
      AND plan_json->>'retrieval_scope' = 'corpus_wide'
      AND (plan_json->>'top_k')::integer = 5
), prerequisites AS (
    SELECT 1
    WHERE EXISTS (SELECT 1 FROM approved_plan)
      AND EXISTS (
          SELECT 1
          FROM turin_retrieval_protocol_amendments
          WHERE protocol_version = 'turin-retrieval-protocol-v1.2'
            AND amendment_scope = 'structured_output_capacity'
            AND amendment_json->>'structured_output_max_tokens' = '500'
      )
      AND EXISTS (SELECT 1 FROM turin_retrieval_protocol_amendments WHERE protocol_version = 'turin-retrieval-protocol-v1.1')
      AND EXISTS (
          SELECT 1
          FROM experiment_runs
          WHERE run_id = 'experiment-2bc7c95f1c98'
            AND question_id = 'CI2'
            AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.1'
            AND status = 'failed'
            AND error_code = 'output_token_exhaustion'
            AND corpus_version = 'corpus_f40d78dbce52'
            AND retrieval_scope = 'corpus_wide'
            AND retrieval_run_classification = 'primary'
      )
      AND (SELECT count(*) FROM experiment_runs WHERE question_id = 'CI2' AND retrieval_scope = 'corpus_wide' AND retrieval_run_classification = 'primary' AND status IN ('completed', 'completed_with_missingness') AND parse_status = 'parsed') = 0
      AND (SELECT count(*) FROM turin_formal_protocol_authorizations WHERE question_id = 'CI2' OR execution_protocol_version = 'turin-retrieval-protocol-v1.2') = 0
      AND (SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI3', 'CI4', 'SM1', 'SM2', 'SM3', 'SM4')) = 0
)
INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id,
    plan_version, plan_protocol_version, execution_protocol_version,
    corpus_version, retrieval_scope, run_classification,
    authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-q06-v12-primary-authorization', 'experiment-2bc7c95f1c98', 'CI2', 'CI2-v1',
    '1.0', 'turin-retrieval-protocol-v1.0', 'turin-retrieval-protocol-v1.2',
    'corpus_f40d78dbce52', 'corpus_wide', 'primary',
    'protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion',
    'granite3.1-dense:2b-instruct-q4_K_M',
    '{"max_tokens": 500, "temperature": 0.0, "top_p": 1.0, "do_sample": false}'::jsonb
FROM prerequisites
ON CONFLICT (authorization_id) DO NOTHING;

COMMIT;