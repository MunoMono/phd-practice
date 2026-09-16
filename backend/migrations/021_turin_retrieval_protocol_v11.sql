-- Retrieval Protocol v1.1: deterministic all-source context representation and output instrumentation.
CREATE TABLE IF NOT EXISTS turin_retrieval_protocol_amendments (
    protocol_version VARCHAR(128) PRIMARY KEY,
    supersedes_protocol_version VARCHAR(128) NOT NULL,
    amendment_scope VARCHAR(128) NOT NULL,
    approved_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    amendment_json JSONB NOT NULL
);

INSERT INTO turin_retrieval_protocol_amendments (
    protocol_version, supersedes_protocol_version, amendment_scope, amendment_json
) VALUES (
    'turin-retrieval-protocol-v1.1',
    'turin-retrieval-protocol-v1.0',
    'context_assembly_and_output_instrumentation',
    '{"context_selection":"deterministic_max_min_fair_all_top_k","documentary_evidence_priority":true,"input_budget_chars":6000,"native_json_schema_output":true}'::jsonb
) ON CONFLICT (protocol_version) DO NOTHING;

CREATE OR REPLACE FUNCTION reject_turin_protocol_amendment_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin retrieval protocol amendments are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_protocol_amendment_update ON turin_retrieval_protocol_amendments;
CREATE TRIGGER reject_turin_protocol_amendment_update
BEFORE UPDATE OR DELETE ON turin_retrieval_protocol_amendments
FOR EACH ROW EXECUTE FUNCTION reject_turin_protocol_amendment_mutation();

ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS generation_metadata_json JSONB,
    ADD COLUMN IF NOT EXISTS repair_generation_metadata_json JSONB,
    ADD COLUMN IF NOT EXISTS response_schema_json JSONB,
    ADD COLUMN IF NOT EXISTS response_schema_version VARCHAR(128),
    ADD COLUMN IF NOT EXISTS response_schema_hash VARCHAR(128),
    ADD COLUMN IF NOT EXISTS display_response_json JSONB;