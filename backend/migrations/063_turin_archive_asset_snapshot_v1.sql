CREATE TABLE IF NOT EXISTS turin_archive_asset_snapshots (
    source_snapshot_version VARCHAR(128) NOT NULL,
    record_pid VARCHAR(255),
    attached_media_pid VARCHAR(255),
    asset_pid VARCHAR(255),
    asset_id VARCHAR(255),
    label TEXT,
    display_date TEXT,
    normalized_date TEXT,
    use_for_ml BOOLEAN,
    ml_pages TEXT,
    source_type TEXT,
    record_title TEXT,
    attached_media_title TEXT,
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    people JSONB NOT NULL DEFAULT '[]'::jsonb,
    projects JSONB NOT NULL DEFAULT '[]'::jsonb,
    box_title TEXT,
    collection_title TEXT,
    exact_project_title TEXT,
    exact_job_id TEXT,
    controlled_aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    preset_groups JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_snapshot_provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_snapshot_version, asset_pid, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_turin_archive_asset_snapshot_identity
    ON turin_archive_asset_snapshots (source_snapshot_version, asset_pid, asset_id);