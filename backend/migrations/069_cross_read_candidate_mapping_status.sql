-- Migration: distinguish retrieval candidates from researcher-confirmed relations.

ALTER TABLE cross_read_mappings
    DROP CONSTRAINT IF EXISTS cross_read_mappings_relation_type_check,
    ADD CONSTRAINT cross_read_mappings_relation_type_check
        CHECK (relation_type IN ('unreviewed', 'supports', 'complicates', 'contradicts', 'no_documentary_trace'));