-- Retain legacy annotations while enabling the researcher-facing connected-UAT relation vocabulary.
ALTER TABLE cross_read_mappings
    DROP CONSTRAINT IF EXISTS cross_read_mappings_relation_type_check,
    ADD CONSTRAINT cross_read_mappings_relation_type_check
        CHECK (relation_type IN (
            'unreviewed',
            'convergence',
            'contradiction',
            'complication',
            'contextual_relation',
            'no_documentary_trace',
            'supports',
            'complicates',
            'contradicts'
        ));