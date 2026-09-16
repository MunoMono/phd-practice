BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1' AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2' AND authorization_category IN ('protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion', 'infrastructure_recovery_after_v1_2_read_timeout', 'orphaned_inference_replacement_after_write_ahead_persistence_remediation'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.3' AND authorization_category IN ('protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion', 'q07_ci3_v13_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.4' AND authorization_category = 'q07_ci3_v2_v14_primary_authorization')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.5' AND authorization_category IN ('q07_ci3_v2_v15_primary_authorization', 'q08_ci4_v15_primary_authorization', 'q09_sm1_v15_primary_authorization', 'q09_sm1_v2_v15_retrieval_plan_revision_authorization', 'q10_sm2_v15_primary_authorization', 'q11_sm3_v15_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.6' AND authorization_category = 'q12_sm4_v2_v16_zero_documentary_primary_authorization')
        OR (execution_protocol_version = 'turin-comparison-protocol-v2.0-qwen' AND authorization_category IN ('qwen_comparison_q09_sm1_v2_single_run', 'qwen_comparison_q01_kr1_v1_single_run'))
    );

INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
    plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
    run_classification, authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-qwen-q01-kr1-v1-comparison-authorization', NULL,
    'KR1', 'KR1-v1', '1.0', 'turin-retrieval-protocol-v1.0',
    'turin-comparison-protocol-v2.0-qwen', 'corpus_f40d78dbce52', 'corpus_wide',
    'primary', 'qwen_comparison_q01_kr1_v1_single_run', 'qwen3:8b-q4_K_M',
    '{"max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"runtime_timeout_seconds":600}'::jsonb
WHERE EXISTS (
    SELECT 1 FROM experiment_runs
    WHERE run_id = 'experiment-7db3ecba21e1'
      AND question_id = 'KR1'
      AND retrieval_plan_id = 'KR1-v1'
      AND retrieval_plan_version = '1.0'
      AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.0'
      AND corpus_version = 'corpus_f40d78dbce52'
      AND model_name = 'granite3.1-dense:2b-instruct-q4_K_M'
      AND status = 'completed'
)
AND EXISTS (
    SELECT 1 FROM turin_retrieval_plans
    WHERE plan_id = 'KR1-v1'
      AND question_id = 'KR1'
      AND plan_version = '1.0'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND researcher_approval_state = 'approved'
      AND run_classification = 'primary'
      AND plan_json->>'retrieval_scope' = 'corpus_wide'
      AND plan_json->>'top_k' = '5'
      AND plan_json->'lexical_facets' = '[{"facet_id":"project_person","alternatives":["171","Pierre Goumain"]},{"facet_id":"computing","alternatives":["man-computer interaction","man computer interaction","man-computer design systems"]}]'::jsonb
)
AND NOT EXISTS (
    SELECT 1 FROM turin_formal_protocol_authorizations
    WHERE authorization_id = 'turin-qwen-q01-kr1-v1-comparison-authorization'
)
AND NOT EXISTS (
    SELECT 1 FROM experiment_runs
    WHERE retrieval_protocol_version = 'turin-comparison-protocol-v2.0-qwen'
      AND question_id = 'KR1'
      AND retrieval_plan_id = 'KR1-v1'
      AND fixture_only = false
);

COMMIT;