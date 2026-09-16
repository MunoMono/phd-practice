-- One append-only clean-primary authorization for the first governed Q07 / CI3 v1.3 execution.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    ALTER COLUMN prior_non_evaluable_run_id DROP NOT NULL,
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1' AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2' AND authorization_category IN ('protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion', 'infrastructure_recovery_after_v1_2_read_timeout', 'orphaned_inference_replacement_after_write_ahead_persistence_remediation'))
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.3' AND authorization_category IN ('protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion', 'q07_ci3_v13_primary_authorization'))
    ),
    ADD CONSTRAINT turin_formal_protocol_authorizations_q07_primary_lineage_check CHECK (
        (authorization_category = 'q07_ci3_v13_primary_authorization'
            AND prior_non_evaluable_run_id IS NULL
            AND replacement_incident_id IS NULL
            AND replacement_intended_run_id IS NULL)
        OR authorization_category <> 'q07_ci3_v13_primary_authorization'
    );

    CREATE OR REPLACE FUNCTION validate_turin_clean_primary_authorization()
    RETURNS TRIGGER AS $$
    BEGIN
      IF NEW.formal_authorization_id = 'turin-q07-ci3-v13-primary-authorization' THEN
        IF NEW.recovery_of_run_id IS NOT NULL
           OR NEW.recovery_category IS NOT NULL
           OR NEW.question_id <> 'CI3'
           OR NEW.retrieval_plan_id <> 'CI3-v1'
           OR NEW.retrieval_plan_version <> '1.0'
           OR NEW.retrieval_protocol_version <> 'turin-retrieval-protocol-v1.3'
           OR NEW.corpus_version <> 'corpus_f40d78dbce52'
           OR NEW.retrieval_scope <> 'corpus_wide'
           OR NEW.retrieval_run_classification <> 'primary'
           OR NEW.model_name <> 'granite3.1-dense:2b-instruct-q4_K_M'
           OR NEW.model_parameters_json <> '{"max_tokens":1000,"temperature":0.0,"top_p":1.0,"do_sample":false,"granite_timeout_seconds":1200}'::jsonb
           OR NOT EXISTS (
               SELECT 1 FROM turin_formal_protocol_authorizations auth_record
               WHERE auth_record.authorization_id = NEW.formal_authorization_id
                 AND auth_record.question_id = NEW.question_id
                 AND auth_record.plan_id = NEW.retrieval_plan_id
                 AND auth_record.plan_version = NEW.retrieval_plan_version
                 AND auth_record.execution_protocol_version = NEW.retrieval_protocol_version
                 AND auth_record.corpus_version = NEW.corpus_version
                 AND auth_record.authorization_category = 'q07_ci3_v13_primary_authorization'
           ) THEN
          RAISE EXCEPTION 'Q07 clean-primary execution requires its exact formal authorization and frozen identity.';
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS validate_turin_clean_primary_authorization_insert ON experiment_runs;
    CREATE TRIGGER validate_turin_clean_primary_authorization_insert
    BEFORE INSERT ON experiment_runs
    FOR EACH ROW EXECUTE FUNCTION validate_turin_clean_primary_authorization();

WITH prerequisites AS (
    SELECT 1
    WHERE EXISTS (
        SELECT 1
        FROM turin_retrieval_plans
        WHERE plan_id = 'CI3-v1'
          AND question_id = 'CI3'
          AND plan_version = '1.0'
          AND protocol_version = 'turin-retrieval-protocol-v1.0'
          AND researcher_approval_state = 'approved'
          AND run_classification = 'primary'
          AND plan_json->>'retrieval_scope' = 'corpus_wide'
          AND plan_json->>'top_k' = '5'
          AND plan_json->'lexical_facets' = '[{"facet_id":"unit","alternatives":["Design Education Unit","DEU"]},{"facet_id":"archive_context","alternatives":["DDR","Department of Design Research"]}]'::jsonb
          AND plan_json->'researcher_synonyms' = '[]'::jsonb
          AND plan_json->>'rationale' = 'Retrieves DEU material in its institutional context. Contemporary/retrospective classification is made after retrieval through document date, source type, provenance, and researcher assessment.'
    )
      AND EXISTS (
        SELECT 1
        FROM turin_retrieval_protocol_amendments
        WHERE protocol_version = 'turin-retrieval-protocol-v1.3'
          AND supersedes_protocol_version = 'turin-retrieval-protocol-v1.2'
          AND amendment_scope = 'structured_output_capacity'
          AND amendment_json->>'structured_output_max_tokens' = '1000'
    )
      AND EXISTS (
        SELECT 1
        FROM experiment_runs
        WHERE run_id = 'experiment-3fecb79f85d7'
          AND fixture_only = true
          AND retrieval_protocol_version = 'turin-retrieval-protocol-v1.3'
          AND status = 'completed'
          AND generation_metadata_json->>'max_tokens' = '1000'
          AND generation_metadata_json->>'granite_timeout_seconds' = '1200'
          AND (provenance_validation_json->>'valid')::boolean = true
    )
      AND (SELECT count(*) FROM experiment_runs WHERE question_id = 'CI3') = 0
      AND (SELECT count(*) FROM turin_formal_protocol_authorizations WHERE question_id = 'CI3') = 0
      AND (SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI4', 'SM1', 'SM2', 'SM3', 'SM4')) = 0
)
INSERT INTO turin_formal_protocol_authorizations (
    authorization_id, prior_non_evaluable_run_id, question_id, plan_id, plan_version,
    plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope,
    run_classification, authorization_category, model_name, model_parameters_json
)
SELECT
    'turin-q07-ci3-v13-primary-authorization', NULL, 'CI3', 'CI3-v1', '1.0',
    'turin-retrieval-protocol-v1.0', 'turin-retrieval-protocol-v1.3',
    'corpus_f40d78dbce52', 'corpus_wide', 'primary',
    'q07_ci3_v13_primary_authorization', 'granite3.1-dense:2b-instruct-q4_K_M',
    '{"max_tokens":1000,"temperature":0.0,"top_p":1.0,"do_sample":false,"granite_timeout_seconds":1200}'::jsonb
FROM prerequisites;

COMMIT;
