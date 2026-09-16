-- Archive metadata synchronisation provenance. These fields describe the
-- current DDR metadata snapshot, not the extracted source-document evidence.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS archive_metadata_fetched_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS archive_metadata_source VARCHAR(255),
    ADD COLUMN IF NOT EXISTS archive_metadata_snapshot_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS metadata_sync_status VARCHAR(64),
    ADD COLUMN IF NOT EXISTS metadata_sync_error TEXT,
    ADD COLUMN IF NOT EXISTS source_asset_checksum VARCHAR(128),
    ADD COLUMN IF NOT EXISTS source_asset_identity_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS source_asset_changed INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reingestion_required INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS documents_archive_metadata_snapshot_hash_idx
ON documents(archive_metadata_snapshot_hash);

CREATE INDEX IF NOT EXISTS documents_metadata_sync_status_idx
ON documents(metadata_sync_status);

CREATE INDEX IF NOT EXISTS documents_source_asset_identity_hash_idx
ON documents(source_asset_identity_hash);

COMMENT ON COLUMN documents.archive_metadata_snapshot_hash IS 'SHA-256 hash of the normalised DDR GraphQL metadata snapshot used for this local record.';
COMMENT ON COLUMN documents.source_asset_checksum IS 'Checksum supplied by DDR for the current source asset, when DDR exposes one; distinct from the checksum of locally ingested bytes.';
COMMENT ON COLUMN documents.source_asset_identity_hash IS 'SHA-256 hash of stable DDR source-asset identity fields used to detect an upstream asset replacement.';
COMMENT ON COLUMN documents.reingestion_required IS 'Set when upstream asset identity changes; archive metadata may be current while extracted document evidence is stale.';