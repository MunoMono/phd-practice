ALTER TABLE turin_archive_authority_source_relations
    ADD COLUMN IF NOT EXISTS derivation_tier VARCHAR(64),
    ADD COLUMN IF NOT EXISTS trigger_field VARCHAR(128),
    ADD COLUMN IF NOT EXISTS trigger_value_raw TEXT,
    ADD COLUMN IF NOT EXISTS trigger_value_normalized TEXT,
    ADD COLUMN IF NOT EXISTS authority_value_normalized TEXT,
    ADD COLUMN IF NOT EXISTS source_snapshot_version VARCHAR(128),
    ADD COLUMN IF NOT EXISTS trigger_json_path TEXT,
    ADD COLUMN IF NOT EXISTS source_record_pid VARCHAR(255),
    ADD COLUMN IF NOT EXISTS source_attached_media_pid VARCHAR(255),
    ADD COLUMN IF NOT EXISTS source_asset_pid VARCHAR(255);

UPDATE turin_archive_authority_source_relations
SET derivation_tier = CASE derivation_method
        WHEN 'exact_controlled_identifier' THEN 'TIER_2_EXACT_CONTROLLED_IDENTIFIER'
        WHEN 'exact_controlled_metadata' THEN 'TIER_3_EXACT_CONTROLLED_METADATA'
        WHEN 'exact_archive_metadata' THEN 'TIER_3_EXACT_CONTROLLED_METADATA'
    END,
    source_snapshot_version = 'turin-archive-metadata-v1',
    source_record_pid = archive_record_pid,
    source_attached_media_pid = attached_media_pid,
    source_asset_pid = asset_pid
WHERE snapshot_version = 'turin-archive-authority-graph-v1';