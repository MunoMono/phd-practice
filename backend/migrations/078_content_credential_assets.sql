CREATE TABLE IF NOT EXISTS content_credential_assets (
    id SERIAL PRIMARY KEY,
    asset_id VARCHAR(255) NOT NULL UNIQUE,
    query_id VARCHAR(255) NOT NULL REFERENCES query_runs(query_id) ON DELETE RESTRICT,
    asset_format VARCHAR(128) NOT NULL,
    asset_bytes BYTEA NOT NULL,
    asset_sha256 VARCHAR(64) NOT NULL UNIQUE,
    manifest_sha256 VARCHAR(64),
    validation_state VARCHAR(64) NOT NULL,
    validation_status_json JSONB NOT NULL,
    signer_subject VARCHAR(512),
    signer_trust VARCHAR(64) NOT NULL DEFAULT 'untrusted_research',
    created_by VARCHAR(255) NOT NULL DEFAULT 'system',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_content_credential_assets_query_id
    ON content_credential_assets(query_id);
CREATE INDEX IF NOT EXISTS ix_content_credential_assets_validation_state
    ON content_credential_assets(validation_state);