#!/bin/bash
#
# Setup Backup Cron Job
# Configures daily database backup at 2am local time
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup-database.sh"

echo "Setting up daily backup cron job at 2am..."

# Make backup script executable
chmod +x "${BACKUP_SCRIPT}"

# Create cron job entry
CRON_ENTRY="0 2 * * * cd ${PROJECT_DIR} && ${BACKUP_SCRIPT} >> ${PROJECT_DIR}/logs/backup_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "${BACKUP_SCRIPT}"; then
    echo "Cron job already exists. Updating..."
    # Remove old entry and add new one
    (crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}"; echo "${CRON_ENTRY}") | crontab -
else
    echo "Adding new cron job..."
    # Add to existing crontab or create new one
    (crontab -l 2>/dev/null; echo "${CRON_ENTRY}") | crontab -
fi

echo ""
echo "✓ Backup cron job configured successfully!"
echo ""
echo "Schedule: Daily at 2:00 AM local time"
echo "Backup script: ${BACKUP_SCRIPT}"
echo "Backup directory: ${PROJECT_DIR}/backups"
echo "Log directory: ${PROJECT_DIR}/logs"
echo ""
echo "Current crontab:"
crontab -l | grep -v "^#" | grep -v "^$" || echo "(no active cron jobs)"
echo ""
echo "To verify the setup, you can:"
echo "  - Check cron jobs: crontab -l"
echo "  - Test backup manually: ${BACKUP_SCRIPT}"
echo "  - View backup logs: tail -f ${PROJECT_DIR}/logs/backup_*.log"
echo ""

# Create initial directories
mkdir -p "${PROJECT_DIR}/backups"
mkdir -p "${PROJECT_DIR}/logs"

echo "Setup complete!"
