BEGIN;

CREATE TABLE IF NOT EXISTS turin_qwen_v2_recovery_authorizations (
    authorization_id VARCHAR(255) PRIMARY KEY,
    original_run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL UNIQUE,
    recovery_reason VARCHAR(128) NOT NULL CHECK (recovery_reason = 'infrastructure_failure_before_inference'),
    inference_started BOOLEAN NOT NULL DEFAULT false CHECK (inference_started = false),
    configuration_fingerprint VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_qwen_v2_recovery_authorization_mutation()
RETURNS TRIGGER AS $$ BEGIN
    RAISE EXCEPTION 'Turin Qwen V2 recovery authorizations are append-only.';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER reject_turin_qwen_v2_recovery_authorization_update
BEFORE UPDATE OR DELETE ON turin_qwen_v2_recovery_authorizations
FOR EACH ROW EXECUTE FUNCTION reject_turin_qwen_v2_recovery_authorization_mutation();

ALTER TABLE turin_formal_protocol_authorizations
  DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
  ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
    (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal-recovery' AND authorization_category = 'qwen_evidence_pipeline_v2_preinference_recovery')
    OR (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND authorization_category = 'qwen_evidence_pipeline_v2_primary')
    OR execution_protocol_version NOT LIKE 'turin-evidence-pipeline-v2.0-qwen-formal%'
  );

INSERT INTO turin_qwen_v2_recovery_authorizations (authorization_id, original_run_id, question_id, recovery_reason, configuration_fingerprint)
SELECT 'turin-qwen-v2-' || lower(question_id) || '-preinference-recovery', run_id, question_id, 'infrastructure_failure_before_inference',
       'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966'
FROM experiment_runs
WHERE run_id IN ('experiment-fe59f8653b00','experiment-166a3d05493b','experiment-1f711de966c2','experiment-2b6aaf144b03','experiment-da944d918670','experiment-998c378235ca','experiment-c1110c6ea972','experiment-bc7c415df33e','experiment-624e8ffbe4f8','experiment-3ddda30a12b7','experiment-ec1c9f7c7104','experiment-df098156516c')
  AND retrieval_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal'
  AND status = 'failed'
  AND error_code = 'evidence_pipeline_failure'
  AND raw_model_response IS NULL
  AND parse_status = 'not_invoked'
  AND NOT EXISTS (SELECT 1 FROM turin_qwen_v2_recovery_authorizations a WHERE a.original_run_id = experiment_runs.run_id);

INSERT INTO turin_formal_protocol_authorizations (authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version, plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json)
SELECT r.authorization_id, r.original_run_id, r.question_id, failed.retrieval_plan_id, failed.retrieval_plan_version, failed.retrieval_protocol_version,
       'turin-evidence-pipeline-v2.0-qwen-formal-recovery', failed.corpus_version, failed.retrieval_scope, failed.retrieval_run_classification,
       'qwen_evidence_pipeline_v2_preinference_recovery', 'qwen3:8b-q4_K_M',
       '{"temperature":0.2,"num_ctx":16384,"think":false,"stage_a_max_output_tokens":1500,"stage_b_max_output_tokens":1000,"stage_c_max_output_tokens":768}'::jsonb
FROM turin_qwen_v2_recovery_authorizations r
JOIN experiment_runs failed ON failed.run_id=r.original_run_id
WHERE NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a WHERE a.authorization_id=r.authorization_id);

COMMIT;