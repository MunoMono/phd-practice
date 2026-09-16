-- Authorize exactly one prospective Q02 primary execution under Retrieval Protocol v1.1.
WITH approved_plan AS (
    SELECT 1
    FROM turin_retrieval_plans
    WHERE plan_id = 'KR2-v1'
      AND question_id = 'KR2'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND plan_version = '1.0'
      AND researcher_approval_state = 'approved'
), prerequisites AS (
    SELECT 1
    WHERE EXISTS (SELECT 1 FROM approved_plan)
      AND EXISTS (SELECT 1 FROM turin_retrieval_protocol_amendments WHERE protocol_version = 'turin-retrieval-protocol-v1.1')
      AND EXISTS (
          SELECT 1 FROM experiment_runs
          WHERE run_id = 'experiment-ac4550d6a2d2'
            AND question_id = 'KR2'
            AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.0'
            AND status = 'failed'
            AND error_code = 'parse_failure'
            AND corpus_version = 'corpus_f40d78dbce52'
      )
      AND (
          SELECT count(*) FROM experiment_runs
          WHERE question_id = 'KR1'
            AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.0'
            AND status = 'completed'
            AND retrieval_scope = 'corpus_wide'
            AND retrieval_run_classification = 'primary'
      ) = 1
      AND (
          SELECT count(*) FROM experiment_runs
          WHERE question_id = 'KR2'
            AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.1'
            AND retrieval_scope = 'corpus_wide'
            AND retrieval_run_classification = 'primary'
      ) = 0
      AND NOT EXISTS (
          SELECT 1 FROM experiment_runs
          WHERE question_id IN ('KR3', 'KR4', 'KR5', 'KR6', 'KR7', 'KR8', 'KR9', 'KR10', 'KR11', 'KR12')
      )
)
INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id,
    plan_version, plan_protocol_version, execution_protocol_version,
    corpus_version, retrieval_scope, run_classification,
    authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-q02-v11-primary-authorization', 'experiment-ac4550d6a2d2', 'KR2', 'KR2-v1',
    '1.0', 'turin-retrieval-protocol-v1.0', 'turin-retrieval-protocol-v1.1',
    'corpus_f40d78dbce52', 'corpus_wide', 'primary',
    'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning',
    'granite3.1-dense:2b-instruct-q4_K_M',
    '{"max_tokens": 350, "temperature": 0.0, "top_p": 1.0, "do_sample": false}'::jsonb
FROM prerequisites
ON CONFLICT (authorization_id) DO NOTHING;