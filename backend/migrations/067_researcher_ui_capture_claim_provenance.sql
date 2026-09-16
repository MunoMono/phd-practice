ALTER TABLE researcher_ui_captures
    ADD COLUMN IF NOT EXISTS claim_provenance JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS source_classifications JSONB NOT NULL DEFAULT '[]'::jsonb;