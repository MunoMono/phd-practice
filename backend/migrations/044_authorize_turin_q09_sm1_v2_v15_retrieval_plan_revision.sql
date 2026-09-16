-- One append-only authorization for a governed SM1 evidence-class retrieval-plan revision.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1' AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2' AND authorization_category IN ('protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion', 'infrastructure_recovery_after_v1_2_read_timeout', 'orphaned_inference_replacement_after_write_ahead_persistence_remediation'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.3' AND authorization_category IN ('protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion', 'q07_ci3_v13_primary_authorization'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.4' AND authorization_category = 'q07_ci3_v2_v14_primary_authorization')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.5' AND authorization_category IN ('q07_ci3_v2_v15_primary_authorization', 'q08_ci4_v15_primary_authorization', 'q09_sm1_v15_primary_authorization', 'q09_sm1_v2_v15_retrieval_plan_revision_authorization'))
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

CREATE OR REPLACE FUNCTION validate_turin_failure_recovery()
RETURNS TRIGGER AS $$
DECLARE original_run experiment_runs%ROWTYPE;
BEGIN
    IF NEW.recovery_of_run_id IS NULL AND NEW.recovery_category IS NULL THEN
        PERFORM pg_advisory_xact_lock(hashtext(COALESCE(NEW.question_id, '') || COALESCE(NEW.retrieval_protocol_version, '')));
        IF NEW.formal_authorization_id = 'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization' THEN
            IF NEW.question_id <> 'SM1'
               OR NEW.retrieval_plan_id <> 'SM1-v2'
               OR NEW.retrieval_plan_version <> '2.0'
               OR NEW.retrieval_protocol_version <> 'turin-retrieval-protocol-v1.5'
               OR NEW.corpus_version <> 'corpus_f40d78dbce52'
               OR NEW.retrieval_scope <> 'corpus_wide'
               OR NEW.retrieval_run_classification <> 'primary'
               OR NOT EXISTS (
                                     SELECT 1 FROM turin_formal_protocol_authorizations authorization_record
                                     WHERE authorization_record.authorization_id = NEW.formal_authorization_id
                                         AND authorization_record.question_id = 'SM1'
                                         AND authorization_record.plan_id = 'SM1-v2'
                                         AND authorization_record.plan_version = '2.0'
                                         AND authorization_record.execution_protocol_version = 'turin-retrieval-protocol-v1.5'
                                         AND authorization_record.corpus_version = 'corpus_f40d78dbce52'
                                         AND authorization_record.retrieval_scope = 'corpus_wide'
                                         AND authorization_record.run_classification = 'primary'
                                         AND authorization_record.authorization_category = 'q09_sm1_v2_v15_retrieval_plan_revision_authorization'
               )
               OR NOT EXISTS (
                   SELECT 1 FROM experiment_runs historical
                   WHERE historical.run_id = 'experiment-fd6db9dfa85f'
                     AND historical.question_id = 'SM1'
                     AND historical.retrieval_plan_id = 'SM1-v1'
                     AND historical.retrieval_plan_version = '1.0'
                     AND historical.retrieval_protocol_version = 'turin-retrieval-protocol-v1.5'
                     AND historical.formal_authorization_id = 'turin-q09-sm1-v1-v15-primary-authorization'
                     AND historical.status IN ('completed', 'completed_with_missingness')
               ) THEN
                RAISE EXCEPTION 'SM1-v2 requires its exact retrieval-plan-revision authorization and preserved SM1-v1 result.';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.retrieval_run_classification = 'primary' AND NEW.retrieval_scope = 'corpus_wide' AND EXISTS (SELECT 1 FROM experiment_runs prior LEFT JOIN turin_formal_run_invalidations invalidation ON invalidation.invalidated_run_id = prior.run_id WHERE prior.question_id = NEW.question_id AND prior.retrieval_protocol_version = NEW.retrieval_protocol_version AND (prior.status IN ('completed', 'completed_with_missingness') OR prior.raw_model_response IS NOT NULL OR COALESCE(jsonb_typeof(prior.structured_response_json), 'null') <> 'null' OR COALESCE(jsonb_typeof(prior.provenance_validation_json), 'null') <> 'null') AND invalidation.invalidated_run_id IS NULL) THEN RAISE EXCEPTION 'An evaluable primary result already exists for this question and protocol.'; END IF;
        RETURN NEW;
    END IF;
    IF NEW.recovery_of_run_id IS NULL THEN RAISE EXCEPTION 'Formal recovery requires complete lineage.'; END IF;
    SELECT * INTO original_run FROM experiment_runs WHERE run_id = NEW.recovery_of_run_id;
    IF NOT FOUND OR NEW.question_id <> original_run.question_id OR NEW.retrieval_plan_id <> original_run.retrieval_plan_id OR NEW.retrieval_plan_version <> original_run.retrieval_plan_version OR NEW.corpus_version <> original_run.corpus_version OR NEW.retrieval_scope <> original_run.retrieval_scope OR NEW.retrieval_run_classification <> original_run.retrieval_run_classification THEN RAISE EXCEPTION 'Recovery must use the identical question, plan, corpus, scope, and classification.'; END IF;
    IF NEW.recovery_category = 'protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion' THEN
        IF original_run.run_id <> 'experiment-cb1d519cd8ad' OR original_run.retrieval_protocol_version <> 'turin-retrieval-protocol-v1.2' OR NEW.retrieval_protocol_version <> 'turin-retrieval-protocol-v1.3' OR original_run.status <> 'failed' OR original_run.error_code <> 'output_token_exhaustion' OR original_run.raw_model_response IS NULL OR original_run.parse_status <> 'failed_with_safe_response' OR (original_run.generation_metadata_json->>'eval_count')::integer <> 500 OR original_run.generation_metadata_json->>'done_reason' <> 'length' OR original_run.generation_metadata_json->>'max_tokens' <> '500' THEN RAISE EXCEPTION 'Recovery source is not the governed Q06 v1.2 structured-output capacity failure.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a WHERE a.authorization_id = NEW.formal_authorization_id AND a.prior_non_evaluable_run_id = NEW.recovery_of_run_id AND a.question_id = NEW.question_id AND a.plan_id = NEW.retrieval_plan_id AND a.execution_protocol_version = NEW.retrieval_protocol_version AND a.corpus_version = NEW.corpus_version AND a.authorization_category = NEW.recovery_category AND a.model_parameters_json = NEW.model_parameters_json) THEN RAISE EXCEPTION 'Q06 v1.3 recovery requires its exact formal authorization and model configuration.'; END IF;
    ELSIF NEW.recovery_category = 'infrastructure_recovery_after_v1_2_read_timeout' THEN
        IF original_run.run_id <> 'experiment-3643a4fc2fb0' OR original_run.retrieval_protocol_version <> NEW.retrieval_protocol_version OR original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure' OR original_run.error_message NOT LIKE 'ReadTimeout:%' OR original_run.raw_model_response IS NOT NULL OR original_run.parse_status <> 'not_invoked' THEN RAISE EXCEPTION 'Recovery source is not the governed Q06 no-output ReadTimeout incident.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a WHERE a.authorization_id = NEW.formal_authorization_id AND a.prior_non_evaluable_run_id = NEW.recovery_of_run_id AND a.question_id = NEW.question_id AND a.plan_id = NEW.retrieval_plan_id AND a.execution_protocol_version = NEW.retrieval_protocol_version AND a.corpus_version = NEW.corpus_version AND a.authorization_category = NEW.recovery_category) OR EXISTS (SELECT 1 FROM turin_execution_incidents i WHERE i.authorization_id = NEW.formal_authorization_id) THEN RAISE EXCEPTION 'Recovery requires an unspent exact formal authorization.'; END IF;
    ELSIF NEW.recovery_category = 'orphaned_inference_replacement_after_write_ahead_persistence_remediation' THEN
        IF original_run.run_id <> 'experiment-3643a4fc2fb0' OR original_run.retrieval_protocol_version <> NEW.retrieval_protocol_version OR NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations a JOIN turin_execution_incidents i ON i.incident_id = a.replacement_incident_id WHERE a.authorization_id = NEW.formal_authorization_id AND a.authorization_category = NEW.recovery_category AND i.incident_id = 'turin-q06-v12-orphaned-inference-incident' AND i.intended_run_id = 'experiment-2604c21d4d1b' AND i.parent_run_id = NEW.recovery_of_run_id AND i.granite_http_status = 200 AND i.raw_response_durably_persisted = false) THEN RAISE EXCEPTION 'Replacement requires its exact orphaned-inference authorization and incident lineage.'; END IF;
    ELSIF NEW.recovery_category = 'infrastructure_failure_before_inference' THEN
        IF original_run.retrieval_protocol_version <> NEW.retrieval_protocol_version OR original_run.status <> 'failed' OR original_run.error_code <> 'granite_failure' OR original_run.raw_model_response IS NOT NULL OR original_run.model_name IS NOT NULL OR original_run.inference_duration_ms IS NOT NULL OR original_run.parse_status <> 'not_invoked' OR NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery source is not an authorized failed-before-inference infrastructure attempt.'; END IF;
    ELSIF NEW.recovery_category = 'instrument_implementation_correction' THEN
        IF original_run.retrieval_protocol_version <> NEW.retrieval_protocol_version OR original_run.status <> 'failed' OR original_run.error_code <> 'provenance_validation_failure' OR original_run.raw_model_response IS NULL OR NOT EXISTS (SELECT 1 FROM turin_formal_run_invalidations invalidation WHERE invalidation.invalidated_run_id = original_run.run_id AND invalidation.invalidation_category = 'instrument_implementation_correction' AND invalidation.defect_code = 'citation_contract_ambiguity' AND invalidation.plan_id = NEW.retrieval_plan_id AND invalidation.protocol_version = NEW.retrieval_protocol_version AND invalidation.corpus_version = NEW.corpus_version AND invalidation.model_name = NEW.model_name AND invalidation.max_tokens = (NEW.model_parameters_json->>'max_tokens')::integer AND invalidation.temperature = (NEW.model_parameters_json->>'temperature')::double precision AND invalidation.top_p = (NEW.model_parameters_json->>'top_p')::double precision AND invalidation.do_sample = (NEW.model_parameters_json->>'do_sample')::boolean) THEN RAISE EXCEPTION 'Recovery source is not a documented instrument implementation defect with identical governed model configuration.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.'; END IF;
    ELSE
        RAISE EXCEPTION 'Unsupported formal recovery category.';
    END IF;
    IF EXISTS (SELECT 1 FROM experiment_runs prior WHERE prior.recovery_of_run_id = NEW.recovery_of_run_id) THEN RAISE EXCEPTION 'Only one formal recovery execution is permitted for a recovery source.'; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization-rationale',
    'SM1',
    'AUTHORIZED FOR ONE FORMAL EXECUTION — SM1-v2 RETRIEVAL-PLAN REVISION',
    'SM1-v1 completed as an evaluable primary run but demonstrated a retrieval-plan evidence-class coverage failure: the corpus-wide search reached all 12,884 frozen chunks, yet later participant testimony relevant to motive ranked outside top-k. SM1-v2 is an append-only retrieval-plan revision that preserves the contemporary decision/process evidence class while adding deterministic retrospective participant stratification. This authorization permits one governed re-execution to evaluate the same research question against the corrected evidence-class architecture.'
WHERE NOT EXISTS (
    SELECT 1 FROM turin_question_governance_notes
    WHERE note_id = 'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization-rationale'
);

INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
    plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
    run_classification, authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization', NULL, 'SM1', 'SM1-v2', '2.0',
    'turin-retrieval-protocol-v1.0', 'turin-retrieval-protocol-v1.5',
    'corpus_f40d78dbce52', 'corpus_wide', 'primary',
    'q09_sm1_v2_v15_retrieval_plan_revision_authorization', 'granite3.1-dense:2b-instruct-q4_K_M',
    '{"max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"granite_timeout_seconds":1200}'::jsonb
WHERE EXISTS (
    SELECT 1 FROM turin_retrieval_plans
    WHERE plan_id = 'SM1-v2'
      AND question_id = 'SM1'
      AND plan_version = '2.0'
      AND protocol_version = 'turin-retrieval-protocol-v1.0'
      AND researcher_approval_state = 'approved'
    AND plan_json->>'retrieval_scope' = 'corpus_wide'
      AND run_classification = 'primary'
      AND supersedes_plan_id = 'SM1-v1'
      AND plan_json->>'top_k' = '6'
    AND jsonb_array_length(plan_json->'temporal_strata') = 2
    AND plan_json->'temporal_strata' @> '[{"stratum_id":"contemporary","classification":"contemporary DDR document","top_k":3,"year_to":1985,"source_type":"any"},{"stratum_id":"retrospective","classification":"later retrospective account","top_k":3,"year_from":1986,"source_type":"oral_history","lexical_facets":[{"facet_id":"retrospective_institutional_fate","alternatives":["\\\"future of design research\\\"","\\\"close the DDR\\\"","\\\"DDR closing\\\""]}]}]'::jsonb
      AND plan_json->'authority_linked_document_ids' = '[]'::jsonb
      AND plan_json->'authority_document_link_ids' = '[]'::jsonb
)
AND EXISTS (
    SELECT 1 FROM experiment_runs
    WHERE run_id = 'experiment-fd6db9dfa85f'
      AND question_id = 'SM1'
      AND retrieval_plan_id = 'SM1-v1'
      AND retrieval_plan_version = '1.0'
      AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.5'
      AND corpus_version = 'corpus_f40d78dbce52'
      AND status IN ('completed', 'completed_with_missingness')
)
AND EXISTS (
    SELECT 1 FROM turin_retrieval_protocol_amendments
    WHERE protocol_version = 'turin-retrieval-protocol-v1.5'
      AND amendment_json->>'structured_output_max_tokens' = '1500'
      AND amendment_json->>'response_schema_version' = 'turin-archival-analysis-response-v1.5-concise'
)
AND NOT EXISTS (
    SELECT 1 FROM turin_formal_protocol_authorizations
    WHERE authorization_id = 'turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization'
)
AND NOT EXISTS (
    SELECT 1 FROM experiment_runs
    WHERE retrieval_plan_id = 'SM1-v2' AND fixture_only = false
)
AND NOT EXISTS (
    SELECT 1 FROM experiment_runs WHERE question_id IN ('SM2', 'SM3', 'SM4')
);

COMMIT;