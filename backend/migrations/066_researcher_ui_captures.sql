CREATE TABLE IF NOT EXISTS researcher_ui_captures (
    capture_id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    capture_classification VARCHAR(64) NOT NULL CHECK (capture_classification = 'RESEARCHER_UI_CAPTURE'),
    mode VARCHAR(64) NOT NULL CHECK (mode = 'archive_first_one_shot'),
    question_id VARCHAR(64),
    exact_question TEXT NOT NULL,
    corpus_version VARCHAR(255) NOT NULL,
    archive_snapshot_version VARCHAR(255) NOT NULL,
    retrieved_sources JSONB NOT NULL,
    selected_passages JSONB NOT NULL,
    qwen_raw_output TEXT,
    parsed_output_if_available JSONB,
    provenance_result JSONB NOT NULL,
    evidential_limits JSONB NOT NULL,
    model_config JSONB NOT NULL
);

CREATE OR REPLACE FUNCTION reject_researcher_ui_capture_update()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'researcher_ui_captures are immutable';
END;
$$;

DROP TRIGGER IF EXISTS reject_researcher_ui_capture_update ON researcher_ui_captures;
CREATE TRIGGER reject_researcher_ui_capture_update
BEFORE UPDATE OR DELETE ON researcher_ui_captures
FOR EACH ROW EXECUTE FUNCTION reject_researcher_ui_capture_update();