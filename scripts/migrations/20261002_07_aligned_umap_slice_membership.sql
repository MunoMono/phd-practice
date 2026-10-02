BEGIN;

ALTER TABLE aligned_umap_slices
    ADD COLUMN IF NOT EXISTS membership_point_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE aligned_umap_slices
    ADD CONSTRAINT aligned_umap_slices_membership_ids_array
    CHECK (jsonb_typeof(membership_point_ids_json) = 'array');

ALTER TABLE aligned_umap_slices
    ADD CONSTRAINT aligned_umap_slices_membership_not_empty
    CHECK (jsonb_array_length(membership_point_ids_json) > 0);

ALTER TABLE aligned_umap_slices
    ADD CONSTRAINT aligned_umap_slices_membership_count_matches
    CHECK (point_count = jsonb_array_length(membership_point_ids_json));

COMMIT;
