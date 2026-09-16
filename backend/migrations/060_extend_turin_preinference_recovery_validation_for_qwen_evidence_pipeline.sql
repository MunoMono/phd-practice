BEGIN;

CREATE OR REPLACE FUNCTION public.validate_turin_failure_recovery()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
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
        IF NOT (
            (original_run.retrieval_protocol_version = NEW.retrieval_protocol_version AND original_run.status = 'failed' AND original_run.error_code = 'granite_failure' AND original_run.raw_model_response IS NULL AND original_run.model_name IS NULL AND original_run.inference_duration_ms IS NULL AND original_run.parse_status = 'not_invoked' AND EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category))
            OR
            -- Qwen's model identity and zero duration are write-ahead metadata, not an inference marker.
            (original_run.retrieval_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND NEW.retrieval_protocol_version = 'turin-evidence-pipeline-v2.0-qwen-formal' AND original_run.status = 'failed' AND original_run.error_code = 'evidence_pipeline_failure' AND original_run.model_name = 'qwen3:8b-q4_K_M' AND original_run.inference_duration_ms = 0 AND original_run.raw_model_response IS NULL AND original_run.raw_repair_response IS NULL AND original_run.parse_status = 'not_invoked' AND COALESCE(jsonb_typeof(original_run.parsed_response_json), 'null') = 'null' AND COALESCE(jsonb_typeof(original_run.structured_response_json), 'null') = 'null' AND COALESCE(jsonb_typeof(original_run.provenance_validation_json), 'null') = 'null' AND COALESCE(jsonb_typeof(original_run.repair_generation_metadata_json), 'null') = 'null' AND COALESCE(jsonb_typeof(original_run.response_schema_json), 'null') = 'null' AND original_run.response_schema_version IS NULL AND original_run.response_schema_hash IS NULL AND original_run.generation_metadata_json = jsonb_build_object('protocol_fingerprint', 'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966') AND original_run.formal_authorization_id = 'turin-qwen-v2-' || lower(original_run.question_id) || '-authorization' AND EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) AND EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations canonical_auth JOIN turin_qwen_v2_recovery_authorizations supplemental_auth ON supplemental_auth.original_run_id = original_run.run_id WHERE canonical_auth.authorization_id = NEW.formal_authorization_id AND canonical_auth.prior_non_evaluable_run_id = NEW.recovery_of_run_id AND canonical_auth.question_id = NEW.question_id AND canonical_auth.plan_id = NEW.retrieval_plan_id AND canonical_auth.plan_version = NEW.retrieval_plan_version AND canonical_auth.plan_protocol_version = NEW.retrieval_protocol_version AND canonical_auth.execution_protocol_version = NEW.retrieval_protocol_version AND canonical_auth.corpus_version = NEW.corpus_version AND canonical_auth.retrieval_scope = NEW.retrieval_scope AND canonical_auth.run_classification = NEW.retrieval_run_classification AND canonical_auth.authorization_category = 'qwen_evidence_pipeline_v2_canonical_preinference_recovery' AND canonical_auth.model_name = 'qwen3:8b-q4_K_M' AND supplemental_auth.authorization_id = 'turin-qwen-v2-' || lower(original_run.question_id) || '-preinference-recovery' AND supplemental_auth.question_id = original_run.question_id AND supplemental_auth.recovery_reason = NEW.recovery_category AND supplemental_auth.inference_started = false AND supplemental_auth.configuration_fingerprint = 'f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966'))
        ) THEN RAISE EXCEPTION 'Recovery source is not an authorized failed-before-inference infrastructure attempt.'; END IF;
    ELSIF NEW.recovery_category = 'instrument_implementation_correction' THEN
        IF original_run.retrieval_protocol_version <> NEW.retrieval_protocol_version OR original_run.status <> 'failed' OR original_run.error_code <> 'provenance_validation_failure' OR original_run.raw_model_response IS NULL OR NOT EXISTS (SELECT 1 FROM turin_formal_run_invalidations invalidation WHERE invalidation.invalidated_run_id = original_run.run_id AND invalidation.invalidation_category = 'instrument_implementation_correction' AND invalidation.defect_code = 'citation_contract_ambiguity' AND invalidation.plan_id = NEW.retrieval_plan_id AND invalidation.protocol_version = NEW.retrieval_protocol_version AND invalidation.corpus_version = NEW.corpus_version AND invalidation.model_name = NEW.model_name AND invalidation.max_tokens = (NEW.model_parameters_json->>'max_tokens')::integer AND invalidation.temperature = (NEW.model_parameters_json->>'temperature')::double precision AND invalidation.top_p = (NEW.model_parameters_json->>'top_p')::double precision AND invalidation.do_sample = (NEW.model_parameters_json->>'do_sample')::boolean) THEN RAISE EXCEPTION 'Recovery source is not a documented instrument implementation defect with identical governed model configuration.'; END IF;
        IF NOT EXISTS (SELECT 1 FROM turin_formal_run_recoveries audit_record WHERE audit_record.recovery_of_run_id = NEW.recovery_of_run_id AND audit_record.plan_id = NEW.retrieval_plan_id AND audit_record.protocol_version = NEW.retrieval_protocol_version AND audit_record.corpus_version = NEW.corpus_version AND audit_record.recovery_category = NEW.recovery_category) THEN RAISE EXCEPTION 'Recovery requires an append-only authorized recovery record.'; END IF;
    ELSE
        RAISE EXCEPTION 'Unsupported formal recovery category.';
    END IF;
    IF EXISTS (SELECT 1 FROM experiment_runs prior WHERE prior.recovery_of_run_id = NEW.recovery_of_run_id) THEN RAISE EXCEPTION 'Only one formal recovery execution is permitted for a recovery source.'; END IF;
    RETURN NEW;
END;
$function$;

COMMIT;
