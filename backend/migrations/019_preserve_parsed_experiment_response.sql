-- Preserve the schema-valid model response independently from failure-safe display output.
ALTER TABLE experiment_runs
    ADD COLUMN IF NOT EXISTS parsed_response_json JSONB;