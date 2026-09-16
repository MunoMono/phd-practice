ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS asset_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS asset_pid VARCHAR(255),
    ADD COLUMN IF NOT EXISTS asset_id_or_asset_pid VARCHAR(255),
    ADD COLUMN IF NOT EXISTS use_for_ml INTEGER,
    ADD COLUMN IF NOT EXISTS ml_page_scope TEXT,
    ADD COLUMN IF NOT EXISTS ml_policy_status VARCHAR(64),
    ADD COLUMN IF NOT EXISTS ml_exclusion_reason TEXT;

CREATE INDEX IF NOT EXISTS documents_asset_id_idx
ON documents(asset_id);

CREATE INDEX IF NOT EXISTS documents_asset_pid_idx
ON documents(asset_pid);

CREATE INDEX IF NOT EXISTS documents_asset_identifier_idx
ON documents(asset_id_or_asset_pid);

CREATE INDEX IF NOT EXISTS documents_ml_policy_status_idx
ON documents(ml_policy_status);