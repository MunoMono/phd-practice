-- Append-only research audit note closing Q06 after its governed structured-output capacity failure.
BEGIN;

CREATE TABLE IF NOT EXISTS turin_research_incident_notes (
    note_id VARCHAR(255) PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL UNIQUE REFERENCES experiment_runs(run_id) ON DELETE RESTRICT,
    question_id VARCHAR(64) NOT NULL,
    incident_category VARCHAR(128) NOT NULL CHECK (incident_category = 'structured_output_capacity_limitation'),
    note_text TEXT NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION reject_turin_research_incident_note_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Turin research incident notes are append-only.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reject_turin_research_incident_note_update ON turin_research_incident_notes;
CREATE TRIGGER reject_turin_research_incident_note_update
BEFORE UPDATE OR DELETE ON turin_research_incident_notes
FOR EACH ROW EXECUTE FUNCTION reject_turin_research_incident_note_mutation();

INSERT INTO turin_research_incident_notes (note_id, run_id, question_id, incident_category, note_text)
SELECT
    'turin-q06-structured-output-capacity-closure',
    'experiment-cb1d519cd8ad',
    'CI2',
    'structured_output_capacity_limitation',
    'Retrieval and governed context representation completed successfully, but Granite repeatedly failed to complete a schema-valid structured response for Q06 within the governed output ceiling. The final hardened run preserved the raw response and terminated cleanly at the 500-token limit. No evaluable interpretative result was produced.'
WHERE EXISTS (
    SELECT 1
    FROM experiment_runs
    WHERE run_id = 'experiment-cb1d519cd8ad'
      AND question_id = 'CI2'
      AND status = 'failed'
      AND error_code = 'output_token_exhaustion'
      AND raw_model_response IS NOT NULL
    AND (parsed_response_json IS NULL OR parsed_response_json = 'null'::jsonb)
      AND formal_authorization_id = 'turin-q06-v12-orphaned-inference-write-ahead-replacement-authorization'
)
AND NOT EXISTS (
    SELECT 1 FROM turin_research_incident_notes
    WHERE note_id = 'turin-q06-structured-output-capacity-closure'
);

COMMIT;
