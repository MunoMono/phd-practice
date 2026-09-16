ALTER TABLE turin_archive_asset_snapshots
    ADD COLUMN IF NOT EXISTS source_snapshot_provenance JSONB NOT NULL DEFAULT '{}'::jsonb;