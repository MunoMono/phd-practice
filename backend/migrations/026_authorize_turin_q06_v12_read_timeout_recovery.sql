-- Prepare the governed Q06 v1.2 ReadTimeout recovery category without authorizing a run.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    DROP CONSTRAINT IF EXISTS turin_formal_protocol_authorizations_governed_pair_check,
    ADD CONSTRAINT turin_formal_protocol_authorizations_governed_pair_check CHECK (
        (execution_protocol_version = 'turin-retrieval-protocol-v1.1'
            AND authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning')
        OR (execution_protocol_version = 'turin-retrieval-protocol-v1.2'
            AND authorization_category IN (
                'protocol_v1_2_reexecution_after_v1_1_output_token_exhaustion',
                'infrastructure_recovery_after_v1_2_read_timeout'
            ))
    );

DROP INDEX IF EXISTS idx_turin_formal_protocol_authorization_question_execution;
CREATE UNIQUE INDEX idx_turin_formal_protocol_authorization_question_execution_category
    ON turin_formal_protocol_authorizations(question_id, execution_protocol_version, authorization_category);

COMMIT;