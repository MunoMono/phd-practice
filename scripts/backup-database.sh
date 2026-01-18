#!/bin/bash
#
# Database Backup Script for PhD Research Data
# Runs daily at 2am via cron
#
# This script:
# - Creates timestamped PostgreSQL dumps
# - Retains backups for 30 days
# - Logs backup operations
# - Optionally uploads to S3-compatible storage
#

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/Users/graham/Documents/repos/ai-methods/backups}"
LOG_DIR="${LOG_DIR:-/Users/graham/Documents/repos/ai-methods/logs}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE=$(date +"%Y-%m-%d")
BACKUP_FILE="epistemic_drift_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="${LOG_DIR}/backup_${DATE}.log"

# Database credentials (from .env or defaults)
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-epistemic_drift}"
CONTAINER_NAME="${CONTAINER_NAME:-epistemic-drift-db}"

# Create directories if they don't exist
mkdir -p "${BACKUP_DIR}"
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "=== Starting database backup ==="
log "Backup file: ${BACKUP_FILE}"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Database container '${CONTAINER_NAME}' is not running!"
    exit 1
fi

# Perform backup using pg_dump
log "Creating database dump..."
if docker exec -t "${CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    log "SUCCESS: Backup completed successfully (${BACKUP_SIZE})"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# Verify backup file exists and is not empty
if [ ! -s "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    log "ERROR: Backup file is empty or does not exist!"
    exit 1
fi

# Optional: Upload to S3-compatible storage (MinIO/S3)
if [ -n "${S3_BUCKET}" ] && [ -n "${S3_ENDPOINT}" ]; then
    log "Uploading backup to S3..."
    if command -v aws &> /dev/null; then
        aws --endpoint-url="${S3_ENDPOINT}" \
            s3 cp "${BACKUP_DIR}/${BACKUP_FILE}" \
            "s3://${S3_BUCKET}/backups/${BACKUP_FILE}" \
            && log "S3 upload successful" \
            || log "WARNING: S3 upload failed"
    else
        log "WARNING: AWS CLI not installed, skipping S3 upload"
    fi
fi

# Clean up old backups (keep only last RETENTION_DAYS days)
log "Cleaning up old backups (keeping last ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "epistemic_drift_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
REMAINING=$(find "${BACKUP_DIR}" -name "epistemic_drift_backup_*.sql.gz" -type f | wc -l | tr -d ' ')
log "Cleanup complete. ${REMAINING} backup(s) remaining."

# Optional: Backup volumes
log "Creating volume backup info..."
docker volume inspect epistemic-drift-db_postgres_data > "${BACKUP_DIR}/volume_info_${TIMESTAMP}.json" 2>/dev/null || true

log "=== Backup completed successfully ==="
log ""

exit 0
