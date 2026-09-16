CREATE TABLE IF NOT EXISTS turin_archive_authority_graph_snapshots (
    snapshot_version VARCHAR(128) PRIMARY KEY,
    corpus_version VARCHAR(255) NOT NULL,
    metadata_snapshot_version VARCHAR(128) NOT NULL,
    materialiser_version VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS turin_archive_authority_source_relations (
    relation_id VARCHAR(255) PRIMARY KEY,
    snapshot_version VARCHAR(128) NOT NULL REFERENCES turin_archive_authority_graph_snapshots(snapshot_version),
    authority_type VARCHAR(128) NOT NULL,
    authority_id VARCHAR(255) NOT NULL,
    authority_label TEXT NOT NULL,
    relation_type VARCHAR(128) NOT NULL,
    archive_record_pid VARCHAR(255),
    attached_media_pid VARCHAR(255),
    asset_pid VARCHAR(255),
    asset_id VARCHAR(255),
    document_id VARCHAR(255) NOT NULL,
    derivation_method VARCHAR(128) NOT NULL,
    source_of_relation TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(snapshot_version, authority_type, authority_id, relation_type, document_id, derivation_method)
);

CREATE INDEX IF NOT EXISTS idx_turin_archive_authority_source_relation_authority
    ON turin_archive_authority_source_relations(snapshot_version, authority_type, authority_id);
CREATE INDEX IF NOT EXISTS idx_turin_archive_authority_source_relation_document
    ON turin_archive_authority_source_relations(snapshot_version, document_id);