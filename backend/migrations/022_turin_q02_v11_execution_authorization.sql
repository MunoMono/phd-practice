-- One append-only authorization for the first formal Q02 execution under the v1.1 amendment.
CREATE TABLE IF NOT EXISTS turin_formal_protocol_authorizations (
    authorization_id VARCHAR(255) PRIMARY KEY,
    prior_non_evaluable_run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL,
    plan_id VARCHAR(255) NOT NULL,
    plan_version VARCHAR(128) NOT NULL,
    plan_protocol_version VARCHAR(128) NOT NULL,
    execution_protocol_version VARCHAR(128) NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    retrieval_scope VARCHAR(64) NOT NULL,
    run_classification VARCHAR(64) NOT NULL,
    authorization_category VARCHAR(128) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    model_parameters_json JSONB NOT NULL,
    authorized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (authorization_category = 'protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning'),
    CHECK (execution_protocol_version = 'turin-retrieval-protocol-v1.1'),
    CHECK (retrieval_scope = 'corpus_wide'),
    CHECK (run_classification = 'primary')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_turin_formal_protocol_authorization_question_execution
    ON turin_formal_protocol_authorizations(question_id, execution_protocol_version);

CREATE OR REPLACE FUNCTION reject_turin_protocol_authorization_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin formal protocol authorizations are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_protocol_authorization_update ON turin_formal_protocol_authorizations;
CREATE TRIGGER reject_turin_protocol_authorization_update
BEFORE UPDATE OR DELETE ON turin_formal_protocol_authorizations
FOR EACH ROW EXECUTE FUNCTION reject_turin_protocol_authorization_mutation();

ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS formal_authorization_id VARCHAR(255) REFERENCES turin_formal_protocol_authorizations(authorization_id);