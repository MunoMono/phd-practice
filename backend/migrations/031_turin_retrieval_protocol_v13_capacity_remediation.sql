BEGIN;

INSERT INTO turin_retrieval_protocol_amendments (protocol_version, supersedes_protocol_version, amendment_scope, amendment_json)
VALUES ('turin-retrieval-protocol-v1.3', 'turin-retrieval-protocol-v1.2', 'structured_output_capacity', '{"structured_output_max_tokens":1000,"temperature":0.0,"top_p":1.0,"do_sample":false,"response_schema_version":"turin-archival-analysis-response-v1","input_budget_chars":6000,"context_selection":"deterministic_max_min_fair_all_top_k","documentary_evidence_priority":true,"retrieval_changed":false,"corpus_changed":false,"model_changed":false,"governance_note":"Retrieval Protocol v1.3 increases only the structured-output capacity from 500 to 1000 tokens after Q06 empirically exhausted the v1.2 ceiling before completing the governed response schema. Retrieval, corpus, model, prompt substance, schema, sampling, context representation and provenance rules remain unchanged."}'::jsonb)
ON CONFLICT (protocol_version) DO NOTHING;

CREATE TABLE IF NOT EXISTS turin_question_governance_notes (
    note_id VARCHAR(255) PRIMARY KEY,
    question_id VARCHAR(64) NOT NULL,
    governance_status VARCHAR(128) NOT NULL,
    note_text TEXT NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE OR REPLACE FUNCTION reject_turin_question_governance_note_mutation() RETURNS TRIGGER AS $$ BEGIN RAISE EXCEPTION 'Turin question governance notes are append-only.'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS reject_turin_question_governance_note_update ON turin_question_governance_notes;
CREATE TRIGGER reject_turin_question_governance_note_update BEFORE UPDATE OR DELETE ON turin_question_governance_notes FOR EACH ROW EXECUTE FUNCTION reject_turin_question_governance_note_mutation();
INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT 'turin-q06-v13-capacity-remediation-pending', 'CI2', 'PENDING EVALUABLE RESULT — v1.3 CAPACITY REMEDIATION', 'Q06 remains non-evaluable pending a separately authorized v1.3 execution after the final hardened v1.2 run exhausted its structured-output capacity.'
WHERE EXISTS (SELECT 1 FROM turin_retrieval_protocol_amendments WHERE protocol_version = 'turin-retrieval-protocol-v1.3' AND amendment_json->>'structured_output_max_tokens' = '1000')
AND NOT EXISTS (SELECT 1 FROM turin_question_governance_notes WHERE note_id = 'turin-q06-v13-capacity-remediation-pending');

COMMIT;
