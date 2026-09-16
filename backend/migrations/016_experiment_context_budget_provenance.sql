-- Versioned final-input budgeting for future immutable Turin experiment runs.
ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS context_budget_json JSONB;

ALTER TABLE experiment_run_evidence
    ADD COLUMN IF NOT EXISTS supplied_excerpt TEXT,
    ADD COLUMN IF NOT EXISTS original_chars INTEGER,
    ADD COLUMN IF NOT EXISTS supplied_chars INTEGER,
    ADD COLUMN IF NOT EXISTS excerpted BOOLEAN,
    ADD COLUMN IF NOT EXISTS exclusion_reason VARCHAR(128);