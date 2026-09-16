CREATE TABLE IF NOT EXISTS turin_project_identities (
    project_identity_id VARCHAR(128) PRIMARY KEY,
    project_authority_id VARCHAR(100),
    project_job_id VARCHAR(100),
    project_title TEXT NOT NULL,
    normalized_project_title TEXT NOT NULL,
    source_of_truth VARCHAR(100) NOT NULL,
    source_path TEXT NOT NULL,
    archive_record_pid VARCHAR(100),
    attached_media_pid VARCHAR(100),
    asset_pid VARCHAR(100),
    snapshot_version VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_turin_project_identities_title ON turin_project_identities(normalized_project_title);
COMMENT ON TABLE turin_project_identities IS 'Append-only exact controlled project identities materialised from governed archive sources.';
