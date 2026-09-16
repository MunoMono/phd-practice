-- Retrieval Protocol v1.2: prospective structured-output capacity amendment.
INSERT INTO turin_retrieval_protocol_amendments (
    protocol_version, supersedes_protocol_version, amendment_scope, amendment_json
) VALUES (
    'turin-retrieval-protocol-v1.2',
    'turin-retrieval-protocol-v1.1',
    'structured_output_capacity',
    '{"structured_output_max_tokens":500,"temperature":0.0,"top_p":1.0,"do_sample":false,"response_schema_version":"turin-archival-analysis-response-v1","input_budget_chars":6000,"context_selection":"deterministic_max_min_fair_all_top_k","documentary_evidence_priority":true,"retrieval_changed":false,"corpus_changed":false,"model_changed":false}'::jsonb
) ON CONFLICT (protocol_version) DO NOTHING;