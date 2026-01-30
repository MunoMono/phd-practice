-- Migration: Add sync logging and tracking for incremental updates
-- Enables enterprise-grade sync monitoring and incremental syncs

-- Sync log table for audit trail and monitoring
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    sync_id VARCHAR(255) UNIQUE NOT NULL,
    sync_type VARCHAR(50) NOT NULL,  -- 'scheduled', 'manual', 'incremental', 'full'
    sync_source VARCHAR(100) NOT NULL,  -- 'graphql_ddr_archive', 's3_spaces', etc.
    
    -- Timing
    sync_started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sync_completed_at TIMESTAMP,
    sync_duration_seconds INTEGER,
    
    -- Results
    records_fetched INTEGER DEFAULT 0,
    records_new INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    
    -- Tracking
    last_successful_pid VARCHAR(255),
    pids_processed JSONB,  -- Array of PIDs processed
    pids_failed JSONB,     -- Array of PIDs that failed
    
    -- Incremental sync tracking
    sync_since_timestamp TIMESTAMP,  -- For incremental syncs
    sync_checkpoint JSONB,           -- Resume point if sync fails
    
    -- Error handling
    status VARCHAR(50) NOT NULL,  -- 'running', 'completed', 'failed', 'partial'
    error_log TEXT,
    error_count INTEGER DEFAULT 0,
    
    -- Metadata
    triggered_by VARCHAR(255),  -- 'cron', 'api_user_123', 'webhook', etc.
    config JSONB,               -- Sync configuration used
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for querying sync history
CREATE INDEX IF NOT EXISTS idx_sync_log_sync_id ON sync_log(sync_id);
CREATE INDEX IF NOT EXISTS idx_sync_log_sync_type ON sync_log(sync_type);
CREATE INDEX IF NOT EXISTS idx_sync_log_started_at ON sync_log(sync_started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status);

-- Sync metadata table for tracking last successful sync per source
CREATE TABLE IF NOT EXISTS sync_metadata (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(100) UNIQUE NOT NULL,  -- 'ddr_graphql', 's3_spaces'
    
    -- Last successful sync info
    last_sync_timestamp TIMESTAMP,
    last_sync_id VARCHAR(255),
    last_sync_status VARCHAR(50),
    
    -- Statistics
    total_syncs_completed INTEGER DEFAULT 0,
    total_syncs_failed INTEGER DEFAULT 0,
    total_records_synced INTEGER DEFAULT 0,
    records_in_sync INTEGER,  -- Current count of records from this source
    
    -- Scheduling
    next_scheduled_sync TIMESTAMP,
    sync_frequency_hours INTEGER,  -- 24 for daily, 168 for weekly
    
    -- Health monitoring
    consecutive_failures INTEGER DEFAULT 0,
    last_error TEXT,
    health_status VARCHAR(50) DEFAULT 'healthy',  -- 'healthy', 'degraded', 'offline'
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default metadata for DDR Archive GraphQL sync
INSERT INTO sync_metadata (
    source_system,
    sync_frequency_hours,
    health_status
) VALUES (
    'ddr_graphql',
    24,  -- Daily sync
    'healthy'
) ON CONFLICT (source_system) DO NOTHING;

-- Add last_synced_at to documents table for incremental updates
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS sync_version INTEGER DEFAULT 1;

-- Index for incremental sync queries
CREATE INDEX IF NOT EXISTS idx_documents_last_synced_at ON documents(last_synced_at);

-- View for sync health monitoring
CREATE OR REPLACE VIEW sync_health AS
SELECT 
    sm.source_system,
    sm.last_sync_timestamp,
    sm.last_sync_status,
    sm.health_status,
    sm.consecutive_failures,
    sm.total_syncs_completed,
    sm.total_syncs_failed,
    sm.records_in_sync,
    EXTRACT(EPOCH FROM (NOW() - sm.last_sync_timestamp))/3600 as hours_since_last_sync,
    sm.next_scheduled_sync,
    CASE 
        WHEN sm.last_sync_timestamp IS NULL THEN 'Never synced'
        WHEN EXTRACT(EPOCH FROM (NOW() - sm.last_sync_timestamp))/3600 > (sm.sync_frequency_hours * 1.5) THEN 'OVERDUE'
        WHEN sm.consecutive_failures > 2 THEN 'DEGRADED'
        ELSE 'OK'
    END as alert_status
FROM sync_metadata sm;

-- View for recent sync activity
CREATE OR REPLACE VIEW recent_syncs AS
SELECT 
    sl.sync_id,
    sl.sync_type,
    sl.sync_source,
    sl.sync_started_at,
    sl.sync_completed_at,
    sl.sync_duration_seconds,
    sl.records_new,
    sl.records_updated,
    sl.records_failed,
    sl.status,
    sl.triggered_by
FROM sync_log sl
ORDER BY sl.sync_started_at DESC
LIMIT 50;

-- Comments for documentation
COMMENT ON TABLE sync_log IS 'Audit trail for all sync operations with DDR Archive and other sources';
COMMENT ON TABLE sync_metadata IS 'Per-source sync configuration and health monitoring';
COMMENT ON COLUMN documents.last_synced_at IS 'Timestamp of last sync for incremental updates';
COMMENT ON COLUMN documents.sync_version IS 'Increments on each update for change tracking';
COMMENT ON VIEW sync_health IS 'Real-time health status of all sync sources';

-- Function to get last successful sync time for a source
CREATE OR REPLACE FUNCTION get_last_sync_time(p_source VARCHAR)
RETURNS TIMESTAMP AS $$
BEGIN
    RETURN (
        SELECT last_sync_timestamp 
        FROM sync_metadata 
        WHERE source_system = p_source
    );
END;
$$ LANGUAGE plpgsql;

-- Function to record sync completion
CREATE OR REPLACE FUNCTION complete_sync(
    p_sync_id VARCHAR,
    p_records_new INTEGER,
    p_records_updated INTEGER,
    p_records_failed INTEGER,
    p_status VARCHAR
) RETURNS VOID AS $$
DECLARE
    v_started_at TIMESTAMP;
    v_source VARCHAR;
BEGIN
    -- Update sync log
    UPDATE sync_log 
    SET 
        sync_completed_at = CURRENT_TIMESTAMP,
        sync_duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - sync_started_at)),
        records_new = p_records_new,
        records_updated = p_records_updated,
        records_failed = p_records_failed,
        status = p_status
    WHERE sync_id = p_sync_id
    RETURNING sync_started_at, sync_source INTO v_started_at, v_source;
    
    -- Update sync metadata if successful
    IF p_status = 'completed' THEN
        UPDATE sync_metadata
        SET 
            last_sync_timestamp = v_started_at,
            last_sync_id = p_sync_id,
            last_sync_status = p_status,
            total_syncs_completed = total_syncs_completed + 1,
            total_records_synced = total_records_synced + p_records_new + p_records_updated,
            consecutive_failures = 0,
            health_status = 'healthy',
            updated_at = CURRENT_TIMESTAMP
        WHERE source_system = v_source;
    ELSE
        -- Record failure
        UPDATE sync_metadata
        SET 
            consecutive_failures = consecutive_failures + 1,
            total_syncs_failed = total_syncs_failed + 1,
            last_error = 'Sync failed with status: ' || p_status,
            health_status = CASE 
                WHEN consecutive_failures >= 3 THEN 'offline'
                WHEN consecutive_failures >= 1 THEN 'degraded'
                ELSE 'healthy'
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_system = v_source;
    END IF;
END;
$$ LANGUAGE plpgsql;
