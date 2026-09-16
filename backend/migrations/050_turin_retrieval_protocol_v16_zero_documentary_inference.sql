-- Append-only v1.6 capability for explicitly authorized zero-documentary inference tests.
BEGIN;

ALTER TABLE turin_formal_protocol_authorizations
    ADD COLUMN IF NOT EXISTS allow_zero_documentary_inference BOOLEAN NOT NULL DEFAULT false;

INSERT INTO turin_retrieval_protocol_amendments (
    protocol_version, supersedes_protocol_version, amendment_scope, amendment_json
)
SELECT
    'turin-retrieval-protocol-v1.6',
    'turin-retrieval-protocol-v1.5',
    'zero_documentary_evidence_inference',
    '{"inherits":"turin-retrieval-protocol-v1.5","structured_output_max_tokens":1500,"response_schema_version":"turin-archival-analysis-response-v1.5-concise","prompt_changed":false,"context_ceiling_chars":6000,"granite_timeout_seconds":1200,"allow_zero_documentary_inference":true,"requires_explicit_authorization":true,"default_allow_zero_documentary_inference":false,"zero_documentary_context":"DOCUMENTARY EVIDENCE: No documentary passages were retrieved for this question.","authority_context_label":"ARCHIVE / DATABASE AUTHORITY CONTEXT — NOT DOCUMENTARY EVIDENCE","evidence_must_be_empty_when_no_documentary_passages":true,"raw_before_parse":true,"write_ahead":true,"allow_repair":false}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM turin_retrieval_protocol_amendments
    WHERE protocol_version = 'turin-retrieval-protocol-v1.6'
);

COMMIT;