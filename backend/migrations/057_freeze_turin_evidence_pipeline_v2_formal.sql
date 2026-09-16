BEGIN;

CREATE TABLE IF NOT EXISTS turin_evidence_pipeline_protocol_snapshots (
    protocol_version VARCHAR(128) PRIMARY KEY,
    configuration_fingerprint VARCHAR(128) NOT NULL,
    configuration_json JSONB NOT NULL,
    git_commit VARCHAR(64) NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    metadata_snapshot VARCHAR(128) NOT NULL,
    frozen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_evidence_pipeline_protocol_snapshot_mutation()
RETURNS TRIGGER AS $$ BEGIN
    RAISE EXCEPTION 'Turin evidence-pipeline protocol snapshots are immutable.';
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_evidence_pipeline_protocol_snapshot_update ON turin_evidence_pipeline_protocol_snapshots;
CREATE TRIGGER reject_turin_evidence_pipeline_protocol_snapshot_update
BEFORE UPDATE OR DELETE ON turin_evidence_pipeline_protocol_snapshots
FOR EACH ROW EXECUTE FUNCTION reject_turin_evidence_pipeline_protocol_snapshot_mutation();

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1' AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2' AND authorization_category IN ('protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion', 'infrastructure_recovery_after_v1_2_read_timeout', 'orphaned_inference_replacement_after_write_ahead_persistence_remediation'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.3' AND authorization_category IN ('protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion', 'q07_ci3_v13_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.4' AND authorization_category = 'q07_ci3_v2_v14_primary_authorization')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.5' AND authorization_category IN ('q07_ci3_v2_v15_primary_authorization', 'q08_ci4_v15_primary_authorization', 'q09_sm1_v15_primary_authorization', 'q09_sm1_v2_v15_retrieval_plan_revision_authorization', 'q10_sm2_v15_primary_authorization', 'q11_sm3_v15_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.6' AND authorization_category = 'q12_sm4_v2_v16_zero_documentary_primary_authorization')
        OR (execution_protocol_version = 'turin-comparison-protocol-v2.0-qwen' AND authorization_category LIKE 'qwen_comparison_%')
        OR (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND authorization_category = 'qwen_evidence_pipeline_v2_primary')
    );

INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
    plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
    run_classification, authorization_category, model_name, model_parameters_json
)
SELECT 'turin-qwen-v2-' || lower(question_id) || '-authorization', NULL, question_id, plan_id,
       plan_version, protocol_version, 'turin-evidence-pipeline-v2.0-qwen-formal',
       'corpus_f40d78dbce52', 'corpus_wide', 'primary', 'qwen_evidence_pipeline_v2_primary',
       'qwen3:8b-q4_K_M',
       '{"temperature":0.2,"num_ctx":16384,"think":false,"stage_a_max_output_tokens":1500,"stage_b_max_output_tokens":1000,"stage_c_max_output_tokens":768}'::jsonb
FROM turin_retrieval_plans
WHERE (question_id, plan_id) IN (
        ('KR1','KR1-v1'), ('KR2','KR2-v1'), ('KR3','KR3-v1'), ('KR4','KR4-v1'),
        ('CI1','CI1-v1'), ('CI2','CI2-v1'), ('CI3','CI3-v2'), ('CI4','CI4-v1'),
        ('SM1','SM1-v2'), ('SM2','SM2-v1'), ('SM3','SM3-v1'), ('SM4','SM4-v2')
)
  AND researcher_approval_state = 'approved'
  AND run_classification = 'primary'
  AND plan_json->>'retrieval_scope' = 'corpus_wide'
  AND NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a WHERE a.authorization_id = 'turin-qwen-v2-' || lower(turin_retrieval_plans.question_id) || '-authorization');

COMMIT;