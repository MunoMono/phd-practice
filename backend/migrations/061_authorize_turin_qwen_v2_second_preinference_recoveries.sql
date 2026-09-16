BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
  DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
  ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
    (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal-recovery' AND authorization_category = 'qwen_evidence_pipeline_v2_preinference_recovery')
    OR (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND authorization_category IN ('qwen_evidence_pipeline_v2_primary', 'qwen_evidence_pipeline_v2_canonical_preinference_recovery', 'qwen_evidence_pipeline_v2_canonical_second_preinference_recovery'))
    OR execution_protocol_version NOT LIKE 'turin-evidence-pipeline-v2.0-qwen-formal%'
  );

CREATE TEMP TABLE turin_qwen_v2_second_recovery_bridge (
  primary_run_id VARCHAR(255) NOT NULL UNIQUE,
  first_recovery_run_id VARCHAR(255) PRIMARY KEY,
  second_authorization_id VARCHAR(255) NOT NULL UNIQUE
) ON COMMIT DROP;

INSERT INTO turin_qwen_v2_second_recovery_bridge (primary_run_id, first_recovery_run_id, second_authorization_id) VALUES
  ('experiment-fe59f8653b00', 'experiment-86d4723154b9', 'turin-qwen-v2-kr1-canonical-second-preinference-recovery-authorization'),
  ('experiment-166a3d05493b', 'experiment-7c541a085457', 'turin-qwen-v2-kr2-canonical-second-preinference-recovery-authorization'),
  ('experiment-1f711de966c2', 'experiment-ed2b071de782', 'turin-qwen-v2-kr3-canonical-second-preinference-recovery-authorization'),
  ('experiment-2b6aaf144b03', 'experiment-6a24ca8f40fc', 'turin-qwen-v2-kr4-canonical-second-preinference-recovery-authorization'),
  ('experiment-da944d918670', 'experiment-14e7ed243e4e', 'turin-qwen-v2-ci1-canonical-second-preinference-recovery-authorization'),
  ('experiment-998c378235ca', 'experiment-0951f03189d6', 'turin-qwen-v2-ci2-canonical-second-preinference-recovery-authorization'),
  ('experiment-c1110c6ea972', 'experiment-01cff2d67fe2', 'turin-qwen-v2-ci3-canonical-second-preinference-recovery-authorization'),
  ('experiment-bc7c415df33e', 'experiment-d143f72f959c', 'turin-qwen-v2-ci4-canonical-second-preinference-recovery-authorization'),
  ('experiment-624e8ffbe4f8', 'experiment-9b0568ebd9e8', 'turin-qwen-v2-sm1-canonical-second-preinference-recovery-authorization'),
  ('experiment-3ddda30a12b7', 'experiment-df1086a92f56', 'turin-qwen-v2-sm2-canonical-second-preinference-recovery-authorization'),
  ('experiment-ec1c9f7c7104', 'experiment-c0fdca9960ff', 'turin-qwen-v2-sm3-canonical-second-preinference-recovery-authorization'),
  ('experiment-df098156516c', 'experiment-8ffd3484796a', 'turin-qwen-v2-sm4-canonical-second-preinference-recovery-authorization');

DO $$
DECLARE eligible_count INTEGER;
BEGIN
  SELECT count(*) INTO eligible_count
  FROM turin_qwen_v2_second_recovery_bridge bridge
  JOIN experiment_runs first_recovery ON first_recovery.run_id = bridge.first_recovery_run_id
  JOIN experiment_runs primary_run ON primary_run.run_id = bridge.primary_run_id
  JOIN turin_formal_protocol_authorizations first_authorization ON first_authorization.authorization_id = first_recovery.formal_authorization_id
  WHERE first_recovery.recovery_of_run_id = bridge.primary_run_id
    AND first_recovery.recovery_category = 'infrastructure_failure_before_inference'
    AND first_recovery.status = 'failed'
    AND first_recovery.error_code = 'evidence_pipeline_failure'
    AND first_recovery.raw_model_response IS NULL
    AND first_recovery.raw_repair_response IS NULL
    AND first_recovery.inference_duration_ms = 0
    AND first_recovery.parse_status = 'not_invoked'
    AND COALESCE(jsonb_typeof(first_recovery.parsed_response_json), 'null') = 'null'
    AND COALESCE(jsonb_typeof(first_recovery.structured_response_json), 'null') = 'null'
    AND COALESCE(jsonb_typeof(first_recovery.provenance_validation_json), 'null') = 'null'
    AND COALESCE(jsonb_typeof(first_recovery.repair_generation_metadata_json), 'null') = 'null'
    AND COALESCE(jsonb_typeof(first_recovery.response_schema_json), 'null') = 'null'
    AND first_recovery.response_schema_version IS NULL
    AND first_recovery.response_schema_hash IS NULL
    AND first_recovery.generation_metadata_json = jsonb_build_object('protocol_fingerprint', 'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966')
    AND first_recovery.retrieval_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal'
    AND first_recovery.question_id = primary_run.question_id
    AND first_recovery.retrieval_plan_id = primary_run.retrieval_plan_id
    AND first_recovery.retrieval_plan_version = primary_run.retrieval_plan_version
    AND first_recovery.corpus_version = primary_run.corpus_version
    AND first_recovery.retrieval_scope = primary_run.retrieval_scope
    AND first_recovery.retrieval_run_classification = primary_run.retrieval_run_classification
    AND first_authorization.authorization_category = 'qwen_evidence_pipeline_v2_canonical_preinference_recovery';
  IF eligible_count <> 12 THEN
    RAISE EXCEPTION 'Expected exactly 12 governed Qwen V2 first-recovery pre-inference failures; found %.', eligible_count;
  END IF;
END;
$$;

INSERT INTO turin_formal_run_recoveries (recovery_of_run_id, plan_id, protocol_version, corpus_version, recovery_category)
SELECT first_recovery.run_id, first_recovery.retrieval_plan_id, first_recovery.retrieval_protocol_version, first_recovery.corpus_version, 'infrastructure_failure_before_inference'
FROM turin_qwen_v2_second_recovery_bridge bridge
JOIN experiment_runs first_recovery ON first_recovery.run_id = bridge.first_recovery_run_id;

INSERT INTO turin_formal_protocol_authorizations (authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version, plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json)
SELECT bridge.second_authorization_id, first_recovery.run_id, first_recovery.question_id, first_recovery.retrieval_plan_id, first_recovery.retrieval_plan_version, first_recovery.retrieval_protocol_version, first_recovery.retrieval_protocol_version, first_recovery.corpus_version, first_recovery.retrieval_scope, first_recovery.retrieval_run_classification, 'qwen_evidence_pipeline_v2_canonical_second_preinference_recovery', 'qwen3:8b-q4_K_M', first_authorization.model_parameters_json
FROM turin_qwen_v2_second_recovery_bridge bridge
JOIN experiment_runs first_recovery ON first_recovery.run_id = bridge.first_recovery_run_id
JOIN turin_formal_protocol_authorizations first_authorization ON first_authorization.authorization_id = first_recovery.formal_authorization_id;

DO $patch$
DECLARE live_function TEXT;
DECLARE marker TEXT := E'    ELSIF NEW.recovery_category = \'infrastructure_failure_before_inference\' THEN\n        IF NOT (';
DECLARE chained_shape TEXT := E'    ELSIF NEW.recovery_category = \'infrastructure_failure_before_inference\' THEN\n        IF NOT (\n            -- A single bounded Qwen retry is permitted only after the governed first recovery failed before inference.\n            (original_run.retrieval_protocol_version = \'turin-evidence-pipeline-v2.0-qwen-formal\' AND NEW.retrieval_protocol_version = \'turin-evidence-pipeline-v2.0-qwen-formal\' AND original_run.recovery_category = \'infrastructure_failure_before_inference\' AND original_run.recovery_of_run_id IS NOT NULL AND original_run.status = \'failed\' AND original_run.error_code = \'evidence_pipeline_failure\' AND original_run.model_name = \'qwen3:8b-q4_K_M\' AND original_run.inference_duration_ms = 0 AND original_run.raw_model_response IS NULL AND original_run.raw_repair_response IS NULL AND original_run.parse_status = \'not_invoked\' AND COALESCE(jsonb_typeof(original_run.parsed_response_json), \'null\') = \'null\' AND COALESCE(jsonb_typeof(original_run.structured_response_json), \'null\') = \'null\' AND COALESCE(jsonb_typeof(original_run.provenance_validation_json), \'null\') = \'null\' AND COALESCE(jsonb_typeof(original_run.repair_generation_metadata_json), \'null\') = \'null\' AND COALESCE(jsonb_typeof(original_run.response_schema_json), \'null\') = \'null\' AND original_run.response_schema_version IS NULL AND original_run.response_schema_hash IS NULL AND original_run.generation_metadata_json = jsonb_build_object(\'protocol_fingerprint\', \'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966\') AND EXISTS (SELECT 1 FROM turin_formal_run_recoveries chained_lineage WHERE chained_lineage.recovery_of_run_id = NEW.recovery_of_run_id AND chained_lineage.plan_id = NEW.retrieval_plan_id AND chained_lineage.protocol_version = NEW.retrieval_protocol_version AND chained_lineage.corpus_version = NEW.corpus_version AND chained_lineage.recovery_category = NEW.recovery_category) AND EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations second_auth WHERE second_auth.authorization_id = NEW.formal_authorization_id AND second_auth.prior_non_evaluable_run_id = NEW.recovery_of_run_id AND second_auth.question_id = NEW.question_id AND second_auth.plan_id = NEW.retrieval_plan_id AND second_auth.plan_version = NEW.retrieval_plan_version AND second_auth.plan_protocol_version = NEW.retrieval_protocol_version AND second_auth.execution_protocol_version = NEW.retrieval_protocol_version AND second_auth.corpus_version = NEW.corpus_version AND second_auth.retrieval_scope = NEW.retrieval_scope AND second_auth.run_classification = NEW.retrieval_run_classification AND second_auth.authorization_category = \'qwen_evidence_pipeline_v2_canonical_second_preinference_recovery\' AND second_auth.model_name = \'qwen3:8b-q4_K_M\'))\n            OR';
BEGIN
  SELECT pg_get_functiondef('validate_turin_failure_recovery()'::regprocedure) INTO live_function;
  IF position(marker IN live_function) <> 1 AND position(marker IN live_function) = 0 THEN
    RAISE EXCEPTION 'Live recovery function does not contain the expected post-060 pre-inference branch.';
  END IF;
  live_function := replace(live_function, marker, chained_shape);
  EXECUTE live_function;
END;
$patch$;

COMMIT;
