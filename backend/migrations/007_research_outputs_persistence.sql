-- Migration: persistence foundations for missingness and claims research outputs
-- Purpose: replace first-wave frontend mock data for Absences and Claims & Evidence.

CREATE TABLE IF NOT EXISTS missingness_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(32) NOT NULL CHECK (type IN ('documentary', 'descriptive', 'retrieval', 'institutional', 'historiographic', 'computational')),
    query_or_entity_or_field TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source_document_id VARCHAR(255),
    source_chunk_id VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'triaged', 'resolved')),
    reviewer_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_missingness_events_type ON missingness_events(type);
CREATE INDEX IF NOT EXISTS idx_missingness_events_status ON missingness_events(status);
CREATE INDEX IF NOT EXISTS idx_missingness_events_source_document_id ON missingness_events(source_document_id);

DROP TRIGGER IF EXISTS update_missingness_events_updated_at ON missingness_events;

CREATE TRIGGER update_missingness_events_updated_at
    BEFORE UPDATE ON missingness_events
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS claims (
    id SERIAL PRIMARY KEY,
    claim_id VARCHAR(255) NOT NULL UNIQUE,
    claim_text TEXT NOT NULL,
    support_level VARCHAR(32) NOT NULL DEFAULT 'unresolved' CHECK (support_level IN ('supported', 'partially_supported', 'unresolved', 'unsupported')),
    caveats TEXT,
    reviewer_status VARCHAR(64) NOT NULL DEFAULT 'draft' CHECK (reviewer_status IN ('draft', 'in_review', 'ready_for_supervisor_review', 'needs_evidence')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claims_support_level ON claims(support_level);
CREATE INDEX IF NOT EXISTS idx_claims_reviewer_status ON claims(reviewer_status);

DROP TRIGGER IF EXISTS update_claims_updated_at ON claims;

CREATE TRIGGER update_claims_updated_at
    BEFORE UPDATE ON claims
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS claim_evidence (
    id SERIAL PRIMARY KEY,
    claim_id VARCHAR(255) NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) NOT NULL,
    document_id VARCHAR(255),
    page_range VARCHAR(255),
    citation_text TEXT,
    provenance_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim_id ON claim_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_chunk_id ON claim_evidence(chunk_id);

INSERT INTO missingness_events (
    event_id,
    type,
    query_or_entity_or_field,
    evidence,
    source_document_id,
    source_chunk_id,
    status,
    reviewer_note
)
SELECT *
FROM (
    VALUES
        (
            'dev-miss-001',
            'retrieval',
            'women-led administration',
            'Development seed: source interrogation returned no chunks for a targeted local query.',
            NULL,
            NULL,
            'reviewing',
            'Development seed only. Treat as provisional until retrieval-trail persistence is in place.'
        ),
        (
            'dev-miss-002',
            'descriptive',
            'creator field',
            'Development seed: creator metadata is absent on a locally ingested record.',
            '606',
            NULL,
            'open',
            'Development seed only. Check authority sync before interpreting as archive silence.'
        ),
        (
            'dev-miss-003',
            'institutional',
            'institutional conflict',
            'Development seed: description foregrounds projects more than internal contestation.',
            '599',
            NULL,
            'triaged',
            'Development seed only. Surface as caveat, not finding.'
        )
) AS seed_rows(event_id, type, query_or_entity_or_field, evidence, source_document_id, source_chunk_id, status, reviewer_note)
WHERE NOT EXISTS (
    SELECT 1 FROM missingness_events existing WHERE existing.event_id = seed_rows.event_id
);

INSERT INTO claims (
    claim_id,
    claim_text,
    support_level,
    caveats,
    reviewer_status
)
SELECT *
FROM (
    VALUES
        (
            'dev-claim-001',
            'Development seed: local DDR administrative records foreground outputs more consistently than they document supporting labour.',
            'supported',
            'Development seed only. Local corpus remains limited to a small ingested sample.',
            'ready_for_supervisor_review'
        ),
        (
            'dev-claim-002',
            'Development seed: women-led administrative labour is absent from the local archive surface.',
            'unresolved',
            'Development seed only. Current state may reflect retrieval or ingestion gaps rather than documentary absence.',
            'needs_evidence'
        ),
        (
            'dev-claim-003',
            'Development seed: cross-read probes suggest institutional uncertainty around the status of design research.',
            'partially_supported',
            'Development seed only. Requires more archival records before generalising.',
            'in_review'
        )
) AS seed_rows(claim_id, claim_text, support_level, caveats, reviewer_status)
WHERE NOT EXISTS (
    SELECT 1 FROM claims existing WHERE existing.claim_id = seed_rows.claim_id
);

INSERT INTO claim_evidence (
    claim_id,
    chunk_id,
    document_id,
    page_range,
    citation_text,
    provenance_json
)
SELECT *
FROM (
    VALUES
        (
            'dev-claim-001',
            'dev-chunk-019',
            'doc-dev-019',
            'pp. 2-3',
            'Development seed citation for dev-chunk-019.',
            '{"status": "development-seed", "note": "Replace with persisted provenance when claim evidence is attached from a real chunk."}'::jsonb
        )
) AS seed_rows(claim_id, chunk_id, document_id, page_range, citation_text, provenance_json)
WHERE NOT EXISTS (
    SELECT 1 FROM claim_evidence existing
    WHERE existing.claim_id = seed_rows.claim_id
      AND existing.chunk_id = seed_rows.chunk_id
);