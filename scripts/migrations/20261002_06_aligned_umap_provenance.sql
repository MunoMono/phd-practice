BEGIN;

CREATE TABLE IF NOT EXISTS aligned_umap_runs (
    id BIGSERIAL PRIMARY KEY,
    aligned_run_id VARCHAR(255) NOT NULL UNIQUE,
    baseline_projection_id VARCHAR(255) NOT NULL,
    baseline_embedding_set_id VARCHAR(255) NOT NULL,
    corpus_snapshot_id VARCHAR(255) NOT NULL,
    dimensions INTEGER NOT NULL,
    parameters_json JSONB NOT NULL,
    method_version VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (dimensions >= 2),
    CHECK (status IN ('draft', 'pending_validation', 'validated', 'invalid'))
);

CREATE TABLE IF NOT EXISTS aligned_umap_slices (
    id BIGSERIAL PRIMARY KEY,
    slice_id VARCHAR(255) NOT NULL UNIQUE,
    aligned_run_id VARCHAR(255) NOT NULL REFERENCES aligned_umap_runs(aligned_run_id) ON DELETE CASCADE,
    slice_order INTEGER NOT NULL,
    period_provenance_json JSONB NOT NULL,
    membership_query_json JSONB NOT NULL,
    point_count INTEGER NOT NULL,
    exclusions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (aligned_run_id, slice_order),
    CHECK (slice_order >= 0),
    CHECK (point_count > 0)
);

CREATE TABLE IF NOT EXISTS aligned_umap_relations (
    id BIGSERIAL PRIMARY KEY,
    relation_id VARCHAR(255) NOT NULL UNIQUE,
    aligned_run_id VARCHAR(255) NOT NULL REFERENCES aligned_umap_runs(aligned_run_id) ON DELETE CASCADE,
    from_slice_id VARCHAR(255) NOT NULL REFERENCES aligned_umap_slices(slice_id) ON DELETE CASCADE,
    to_slice_id VARCHAR(255) NOT NULL REFERENCES aligned_umap_slices(slice_id) ON DELETE CASCADE,
    source_point_id VARCHAR(255) NOT NULL,
    target_point_id VARCHAR(255) NOT NULL,
    relation_type VARCHAR(128) NOT NULL,
    authority_provenance_json JSONB NOT NULL,
    validator_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_slice_id <> to_slice_id),
    CHECK (validator_status IN ('pending', 'valid', 'invalid'))
);

CREATE TABLE IF NOT EXISTS aligned_umap_validation_reports (
    id BIGSERIAL PRIMARY KEY,
    report_id VARCHAR(255) NOT NULL UNIQUE,
    aligned_run_id VARCHAR(255) NOT NULL REFERENCES aligned_umap_runs(aligned_run_id) ON DELETE CASCADE,
    relation_coverage_json JSONB NOT NULL,
    exclusions_json JSONB NOT NULL,
    diagnostics_json JSONB NOT NULL,
    reviewer VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_aligned_umap_runs_scope ON aligned_umap_runs (baseline_projection_id, baseline_embedding_set_id, corpus_snapshot_id);
CREATE INDEX IF NOT EXISTS ix_aligned_umap_relations_pair ON aligned_umap_relations (aligned_run_id, from_slice_id, to_slice_id);
CREATE INDEX IF NOT EXISTS ix_aligned_umap_relations_points ON aligned_umap_relations (source_point_id, target_point_id);
CREATE INDEX IF NOT EXISTS ix_aligned_umap_validation_reports_run ON aligned_umap_validation_reports (aligned_run_id, created_at DESC);

COMMIT;
