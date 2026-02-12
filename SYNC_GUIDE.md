# Authority Sync System Guide

## Overview

Enterprise-grade sync system for fetching authorities from DDR Archive GraphQL and storing in local PostgreSQL/pgvector.

## Architecture

```
┌─────────────────────────────────────────┐
│  DDR Archive GraphQL (External)         │
│  • Authorities with PIDs                │
│  • Media attachments (PDF/TIFF)         │
└──────────────┬──────────────────────────┘
               │
               │ Sync Methods:
               │ • Scheduled (daily at 2 AM)
               │ • Manual trigger (API)
               │ • Incremental (only changed)
               │
               ▼
┌─────────────────────────────────────────┐
│  GraphQL Sync Service                   │
│  • Validates PIDs                       │
│  • Fetches metadata                     │
│  • Filters for training eligibility     │
│  • Logs all operations                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  PostgreSQL + pgvector                  │
│  • documents (with PIDs)                │
│  • sync_log (audit trail)               │
│  • sync_metadata (health monitoring)    │
└─────────────────────────────────────────┘
```

## Database Tables

### `sync_log`
Audit trail for all sync operations.

```sql
SELECT * FROM sync_log 
ORDER BY sync_started_at DESC 
LIMIT 10;
```

**Key columns:**
- `sync_id` - Unique identifier
- `sync_type` - scheduled/manual/incremental/full
- `records_new` - New documents added
- `records_updated` - Existing documents updated
- `records_failed` - Failed operations
- `status` - running/completed/failed/partial

### `sync_metadata`
Per-source configuration and health monitoring.

```sql
SELECT * FROM sync_metadata 
WHERE source_system = 'ddr_graphql';
```

**Key columns:**
- `last_sync_timestamp` - When last sync completed
- `health_status` - healthy/degraded/offline
- `consecutive_failures` - Alert if > 2
- `sync_frequency_hours` - 24 for daily

### `documents`
Training corpus with PID linkage.

**New columns for sync:**
- `last_synced_at` - Timestamp of last update
- `sync_version` - Increments on each update

## Sync Types

### 1. Scheduled Sync (Recommended)

**Frequency:** Daily at 2:00 AM

**Setup:**
```bash
# Run setup script
./scripts/setup-cron-sync.sh

# Or manually add to crontab
crontab -e
# Add: 0 2 * * * /usr/local/bin/sync-authorities.sh
```

**What it does:**
- Runs incremental sync (only changed records)
- Logs to `/var/log/authority-sync.log`
- Updates sync_metadata health status
- Sends alerts if failures occur

### 2. Manual Sync (API)

**Endpoint:** `POST /api/v1/sync/authorities/manual`

**Use cases:**
- PhD researcher adds new authority
- Need immediate update
- Testing sync functionality

**Example:**
```bash
# Sync all (incremental)
curl -X POST http://localhost:8000/api/v1/sync/authorities/manual

# Sync specific PIDs
curl -X POST http://localhost:8000/api/v1/sync/authorities/manual \
  -H "Content-Type: application/json" \
  -d '{"pids": ["564310168393", "987654321012"]}'

# Force full refresh
curl -X POST http://localhost:8000/api/v1/sync/authorities/manual \
  -H "Content-Type: application/json" \
  -d '{"force_refresh": true}'
```

### 3. Incremental Sync

**How it works:**
- Queries `sync_metadata` for `last_sync_timestamp`
- Only fetches records changed since that time
- Updates `documents.sync_version` on changes
- Faster and API-friendly

**Benefits:**
- Reduces API load 95%+
- Faster sync times
- Lower database writes
- Gentler on DDR Archive

## API Endpoints

### Sync Control

```bash
# Start scheduled sync (cron endpoint)
POST /api/v1/sync/authorities/scheduled
Headers: X-API-Key: your_api_key

# Manual sync
POST /api/v1/sync/authorities/manual
Body: {
  "pids": ["564310168393"],  # Optional: specific PIDs
  "force_refresh": false     # Optional: force re-fetch
}

# Get sync status
GET /api/v1/sync/status

# Get sync history
GET /api/v1/sync/history?limit=20
```

### Health Monitoring

```bash
# Check sync health
GET /api/v1/sync/status

Response:
{
  "graphql_sync": {
    "last_sync": "2026-01-30T02:00:00Z",
    "status": "completed",
    "health": "healthy",
    "hours_since_last": 10.5,
    "alert_status": "OK"
  },
  "recent_syncs": [...]
}
```

## Monitoring

### Health Views

```sql
-- Overall sync health
SELECT * FROM sync_health;

-- Recent sync activity
SELECT * FROM recent_syncs;

-- Check for overdue syncs
SELECT 
    source_system,
    last_sync_timestamp,
    hours_since_last_sync,
    alert_status
FROM sync_health
WHERE alert_status IN ('OVERDUE', 'DEGRADED');
```

### Alert Conditions

**OVERDUE:** Last sync > 1.5x expected frequency (36+ hours for daily)
**DEGRADED:** 1-2 consecutive failures
**OFFLINE:** 3+ consecutive failures

### Logs

```bash
# View cron sync log
tail -f /var/log/authority-sync.log

# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend | grep sync

# Database sync log
psql -d epistemic_drift -c "SELECT * FROM sync_log ORDER BY sync_started_at DESC LIMIT 10;"
```

## Production Deployment

### Environment Variables

```bash
# .env file
DDR_GRAPHQL_ENDPOINT=https://ddr-archive.org/graphql
DDR_API_TOKEN=your_token_here
SYNC_API_KEY=change_me_in_production  # For cron endpoint security
```

### On Droplet

```bash
# SSH into droplet
ssh root@104.248.170.26

# Setup cron
cd /root/phd-practice
./scripts/setup-cron-sync.sh

# Check cron is running
crontab -l

# Monitor first sync
tail -f /var/log/authority-sync.log
```

### Security

**Cron endpoint security:**
```python
# backend/app/api/routes/sync.py
@router.post("/authorities/scheduled")
async def scheduled_authority_sync(
    x_api_key: Optional[str] = Header(None)
):
    # Validate API key
    if x_api_key != settings.SYNC_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

## Troubleshooting

### Sync not running

```bash
# Check cron service
systemctl status cron  # Linux
# or
launchctl list | grep cron  # macOS

# Check crontab
crontab -l

# Run manually
/usr/local/bin/sync-authorities.sh
```

### Sync failing

```bash
# Check sync log
SELECT * FROM sync_log 
WHERE status = 'failed' 
ORDER BY sync_started_at DESC;

# Check error log
SELECT sync_id, error_log, triggered_by 
FROM sync_log 
WHERE status = 'failed';

# Check health status
SELECT * FROM sync_health 
WHERE health_status != 'healthy';
```

### Missing PIDs

```sql
-- Documents without PIDs (orphaned)
SELECT document_id, filename, publication_year 
FROM documents 
WHERE pid IS NULL;

-- PID coverage statistics
SELECT 
  COUNT(*) as total_documents,
  COUNT(pid) as documents_with_pid,
  COUNT(*) - COUNT(pid) as orphaned_documents,
  ROUND(COUNT(pid)::numeric / COUNT(*)::numeric * 100, 2) as pid_coverage_percent
FROM documents;
```

## Best Practices

### 1. Monitor Health Daily
- Check `/api/v1/sync/status` each morning
- Alert on `OVERDUE` or `DEGRADED` status
- Review failed syncs immediately

### 2. Incremental by Default
- Use incremental sync for daily operations
- Only use full refresh when necessary
- Reduces API load on DDR Archive

### 3. Manual Sync for Research
- PhD researchers trigger manual syncs
- Sync specific authorities as curated
- Immediate feedback for new additions

### 4. Audit Trail
- `sync_log` keeps complete history
- Track who triggered what and when
- Useful for reproducibility and debugging

### 5. Graceful Degradation
- Stale data better than no data
- Don't fail hard on sync errors
- Retry with exponential backoff

## Year 1 PhD Target

**Goal:** 50 PID-validated authorities

**Progress tracking:**
```sql
SELECT 
    COUNT(DISTINCT pid) as current_authorities,
    50 as target,
    ROUND((COUNT(DISTINCT pid)::numeric / 50) * 100, 1) as percent_complete
FROM documents 
WHERE pid IS NOT NULL;
```

**Sync frequency for curation:**
- Daily scheduled sync
- Manual triggers as needed
- Review new authorities weekly
- Quality over quantity

## Integration with Frontend

The stats card shows sync health:

```jsx
// frontend/src/components/StatsCards/StatsCards.jsx
const stats = await fetch('/api/graphql', {
  query: `{
    systemMetrics {
      pidCount
    }
  }`
})

// Display: "3/50 authorities curated"
```

## Future Enhancements

1. **Webhook Support**
   - DDR Archive sends updates via webhook
   - Near real-time sync for critical changes

2. **Conflict Resolution**
   - Handle concurrent updates
   - Version control for authority metadata

3. **Batch Processing**
   - Queue system for large syncs
   - Rate limiting for API calls

4. **Advanced Monitoring**
   - Grafana dashboards
   - Prometheus metrics
   - Email/Slack alerts

5. **Data Validation**
   - Schema validation for GraphQL responses
   - Data quality checks
   - Automated cleanup of orphaned records

## Summary

**Daily at 2 AM:** Cron triggers scheduled sync
**API available:** Manual triggers for researchers
**Full audit trail:** Every sync logged and tracked
**Health monitoring:** Real-time status and alerts
**Enterprise-ready:** Incremental, idempotent, monitored

Questions? Check sync status at: `http://localhost:8000/api/v1/sync/status`
