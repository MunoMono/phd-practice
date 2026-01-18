#!/bin/bash
#
# Database Restore Script
# Restores PostgreSQL database from a backup file
#
# Usage: ./restore-database.sh <backup_file>
#

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lht /Users/graham/Documents/repos/ai-methods/backups/*.sql.gz 2>/dev/null | head -10 || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-epistemic_drift}"
CONTAINER_NAME="${CONTAINER_NAME:-epistemic-drift-db}"

# Verify backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file '${BACKUP_FILE}' not found!"
    exit 1
fi

echo "=== Database Restore ==="
echo "Backup file: ${BACKUP_FILE}"
echo "Database: ${POSTGRES_DB}"
echo ""
read -p "This will overwrite the current database. Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Database container '${CONTAINER_NAME}' is not running!"
    exit 1
fi

echo ""
echo "Creating pre-restore backup..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PRE_RESTORE_BACKUP="/Users/graham/Documents/repos/ai-methods/backups/pre_restore_${TIMESTAMP}.sql.gz"
docker exec -t "${CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${PRE_RESTORE_BACKUP}"
echo "Pre-restore backup saved: ${PRE_RESTORE_BACKUP}"

echo ""
echo "Restoring database..."
gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo ""
echo "✓ Restore completed successfully!"
echo ""
echo "If you need to rollback, use: $0 ${PRE_RESTORE_BACKUP}"
