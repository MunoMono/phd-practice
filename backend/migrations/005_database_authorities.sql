-- Migration 005: Database Authorities Table
-- Creates table to store DDR database authorities (controlled vocabularies)
-- These provide ground truth labels for ML training and provenance tracking
-- 
-- 5 Core Intended Categories (provenance):
--   - agent_employment, ddr_projects, ref_students, ref_fonds, ref_publication_type
-- 
-- 6 Critical Categories (ML labels):
--   - ref_epistemic_stance, ref_methodology, ref_project_theme, 
--     ref_ddr_period, ref_beneficiary_audience, ref_project_outcome

CREATE TABLE IF NOT EXISTS database_authorities (
    id SERIAL PRIMARY KEY,
    authority_type VARCHAR(50) NOT NULL,     -- e.g., 'ref_epistemic_stance'
    authority_id VARCHAR(100) NOT NULL,      -- from DDR GraphQL (id/code/slug field)
    code VARCHAR(100),                       -- optional code field
    label TEXT NOT NULL,                     -- human-readable label
    description TEXT,                        -- detailed description
    category VARCHAR(20) NOT NULL,           -- 'core' or 'critical'
    
    -- Additional fields for specific authority types
    metadata JSONB,                          -- flexible storage for type-specific fields
    
    synced_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure uniqueness per authority type and ID
    UNIQUE(authority_type, authority_id)
);

-- Index for fast lookups by type and category
CREATE INDEX idx_db_authorities_type ON database_authorities(authority_type);
CREATE INDEX idx_db_authorities_category ON database_authorities(category);

-- Index for JSONB metadata queries
CREATE INDEX idx_db_authorities_metadata ON database_authorities USING gin(metadata);

-- Comments for documentation
COMMENT ON TABLE database_authorities IS 'DDR database authorities: controlled vocabularies for provenance and ML training';
COMMENT ON COLUMN database_authorities.category IS 'core = provenance/attribution, critical = ML ground truth labels';
COMMENT ON COLUMN database_authorities.metadata IS 'Type-specific fields like year, degree, funder_name, start_date, etc.';
