-- Append-only v1.5 schema enforcement of the existing concise response instruction.
BEGIN;

INSERT INTO turin_retrieval_protocol_amendments (protocol_version, supersedes_protocol_version, amendment_scope, amendment_json)
VALUES (
    'turin-retrieval-protocol-v1.5',
    'turin-retrieval-protocol-v1.4',
    'structured_response_contract_enforcement',
    '{"structured_output_max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"response_schema_version":"turin-archival-analysis-response-v1.5-concise","input_budget_chars":6000,"context_selection":"deterministic_max_min_fair_all_top_k","documentary_evidence_priority":true,"retrieval_changed":false,"corpus_changed":false,"model_changed":false,"prompt_changed":false,"governance_note":"Protocol v1.5 preserves v1.4 and machine-enforces the existing concise-response instruction only: answer and governed prose fields maxLength 180, each governed array maxItems 1. Technical identifiers remain unrestricted. No retrieval, corpus, prompt substance, model, sampling, context, timeout, persistence, repair, or provenance rule changes."}'::jsonb
)
ON CONFLICT (protocol_version) DO NOTHING;

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q07-ci3-v2-v15-contract-enforcement-pending',
    'CI3',
    'PENDING EVALUABLE RESULT — CI3-v2 + v1.5 STRUCTURED RESPONSE CONTRACT ENFORCEMENT',
    'Q07 CI3-v2/v1.4 remained non-evaluable after output exhaustion. v1.5 changes only the machine-enforced output envelope to match the unchanged concise prompt. CI3-v2 retrieval retains all six source snapshots independently of Granite response-array cardinality.'
WHERE NOT EXISTS (SELECT 1 FROM turin_question_governance_notes WHERE note_id = 'turin-q07-ci3-v2-v15-contract-enforcement-pending');

COMMIT;