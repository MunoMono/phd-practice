BEGIN;

-- Migration 058 remains the immutable supplemental authorization record. These
-- canonical rows are the trigger-governed bridge for the same twelve originals.
ALTER TABLE turin_formal_protocol_authorizations
  DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
  ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
    (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal-recovery' AND authorization_category = 'qwen_evidence_pipeline_v2_preinference_recovery')
    OR (execution_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND authorization_category IN ('qwen_evidence_pipeline_v2_primary', 'qwen_evidence_pipeline_v2_canonical_preinference_recovery'))
    OR execution_protocol_version NOT LIKE 'turin-evidence-pipeline-v2.0-qwen-formal%'
  );

CREATE TEMP TABLE turin_qwen_v2_canonical_recovery_bridge (
  original_run_id VARCHAR(255) PRIMARY KEY,
  supplemental_authorization_id VARCHAR(255) NOT NULL UNIQUE,
  canonical_authorization_id VARCHAR(255) NOT NULL UNIQUE
) ON COMMIT DROP;

INSERT INTO turin_qwen_v2_canonical_recovery_bridge (
  original_run_id, supplemental_authorization_id, canonical_authorization_id
) VALUES
  ('experiment-fe59f8653b00', 'turin-qwen-v2-kr1-preinference-recovery', 'turin-qwen-v2-kr1-canonical-preinference-recovery-authorization'),
  ('experiment-166a3d05493b', 'turin-qwen-v2-kr2-preinference-recovery', 'turin-qwen-v2-kr2-canonical-preinference-recovery-authorization'),
  ('experiment-1f711de966c2', 'turin-qwen-v2-kr3-preinference-recovery', 'turin-qwen-v2-kr3-canonical-preinference-recovery-authorization'),
  ('experiment-2b6aaf144b03', 'turin-qwen-v2-kr4-preinference-recovery', 'turin-qwen-v2-kr4-canonical-preinference-recovery-authorization'),
  ('experiment-da944d918670', 'turin-qwen-v2-ci1-preinference-recovery', 'turin-qwen-v2-ci1-canonical-preinference-recovery-authorization'),
  ('experiment-998c378235ca', 'turin-qwen-v2-ci2-preinference-recovery', 'turin-qwen-v2-ci2-canonical-preinference-recovery-authorization'),
  ('experiment-c1110c6ea972', 'turin-qwen-v2-ci3-preinference-recovery', 'turin-qwen-v2-ci3-canonical-preinference-recovery-authorization'),
  ('experiment-bc7c415df33e', 'turin-qwen-v2-ci4-preinference-recovery', 'turin-qwen-v2-ci4-canonical-preinference-recovery-authorization'),
  ('experiment-624e8ffbe4f8', 'turin-qwen-v2-sm1-preinference-recovery', 'turin-qwen-v2-sm1-canonical-preinference-recovery-authorization'),
  ('experiment-3ddda30a12b7', 'turin-qwen-v2-sm2-preinference-recovery', 'turin-qwen-v2-sm2-canonical-preinference-recovery-authorization'),
  ('experiment-ec1c9f7c7104', 'turin-qwen-v2-sm3-preinference-recovery', 'turin-qwen-v2-sm3-canonical-preinference-recovery-authorization'),
  ('experiment-df098156516c', 'turin-qwen-v2-sm4-preinference-recovery', 'turin-qwen-v2-sm4-canonical-preinference-recovery-authorization');

DO $$
DECLARE eligible_count INTEGER;
BEGIN
  SELECT count(*) INTO eligible_count
  FROM turin_qwen_v2_canonical_recovery_bridge bridge
  JOIN turin_qwen_v2_recovery_authorizations supplemental
    ON supplemental.authorization_id = bridge.supplemental_authorization_id
   AND supplemental.original_run_id = bridge.original_run_id
   AND supplemental.recovery_reason = 'infrastructure_failure_before_inference'
   AND supplemental.inference_started = false
   AND supplemental.configuration_fingerprint = 'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966'
  JOIN experiment_runs original ON original.run_id = bridge.original_run_id
  WHERE original.retrieval_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal'
    AND original.status = 'failed'
    AND original.error_code = 'evidence_pipeline_failure'
    AND original.raw_model_response IS NULL
    AND original.model_name = 'qwen3:8b-q4_K_M'
    AND original.inference_duration_ms = 0
    AND original.parse_status = 'not_invoked';
  IF eligible_count <> 12 THEN
    RAISE EXCEPTION 'Expected 12 untouched Qwen V2 pre-inference failures with matching migration-058 supplemental authorization; found %.', eligible_count;
  END IF;
END;
$$;

INSERT INTO turin_formal_run_recoveries (
  recovery_of_run_id, plan_id, protocol_version, corpus_version, recovery_category
)
SELECT original.run_id, original.retrieval_plan_id, original.retrieval_protocol_version,
       original.corpus_version, 'infrastructure_failure_before_inference'
FROM turin_qwen_v2_canonical_recovery_bridge bridge
JOIN experiment_runs original ON original.run_id = bridge.original_run_id
WHERE NOT EXISTS (
  SELECT 1 FROM turin_formal_run_recoveries existing
  WHERE existing.recovery_of_run_id = original.run_id
);

INSERT INTO turin_formal_protocol_authorizations (
  authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
  plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
  run_classification, authorization_category, model_name, model_parameters_json
)
SELECT bridge.canonical_authorization_id, original.run_id, original.question_id,
       original.retrieval_plan_id, original.retrieval_plan_version,
       original.retrieval_protocol_version, original.retrieval_protocol_version,
       original.corpus_version, original.retrieval_scope,
       original.retrieval_run_classification,
       'qwen_evidence_pipeline_v2_canonical_preinference_recovery',
       'qwen3:8b-q4_K_M',
       supplemental_formal.model_parameters_json
FROM turin_qwen_v2_canonical_recovery_bridge bridge
JOIN experiment_runs original ON original.run_id = bridge.original_run_id
JOIN turin_formal_protocol_authorizations supplemental_formal
  ON supplemental_formal.authorization_id = bridge.supplemental_authorization_id
WHERE NOT EXISTS (
  SELECT 1 FROM turin_formal_protocol_authorizations existing
  WHERE existing.authorization_id = bridge.canonical_authorization_id
);

DO $$
DECLARE lineage_count INTEGER;
DECLARE authorization_count INTEGER;
BEGIN
  SELECT count(*) INTO lineage_count
  FROM turin_formal_run_recoveries recovery
  JOIN turin_qwen_v2_canonical_recovery_bridge bridge
    ON bridge.original_run_id = recovery.recovery_of_run_id;
  SELECT count(*) INTO authorization_count
  FROM turin_formal_protocol_authorizations auth
  JOIN turin_qwen_v2_canonical_recovery_bridge bridge
    ON bridge.canonical_authorization_id = auth.authorization_id;
  IF lineage_count <> 12 OR authorization_count <> 12 THEN
    RAISE EXCEPTION 'Canonical Qwen V2 bridge must contain exactly 12 lineage rows and 12 authorization rows; found % and %.', lineage_count, authorization_count;
  END IF;
END;
$$;

COMMIT;