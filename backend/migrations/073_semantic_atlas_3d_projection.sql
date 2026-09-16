-- Migration: permit versioned three-dimensional Semantic Atlas projections.

ALTER TABLE semantic_atlas_projection_points
    ADD COLUMN IF NOT EXISTS z DOUBLE PRECISION;